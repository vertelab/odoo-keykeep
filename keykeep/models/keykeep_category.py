# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class KeykeepCategory(models.Model):
    _name = "keykeep.category"
    _description = "Keykeep Category"
    _order = "parent_id, name"
    _parent_store = True
    _parent_name = "parent_id"

    name = fields.Char(required=True, translate=True)
    parent_id = fields.Many2one(
        comodel_name="keykeep.category",
        string="Parent Category",
        index=True,
        ondelete="cascade",
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        comodel_name="keykeep.category",
        inverse_name="parent_id",
        string="Child Categories",
    )
    subscription_ids = fields.One2many(
        comodel_name="keykeep.subscription",
        inverse_name="category_id",
        string="Subscriptions",
    )
    subscription_count = fields.Integer(
        compute="_compute_subscription_count", string="Subscription Count"
    )
    expense_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default Expense Account",
        domain="[('account_type', '=', 'expense')]",
        help="Default expense account for journal entries created from subscriptions in this category.",
    )

    def _compute_subscription_count(self):
        for rec in self:
            rec.subscription_count = len(rec.subscription_ids)
