# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    subscription_ids = fields.One2many(
        comodel_name="keykeep.subscription",
        inverse_name="partner_id",
        string="SaaS Subscriptions",
    )
    subscription_count = fields.Integer(compute="_compute_subscription_count")

    def _compute_subscription_count(self):
        for partner in self:
            partner.subscription_count = len(partner.subscription_ids)

    def action_view_subscriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "SaaS Subscriptions",
            "res_model": "keykeep.subscription",
            "view_mode": "kanban,list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    is_keykeep_partner = fields.Boolean(
        string="KeyKeep",
        help="Partner managed in KeyKeep (supplier with subscriptions/credentials).",
    )

    # === Smart-button aggregates (across all the partner's subscriptions) ===

    credential_count = fields.Integer(
        string="API Keys", compute="_compute_aggregates")
    invoice_count = fields.Integer(
        string="Invoices", compute="_compute_aggregates")
    topup_count = fields.Integer(
        string="Top-ups", compute="_compute_aggregates")
    forecast_count = fields.Integer(
        string="Forecast", compute="_compute_aggregates")
    monthly_forecast_amount = fields.Monetary(
        string="Monthly Forecast",
        currency_field="company_currency_id",
        compute="_compute_aggregates",
        help="Sum of the subscriptions' monthly forecast in the company currency.",
    )
    company_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Company Currency",
        related="company_id.currency_id",
    )
    partner_semaphore = fields.Selection(
        selection=[
            ("green", "Green"),
            ("yellow", "Yellow"),
            ("red", "Red"),
        ],
        string="Keykeep Semaphore",
        compute="_compute_partner_semaphore",
        help="Worst renewal_semaphore across the partner's subscriptions.",
    )

    @api.depends("subscription_ids", "subscription_ids.renewal_semaphore")
    def _compute_partner_semaphore(self):
        order = {"green": 0, "yellow": 1, "red": 2}
        for partner in self:
            colours = partner.subscription_ids.mapped("renewal_semaphore")
            if not colours:
                partner.partner_semaphore = False
            else:
                partner.partner_semaphore = max(
                    colours, key=lambda c: order.get(c, 0))

    @api.depends(
        "subscription_ids",
        "subscription_ids.credential_ids",
        "subscription_ids.invoice_ids",
        "subscription_ids.topup_ids",
        "subscription_ids.cost_forecast_ids",
        "subscription_ids.monthly_forecast_amount",
        "company_id",
    )
    def _compute_aggregates(self):
        for partner in self:
            subs = partner.subscription_ids
            partner.credential_count = len(subs.mapped("credential_ids"))
            partner.invoice_count = len(subs.mapped("invoice_ids"))
            partner.topup_count = len(subs.mapped("topup_ids"))
            partner.forecast_count = sum(subs.mapped("forecast_count"))
            partner.monthly_forecast_amount = sum(
                subs.mapped("monthly_forecast_amount"))

    def action_view_credentials(self):
        self.ensure_one()
        credentials = self.subscription_ids.mapped("credential_ids")
        return {
            "type": "ir.actions.act_window",
            "name": "API Keys",
            "res_model": "keykeep.credential",
            "view_mode": "list,form",
            "domain": [("id", "in", credentials.ids)],
            "context": {"default_subscription_id": self.subscription_ids[:1].id},
        }

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.subscription_ids.mapped("invoice_ids")
        return {
            "type": "ir.actions.act_window",
            "name": "Invoices",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
            "context": {"create": False},
        }

    def action_view_topups(self):
        self.ensure_one()
        topups = self.subscription_ids.mapped("topup_ids")
        return {
            "type": "ir.actions.act_window",
            "name": "Top-ups",
            "res_model": "keykeep.topup",
            "view_mode": "list,form",
            "domain": [("id", "in", topups.ids)],
            "context": {"default_subscription_id": self.subscription_ids[:1].id},
        }

    def action_add_topup(self):
        self.ensure_one()
        subs = self.subscription_ids
        ctx = {}
        # Only default the subscription when unambiguous; otherwise let the
        # user pick in the wizard (required field).
        if len(subs) == 1:
            ctx["default_subscription_id"] = subs.id
        return {
            "type": "ir.actions.act_window",
            "name": "Record Top-up",
            "res_model": "keykeep.topup.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }
