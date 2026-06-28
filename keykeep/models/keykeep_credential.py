# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.config import config

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet

    FERNET_AVAILABLE = True
except ImportError:
    FERNET_AVAILABLE = False
    _logger.warning("cryptography not installed, credentials will not be encrypted")


class KeykeepCredential(models.Model):
    _name = "keykeep.credential"
    _description = "Keykeep Credential"
    _order = "credential_type, name"

    name = fields.Char(required=True, string="Label")
    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
        ondelete="cascade",
    )
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
    username = fields.Char(string="Username")

    # Encrypted fields — stored encrypted in ir.config_parameter (or data_encryption if available).
    # The DB column itself is only used as a cache/flag.
    password = fields.Char(string="Password")
    key_value = fields.Text(string="Key / Token Value")

    purpose = fields.Char(
        string="Purpose",
        help="Description of what this key is used for, e.g. 'Production CI/CD', 'Staging environment'.",
    )
    expiry_date = fields.Date(string="Expiry Date")
    renewal_reminder = fields.Boolean(default=True, string="Remind Before Expiry")
    notes = fields.Text(string="Notes")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="subscription_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "name_subscription_uniq",
            "unique (name, subscription_id)",
            "A credential with this name already exists for this subscription.",
        )
    ]

    # ── Encryption strategy detection ──

    def _has_data_encryption(self):
        """Return True if OCA data_encryption is installed and configured."""
        try:
            self.env["encrypted.data"]._retrieve_env()
            return True
        except Exception:
            return False

    def _get_fernet_cipher(self):
        """Get or create a Fernet cipher from the system parameter."""
        if not FERNET_AVAILABLE:
            return None
        key = self.env["ir.config_parameter"].sudo().get_param(
            "keykeep.encryption_key"
        )
        if not key:
            key = Fernet.generate_key().decode()
            self.env["ir.config_parameter"].sudo().set_param(
                "keykeep.encryption_key", key
            )
        return Fernet(key.encode())

    # ── Encryption key helpers ──

    def _encryption_key(self, field_name):
        self.ensure_one()
        return f"keykeep_credential_{self.id}_{field_name}"

    def _store_encrypted(self, field_name, value):
        self.ensure_one()
        if not value:
            return
        key = self._encryption_key(field_name)
        if self._has_data_encryption():
            self.env["encrypted.data"]._encrypted_store(key, value)
        else:
            cipher = self._get_fernet_cipher()
            if cipher:
                encrypted = cipher.encrypt(value.encode()).decode()
                self.env["ir.config_parameter"].sudo().set_param(key, encrypted)

    def _read_encrypted(self, field_name):
        self.ensure_one()
        key = self._encryption_key(field_name)
        if self._has_data_encryption():
            try:
                return self.env["encrypted.data"]._encrypted_get(key)
            except Exception:
                return None
        else:
            cipher = self._get_fernet_cipher()
            if cipher:
                encrypted = (
                    self.env["ir.config_parameter"].sudo().get_param(key)
                )
                if encrypted:
                    try:
                        return cipher.decrypt(encrypted.encode()).decode()
                    except Exception:
                        return None
            return None

    def _delete_encrypted(self, field_name):
        self.ensure_one()
        key = self._encryption_key(field_name)
        if self._has_data_encryption():
            env_name = self.env["encrypted.data"]._retrieve_env()
            self.env["encrypted.data"].search([
                ("name", "=", key),
                ("environment", "=", env_name),
            ]).unlink()
        else:
            self.env["ir.config_parameter"].sudo().set_param(key, False)

    # ── Lifecycle: encrypt on create, decrypt on read/search ──

    @api.model_create_multi
    def create(self, vals_list):
        """Create credential and encrypt sensitive fields."""
        # Extract secrets before creation, store them after
        secrets = []
        clean_vals = []
        for vals in vals_list:
            pw = vals.pop("password", None)
            kv = vals.pop("key_value", None)
            clean_vals.append(vals)
            secrets.append((pw, kv))
        records = super().create(clean_vals)
        for rec, (pw, kv) in zip(records, secrets):
            if pw:
                rec._store_encrypted("password", pw)
            if kv:
                rec._store_encrypted("key_value", kv)
        return records

    def write(self, vals):
        """Encrypt sensitive fields on write."""
        pw = vals.pop("password", None)
        kv = vals.pop("key_value", None)
        result = super().write(vals)
        for rec in self:
            if pw is not None:
                if pw:
                    rec._store_encrypted("password", pw)
                else:
                    rec._delete_encrypted("password")
            if kv is not None:
                if kv:
                    rec._store_encrypted("key_value", kv)
                else:
                    rec._delete_encrypted("key_value")
        return result

    def read(self, fields=None, load="_classic_read"):
        """Decrypt sensitive fields on read."""
        result = super().read(fields, load)
        if not fields or any(f in fields for f in ("password", "key_value")):
            for vals in result:
                rec_id = vals.get("id")
                if not rec_id:
                    continue
                rec = self.browse(rec_id)
                if not fields or "password" in fields:
                    vals["password"] = rec._read_encrypted("password") or ""
                if not fields or "key_value" in fields:
                    vals["key_value"] = rec._read_encrypted("key_value") or ""
        return result

    def unlink(self):
        """Clean up encrypted data on deletion."""
        for rec in self:
            for field_name in ("password", "key_value"):
                rec._delete_encrypted(field_name)
        return super().unlink()

    def copy(self, default=None):
        """Don't copy encrypted values — new record needs re-encryption."""
        default = dict(default or {})
        default.setdefault("password", False)
        default.setdefault("key_value", False)
        return super().copy(default)

    # ── UI Action ──

    def action_reveal_password(self):
        self.ensure_one()
        if not self.env.user.has_group("keykeep.group_admin"):
            raise UserError(_("Only Keykeep admins can reveal credentials."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "keykeep.credential.reveal",
            "name": _("Reveal: %s — %s") % (self.subscription_id.name, self.name),
            "view_mode": "form",
            "target": "new",
            "context": {"default_credential_id": self.id},
        }
