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
    environment = fields.Selection(
        selection=[
            ("production", "Production"),
            ("staging", "Staging"),
            ("development", "Development"),
            ("testing", "Testing"),
        ],
        required=True,
        default="production",
        string="Environment",
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

    # ── Versioning & Health ──
    version_ids = fields.One2many(
        comodel_name="keykeep.credential.version",
        inverse_name="credential_id",
        string="Version History",
    )
    version_count = fields.Integer(
        compute="_compute_version_count",
        string="Versions",
    )
    latest_version = fields.Integer(
        compute="_compute_version_info",
        string="Latest Version",
    )
    rotation_age = fields.Integer(
        compute="_compute_rotation_age",
        string="Days Since Rotation",
        help="Number of days since this credential was last updated (rotated).",
    )

    # ── Audit ──
    access_log_ids = fields.One2many(
        comodel_name="keykeep.credential.access.log",
        inverse_name="credential_id",
        string="Access Log",
    )
    last_accessed_at = fields.Datetime(
        compute="_compute_last_accessed",
        string="Last Accessed",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="subscription_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "name_subscription_env_uniq",
            "unique (name, subscription_id, environment)",
            "A credential with this name already exists for this subscription and environment.",
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

    @api.depends("version_ids")
    def _compute_version_count(self):
        for rec in self:
            rec.version_count = len(rec.version_ids)

    @api.depends("version_ids")
    def _compute_version_info(self):
        for rec in self:
            rec.latest_version = max(rec.version_ids.mapped("version_number") or [0])

    @api.depends("write_date")
    def _compute_rotation_age(self):
        from datetime import date
        today = date.today()
        for rec in self:
            if rec.write_date:
                rec.rotation_age = (today - rec.write_date.date()).days
            else:
                rec.rotation_age = 0

    @api.depends("access_log_ids", "access_log_ids.accessed_at")
    def _compute_last_accessed(self):
        for rec in self:
            logs = rec.access_log_ids.filtered(lambda l: l.action in ("reveal", "reveal_version", "copy"))
            if logs:
                rec.last_accessed_at = logs[0].accessed_at
            else:
                rec.last_accessed_at = False

    def _encrypt_for_version(self, value):
        """Encrypt a value using Fernet for storage in a version record."""
        if not value:
            return None
        cipher = self._get_fernet_cipher()
        if cipher:
            return cipher.encrypt(value.encode()).decode()
        return value

    def _create_version(self, changed_fields=None):
        """Create a version snapshot of the current credential state."""
        self.ensure_one()
        next_version = self.latest_version + 1
        # Encrypt current values for the snapshot
        pw = self._read_encrypted("password")
        kv = self._read_encrypted("key_value")
        return self.env["keykeep.credential.version"].create({
            "credential_id": self.id,
            "version_number": next_version,
            "username": self.username,
            "password": self._encrypt_for_version(pw) if pw else None,
            "key_value": self._encrypt_for_version(kv) if kv else None,
            "changed_by": self.env.uid,
            "changed_at": fields.Datetime.now(),
            "change_note": ", ".join(changed_fields) if changed_fields else None,
        })

    def _log_access(self, action, fields_accessed=None):
        """Create an access log entry. Must succeed or raise."""
        self.ensure_one()
        # Get client IP from request if available
        ip_address = None
        try:
            if hasattr(self.env, "request") and self.env.request:
                ip_address = self.env.request.httprequest.remote_addr
        except Exception:
            pass
        return self.env["keykeep.credential.access.log"].create({
            "credential_id": self.id,
            "user_id": self.env.uid,
            "action": action,
            "fields_accessed": fields_accessed,
            "ip_address": ip_address,
            "accessed_at": fields.Datetime.now(),
        })

    # ── Lifecycle overrides ──

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
            # Create initial version
            if pw or kv:
                rec._create_version()
        return records

    def write(self, vals):
        """Encrypt sensitive fields on write and create version."""
        pw = vals.pop("password", None)
        kv = vals.pop("key_value", None)
        uname = vals.pop("username", None)
        result = super().write(vals)
        # Track which fields changed for versioning
        changed_fields = []
        for rec in self:
            if pw is not None:
                if pw:
                    rec._store_encrypted("password", pw)
                else:
                    rec._delete_encrypted("password")
                changed_fields.append("password")
            if kv is not None:
                if kv:
                    rec._store_encrypted("key_value", kv)
                else:
                    rec._delete_encrypted("key_value")
                changed_fields.append("key_value")
            if uname is not None:
                rec.sudo().write({"username": uname})
                changed_fields.append("username")
            # Create version if secret fields changed
            if changed_fields:
                rec._create_version(changed_fields)
                rec._log_access("rotate", fields_accessed=("both" if "password" in changed_fields and "key_value" in changed_fields else ("password" if "password" in changed_fields else "key_value")))
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

    # ── UI Actions ──

    def action_reveal_password(self):
        self.ensure_one()
        if not self.env.user.has_group("keykeep.group_devops") and not self.env.user.has_group("keykeep.group_admin"):
            raise UserError(_("Only Keykeep admins and DevOps can reveal credentials."))
        # Determine which fields to reveal
        pw = self._read_encrypted("password")
        kv = self._read_encrypted("key_value")
        if pw and kv:
            fields_acc = "both"
        elif pw:
            fields_acc = "password"
        else:
            fields_acc = "key_value"
        # Log access BEFORE showing the credential
        self._log_access("reveal", fields_accessed=fields_acc)
        return {
            "type": "ir.actions.act_window",
            "res_model": "keykeep.credential.reveal",
            "name": _("Reveal: %s — %s") % (self.subscription_id.name, self.name),
            "view_mode": "form",
            "target": "new",
            "context": {"default_credential_id": self.id},
        }

    def action_copy_credential(self):
        self.ensure_one()
        if not self.env.user.has_group("keykeep.group_devops") and not self.env.user.has_group("keykeep.group_admin"):
            raise UserError(_("Only Keykeep admins and DevOps can copy credentials."))
        # Decrypt and determine fields
        pw = self._read_encrypted("password")
        kv = self._read_encrypted("key_value")
        if pw and kv:
            fields_acc = "both"
        elif pw:
            fields_acc = "password"
        else:
            fields_acc = "key_value"
        # Log copy access
        self._log_access("copy", fields_accessed=fields_acc)
        # Return the value(s) to copy — handled by JS
        return {
            "type": "ir.actions.client",
            "tag": "keykeep_copy_credential",
            "params": {
                "credential_id": self.id,
                "password": pw or "",
                "key_value": kv or "",
            },
        }

    def _reencrypt_all_versions(self):
        """Re-encrypt all version records with current Fernet key.
        Used after key rotation. Not called automatically."""
        self.ensure_one()
        cipher = self._get_fernet_cipher()
        if not cipher:
            _logger.warning("Cannot re-encrypt versions: no Fernet cipher available")
            return
        for version in self.version_ids:
            # Decrypt old values with old key (the one stored in version record)
            pw = version._decrypt_archived(self, version.password)
            kv = version._decrypt_archived(self, version.key_value)
            # Re-encrypt with current key
            if pw:
                version.password = self._encrypt_for_version(pw)
            if kv:
                version.key_value = self._encrypt_for_version(kv)
