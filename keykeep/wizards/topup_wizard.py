# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class KeykeepTopupWizard(models.TransientModel):
    _name = "keykeep.topup.wizard"
    _description = "Record Top-up"

    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
    )
    provider_id = fields.Many2one(
        comodel_name="res.partner",
        string="Provider",
        related="subscription_id.partner_id",
        readonly=True,
    )
    date = fields.Datetime(string="Date", default=fields.Datetime.now, required=True)
    amount = fields.Monetary(
        currency_field="currency_id",
        string="Amount",
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="subscription_id.currency_id",
        readonly=True,
    )
    method = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("auto", "Auto"),
            ("api", "API"),
        ],
        string="Method",
        default="manual",
        required=True,
    )
    source = fields.Selection(
        selection=[
            ("provider_portal", "Provider Portal"),
            ("provider_api", "Provider API"),
            ("bifrost_budget", "Bifrost Budget"),
            ("other", "Other"),
        ],
        string="Source",
        default="provider_portal",
    )
    payment_method_id = fields.Many2one(
        comodel_name="keykeep.payment.method",
        string="Payment Method",
    )
    receipt_ref = fields.Char(string="Receipt Reference")
    note = fields.Text(string="Note")

    @api.model
    def default_get(self, fields_list):
        """Default the amount:
        a) when burn_rate_day exists → cover one month (burn × 30)
        b) otherwise → parity with previous top-ups (latest confirmed/reconciled
           amount, or the average if several)."""
        res = super().default_get(fields_list)
        sub_id = self.env.context.get("default_subscription_id")
        if not sub_id:
            return res
        sub = self.env["keykeep.subscription"].browse(sub_id)
        if not sub:
            return res

        burn = sub.burn_rate_day or 0.0
        if burn > 0:
            res["amount"] = round(burn * 30, 2)
            return res

        prev = self.env["keykeep.topup"].search(
            [("subscription_id", "=", sub.id),
             ("state", "in", ["confirmed", "reconciled"])],
            order="date desc",
            limit=5,
        )
        if prev:
            res["amount"] = round(sum(prev.mapped("amount")) / len(prev), 2)
        return res

    def action_confirm(self):
        """Create a confirmed top-up record."""
        self.ensure_one()
        topup = self.env["keykeep.topup"].create({
            "subscription_id": self.subscription_id.id,
            "date": self.date,
            "amount": self.amount,
            "method": self.method,
            "source": self.source,
            "payment_method_id": self.payment_method_id.id,
            "receipt_ref": self.receipt_ref,
            "note": self.note,
            "state": "confirmed",
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Top-ups",
            "res_model": "keykeep.topup",
            "res_id": topup.id,
            "view_mode": "form",
            "view_id": self.env.ref("keykeep.view_keykeep_topup_form").id,
            "target": "current",
        }
