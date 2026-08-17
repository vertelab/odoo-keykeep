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
            "view_mode": "kanban,tree,form",
            "domain": [("partner_id", "=", self.id)],
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

    @api.depends(
        "subscription_ids",
        "subscription_ids.credential_ids",
        "subscription_ids.invoice_ids",
        "subscription_ids.topup_ids",
    )
    def _compute_aggregates(self):
        for partner in self:
            partner.credential_count = len(
                partner.subscription_ids.mapped("credential_ids"))
            partner.invoice_count = len(
                partner.subscription_ids.mapped("invoice_ids"))
            partner.topup_count = len(
                partner.subscription_ids.mapped("topup_ids"))

    def action_view_credentials(self):
        self.ensure_one()
        credentials = self.subscription_ids.mapped("credential_ids")
        return {
            "type": "ir.actions.act_window",
            "name": "API Keys",
            "res_model": "keykeep.credential",
            "view_mode": "tree,form",
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
            "view_mode": "tree,form",
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
