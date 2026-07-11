# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class KeykeepCredentialAccessLog(models.Model):
    _name = "keykeep.credential.access.log"
    _description = "Keykeep Credential Access Log"
    _order = "accessed_at desc"

    credential_id = fields.Many2one(
        comodel_name="keykeep.credential",
        string="Credential",
        required=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        default=lambda self: self.env.user,
    )
    action = fields.Selection(
        selection=[
            ("reveal", "Reveal"),
            ("reveal_version", "Reveal Historical Version"),
            ("copy", "Copy"),
            ("rotate", "Rotate"),
            ("view_metadata", "View Metadata"),
        ],
        required=True,
        string="Action",
    )
    fields_accessed = fields.Selection(
        selection=[
            ("password", "Password"),
            ("key_value", "Key Value"),
            ("both", "Both"),
        ],
        string="Fields Accessed",
    )
    ip_address = fields.Char(
        string="IP Address",
        help="IP address of the user at the time of access.",
    )
    accessed_at = fields.Datetime(
        string="Accessed At",
        required=True,
        default=lambda self: fields.Datetime.now(),
    )
    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        related="credential_id.subscription_id",
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="credential_id.subscription_id.company_id",
        store=True,
    )
