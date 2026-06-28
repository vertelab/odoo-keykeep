# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class KeykeepCredentialReveal(models.TransientModel):
    """Simple wizard to display decrypted credential values."""

    _name = "keykeep.credential.reveal"
    _description = "Reveal Credential"

    credential_id = fields.Many2one(
        comodel_name="keykeep.credential",
        string="Credential",
        readonly=True,
        required=True,
    )
    credential_name = fields.Char(related="credential_id.name", readonly=True)
    credential_type = fields.Selection(
        related="credential_id.credential_type", readonly=True
    )
    username = fields.Char(related="credential_id.username", readonly=True)
    subscription = fields.Char(
        related="credential_id.subscription_id.name", readonly=True
    )
    decrypted_value = fields.Text(
        string="Decrypted Value",
        compute="_compute_decrypted",
        readonly=True,
    )

    def _compute_decrypted(self):
        for wiz in self:
            cred = wiz.credential_id
            if not cred:
                wiz.decrypted_value = ""
                continue
            ct = cred.credential_type
            if ct in ("api_key", "token", "other"):
                wiz.decrypted_value = cred._read_encrypted("key_value") or ""
            elif ct == "login":
                pw = cred._read_encrypted("password") or ""
                uname = cred.username or ""
                wiz.decrypted_value = f"Username: {uname}\nPassword: {pw}"
            else:
                wiz.decrypted_value = ""
