# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import api, fields, models, _


class CreateJournalEntryWizard(models.TransientModel):
    _name = "keykeep.create.journal.entry"
    _description = "Create Journal Entry from Subscription"

    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
        readonly=True,
        default=lambda self: self._context.get("active_id"),
    )
    date = fields.Date(
        required=True,
        default=date.today(),
    )
    amount = fields.Monetary(
        currency_field="currency_id",
        required=True,
        default=lambda self: self._get_default_amount(),
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="subscription_id.currency_id",
    )
    expense_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Expense Account",
        required=True,
        domain="[('account_type', '=', 'expense')]",
        default=lambda self: self._get_default_expense_account(),
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        related="subscription_id.partner_id",
    )
    name = fields.Char(
        string="Journal Entry Label",
        compute="_compute_name",
        store=True,
        readonly=False,
    )

    def _get_default_amount(self):
        sub = self.env["keykeep.subscription"].browse(self._context.get("active_id"))
        return sub.cost_amount if sub else 0.0

    def _get_default_expense_account(self):
        sub = self.env["keykeep.subscription"].browse(self._context.get("active_id"))
        if sub.category_id and sub.category_id.expense_account_id:
            return sub.category_id.expense_account_id.id
        return False

    @api.depends("subscription_id", "date")
    def _compute_name(self):
        for wiz in self:
            if wiz.subscription_id:
                wiz.name = _("%(sub)s — %(date)s") % {
                    "sub": wiz.subscription_id.name,
                    "date": wiz.date,
                }

    def action_create_entry(self):
        """Create an account.move of type 'entry' for this subscription cost."""
        self.ensure_one()
        move = self.env["account.move"].create({
            "move_type": "entry",
            "date": self.date,
            "ref": self.name,
            "journal_id": self.env["account.journal"].search(
                [("type", "=", "general")], limit=1
            ).id,
            "line_ids": [
                (0, 0, {
                    "name": self.name,
                    "account_id": self.expense_account_id.id,
                    "debit": self.amount,
                    "credit": 0.0,
                    "partner_id": self.partner_id.id,
                    "currency_id": self.currency_id.id,
                }),
                (0, 0, {
                    "name": self.name,
                    "account_id": self.partner_id.property_account_payable_id.id,
                    "debit": 0.0,
                    "credit": self.amount,
                    "partner_id": self.partner_id.id,
                    "currency_id": self.currency_id.id,
                }),
            ],
        })
        # Link the entry to the subscription
        self.subscription_id.write({
            "journal_entry_ids": [(4, move.id)],
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
            "name": _("Journal Entry"),
        }
