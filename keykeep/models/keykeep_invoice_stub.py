# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class KeykeepInvoiceStub(models.Model):
    _name = "keykeep.invoice.stub"
    _description = "Keykeep Invoice Stub"
    _order = "date asc"

    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        related="subscription_id.partner_id",
        store=True,
    )
    date = fields.Date(
        string="Period Start",
        required=True,
    )
    period_date_end = fields.Date(
        string="Period End",
    )
    amount = fields.Monetary(
        currency_field="currency_id",
        string="Amount",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="subscription_id.currency_id",
        store=True,
    )
    account_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("invoiced", "Invoiced"),
            ("skipped", "Skipped"),
        ],
        default="draft",
        string="Status",
    )

    # ---- Actions ----

    def action_create_invoice(self):
        """Create an in_invoice from this stub using template lines."""
        self.ensure_one()
        if self.account_move_id:
            return self.action_view_invoice()

        sub = self.subscription_id
        partner = self.partner_id

        # Find or create a purchase journal
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1
        )
        if not journal:
            raise ValidationError(_("No purchase journal found. Please create one."))

        if not sub.invoice_line_template_ids:
            raise ValidationError(_(
                "No invoice lines defined. Add lines under the Invoice tab first."
            ))

        # Build invoice line values from template lines
        inv_line_vals = []
        for tmpl in sub.invoice_line_template_ids:
            product = tmpl.product_id
            price_unit = tmpl.price_unit
            description = tmpl.name or (product.display_name if product else "")

            # If no manual price, use supplier pricing
            if not price_unit and product:
                seller = product._select_seller(
                    partner_id=partner.id,
                    quantity=tmpl.quantity,
                    date=self.date or fields.Date.today(),
                )
                if seller:
                    price_unit = seller.price_discounted
                    if seller.currency_id != self.currency_id:
                        price_unit = seller.currency_id._convert(
                            price_unit, self.currency_id, sub.company_id,
                            self.date or fields.Date.today()
                        )
                elif product.standard_price:
                    price_unit = product.standard_price

            # Account from product
            account = False
            if product:
                account = (
                    product.property_account_expense_id
                    or product.categ_id.property_account_expense_categ_id
                )

            line = {
                "name": description or _("%(sub)s — %(period)s") % {
                    "sub": sub.name,
                    "period": self.date.strftime("%Y-%m"),
                },
                "quantity": tmpl.quantity,
                "price_unit": price_unit or 0.0,
                "currency_id": self.currency_id.id,
            }
            if product:
                line["product_id"] = product.id
                line["product_uom_id"] = (tmpl.product_uom_id or product.uom_id).id
                if account:
                    line["account_id"] = account.id
            if tmpl.tax_ids:
                line["tax_ids"] = [(6, 0, tmpl.tax_ids.ids)]
            elif product:
                taxes = product.supplier_taxes_id.filtered(
                    lambda t: t.company_id in (sub.company_id, False)
                )
                if taxes:
                    line["tax_ids"] = [(6, 0, taxes.ids)]
            if tmpl.analytic_distribution:
                line["analytic_distribution"] = tmpl.analytic_distribution

            inv_line_vals.append((0, 0, line))

        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": self.date,
            "date": self.date,
            "ref": _("%(sub)s — %(period)s") % {
                "sub": sub.name,
                "period": self.date.strftime("%Y-%m"),
            },
            "journal_id": journal.id,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": inv_line_vals,
        })
        # Link the invoice to the subscription
        sub.write({
            "invoice_ids": [(4, move.id)],
        })
        self.write({
            "account_move_id": move.id,
            "state": "invoiced",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "name": _("Invoice"),
        }

    def action_view_invoice(self):
        """Open the linked invoice."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.account_move_id.id,
            "view_mode": "form",
            "name": _("Invoice"),
        }

    def action_delete_invoice(self):
        """Delete the linked draft invoice."""
        self.ensure_one()
        if self.account_move_id and self.account_move_id.state == "draft":
            self.account_move_id.unlink()
            self.account_move_id = False
            self.state = "draft"

    def action_skip_stub(self):
        """Mark stub as skipped."""
        self.state = "skipped"

    def unlink(self):
        for stub in self:
            if stub.account_move_id and stub.account_move_id.state not in ("draft", "cancel"):
                raise ValidationError(
                    _("Cannot delete stub %s: it has a posted invoice.") % stub.date
                )
            if stub.account_move_id:
                stub.account_move_id.with_context(force_delete=True).unlink()
        return super().unlink()
