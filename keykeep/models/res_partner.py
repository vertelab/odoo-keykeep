# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
