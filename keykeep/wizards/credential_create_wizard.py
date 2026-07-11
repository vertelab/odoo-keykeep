# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import secrets
import string

from odoo import fields, models


class KeykeepCredentialCreateWizard(models.TransientModel):
    _name = "keykeep.credential.create.wizard"
    _description = "Create Credential Wizard"

    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
    )
    name = fields.Char(string="Label", required=True)
    credential_type = fields.Selection(
        selection=[
            ("login", "Login"),
            ("api_key", "API Key"),
            ("token", "Token"),
            ("certificate", "Certificate"),
            ("other", "Other"),
        ],
        required=True,
        default="api_key",
    )
    environment = fields.Selection(
        selection=[
            ("production", "Production"),
            ("staging", "Staging"),
            ("development", "Development"),
            ("testing", "Testing"),
        ],
        required=True,
        default="production",
    )
    username = fields.Char(string="Username")
    password = fields.Char(string="Password")
    key_value = fields.Text(string="Key / Token Value")
    purpose = fields.Char(string="Purpose")
    expiry_date = fields.Date(string="Expiry Date")
    renewal_reminder = fields.Boolean(default=True, string="Remind Before Expiry")
    notes = fields.Text(string="Notes")

    def action_generate_password(self):
        """Generate a strong random password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        self.password = "".join(secrets.choice(alphabet) for _ in range(20))

    def action_create(self):
        """Create the credential and close the wizard."""
        self.ensure_one()
        vals = {
            "subscription_id": self.subscription_id.id,
            "name": self.name,
            "credential_type": self.credential_type,
            "environment": self.environment,
            "username": self.username,
            "purpose": self.purpose,
            "expiry_date": self.expiry_date,
            "renewal_reminder": self.renewal_reminder,
            "notes": self.notes,
        }
        if self.password:
            vals["password"] = self.password
        if self.key_value:
            vals["key_value"] = self.key_value
        credential = self.env["keykeep.credential"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "keykeep.credential",
            "res_id": credential.id,
            "view_mode": "form",
            "name": credential.name,
            "target": "current",
        }
