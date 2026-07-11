# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class KeykeepCredentialVersion(models.Model):
    _name = "keykeep.credential.version"
    _description = "Keykeep Credential Version"
    _order = "version_number desc"
    _rec_name = "version_number"

    credential_id = fields.Many2one(
        comodel_name="keykeep.credential",
        string="Credential",
        required=True,
        ondelete="cascade",
    )
    version_number = fields.Integer(
        string="Version",
        required=True,
    )
    username = fields.Char(string="Username (Snapshot)")
    password = fields.Text(string="Password (Encrypted)")
    key_value = fields.Text(string="Key Value (Encrypted)")
    changed_by = fields.Many2one(
        comodel_name="res.users",
        string="Changed By",
        default=lambda self: self.env.user,
    )
    changed_at = fields.Datetime(
        string="Changed At",
        default=lambda self: fields.Datetime.now(),
    )
    change_note = fields.Char(string="Change Note")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="credential_id.subscription_id.company_id",
        store=True,
    )

    def action_reveal_value(self):
        """Reveal the decrypted value of a historical version."""
        self.ensure_one()
        if not self.env.user.has_group("keykeep.group_devops") and not self.env.user.has_group("keykeep.group_admin"):
            from odoo.exceptions import UserError
            from odoo import _
            raise UserError(_("Only users with reveal permission can view historical version values."))

        # Decrypt values using credential's encryption methods
        cred = self.credential_id
        password = self._decrypt_archived(cred, self.password)
        key_value = self._decrypt_archived(cred, self.key_value)

        # Log the access
        cred._log_access("reveal_version", fields_accessed="both" if password and key_value else ("password" if password else "key_value"))

        return {
            "type": "ir.actions.act_window",
            "res_model": "keykeep.credential.version.reveal",
            "name": "Historical Version — %s (v%d)" % (cred.name, self.version_number),
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_credential_id": cred.id,
                "default_version_id": self.id,
                "default_password": password or "",
                "default_key_value": key_value or "",
            },
        }

    def _decrypt_archived(self, credential, encrypted_value):
        """Decrypt a version snapshot using credential's Fernet cipher."""
        if not encrypted_value:
            return None
        cipher = credential._get_fernet_cipher()
        if cipher:
            try:
                return cipher.decrypt(encrypted_value.encode()).decode()
            except Exception:
                return None
        return None
