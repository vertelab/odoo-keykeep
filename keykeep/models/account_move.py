# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    keykeep_subscription_ids = fields.Many2many(
        comodel_name="keykeep.subscription",
        relation="keykeep_subscription_account_move_rel",
        column1="move_id",
        column2="subscription_id",
        string="Keykeep Subscriptions",
        copy=False,
    )
