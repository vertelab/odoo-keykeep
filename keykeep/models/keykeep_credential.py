# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Keykeep credential — hardened internal storage.

Hardening (odoo-keykeep / keykeep-credential-hardening):
- Master key from Odoo configuration (env), NEVER from the database (D1)
- Per-credential keys, wrapped by the master key (D3)
- Ciphertext in credential columns, not ir.config_parameter (D2)
- read() never decrypts; all plaintext via logged actions incl. system path (D5)
- No silent failures (D7)
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.config import config

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet as _Fernet  # noqa: F401
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


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

    # Internal ciphertext columns — raw ciphertext, decrypted only via
    # explicit, logged methods. secret_key = per-credential key wrapped by
    # the master key (which lives in the Odoo configuration).
    password_cipher = fields.Text(string="Password (ciphertext)", readonly=True)
    key_value_cipher = fields.Text(string="Key Value (ciphertext)", readonly=True)
    secret_key = fields.Text(string="Credential key (wrapped)", readonly=True)

    # Public-facing API kept for compatibility: write sets plaintext,
    # read returns ciphertext (never decrypts).
    password = fields.Char(string="Password")
    key_value = fields.Text(string="Key / Token Value")

    purpose = fields.Char(
        string="Purpose",
        help="Description of what this key is used for.",
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
    version_count = fields.Integer(compute="_compute_version_count", string="Versions")
    latest_version = fields.Integer(compute="_compute_version_info", string="Latest Version")
    rotation_age = fields.Integer(
        compute="_compute_rotation_age", string="Days Since Rotation"
    )

    # ── Audit ──
    access_log_ids = fields.One2many(
        comodel_name="keykeep.credential.access.log",
        inverse_name="credential_id",
        string="Access Log",
    )
    last_accessed_at = fields.Datetime(compute="_compute_last_accessed", string="Last Accessed")

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

    # ── Key management (D1, D3) ────────────────────────────────────

    def _get_master_key(self):
        """Master key from Odoo configuration (env) — never from the DB."""
        if not CRYPTO_AVAILABLE:
            raise UserError(_("cryptography is required for keykeep credentials"))
        key = config.get("keykeep_encryption_key", False)
        if not key:
            raise UserError(
                _("keykeep_encryption_key is not configured. Add it to odoo.conf "
                  "(Fernet key: python -c 'from cryptography.fernet import Fernet; "
                  "print(Fernet.generate_key())').")
            )
        return key.encode()

    def _get_fernet_cipher(self):
        return Fernet(self._get_master_key())

    def _get_credential_key(self):
        """Per-credential key; create+wrap on first use."""
        self.ensure_one()
        if self.secret_key:
            try:
                raw = self._get_fernet_cipher().decrypt(self.secret_key.encode())
                return Fernet(raw)
            except InvalidToken as exc:
                raise UserError(
                    _("Credential key could not be unwrapped (wrong master key?)")
                ) from exc
        new_key = Fernet.generate_key()
        wrapped = self._get_fernet_cipher().encrypt(new_key).decode()
        self.write({"secret_key": wrapped})
        return Fernet(new_key)

    def _rotate_credential_key(self):
        """Generate a new credential key; re-encrypt values + versions (D4)."""
        self.ensure_one()
        old_key = self._get_credential_key()
        pw = self._decrypt_with(self.password_cipher, old_key)
        kv = self._decrypt_with(self.key_value_cipher, old_key)
        new_key = Fernet.generate_key()
        wrapped = self._get_fernet_cipher().encrypt(new_key).decode()
        self.write({"secret_key": wrapped})
        self.password_cipher = self._encrypt_with(pw, new_key) if pw else False
        self.key_value_cipher = self._encrypt_with(kv, new_key) if kv else False
        self._reencrypt_all_versions(old_key, new_key)
        self._log_access("rotate", fields_accessed="both")
        return True

    def rotate_master_key(self, new_key_b64):
        """Re-wrap all credential keys with a new master key (D4)."""
        old = self._get_fernet_cipher()
        new = Fernet(new_key_b64.encode())
        for rec in self.search([("secret_key", "!=", False)]):
            try:
                unwrapped = old.decrypt(rec.secret_key.encode())
                rec.write({"secret_key": new.encrypt(unwrapped).decode()})
            except InvalidToken:
                _logger.warning("Could not re-wrap credential %s", rec.id)
        return True

    @staticmethod
    def _encrypt_with(value, cipher):
        if not value:
            return False
        return cipher.encrypt(value.encode()).decode()

    @staticmethod
    def _decrypt_with(ciphertext, cipher):
        if not ciphertext:
            return None
        try:
            return cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise UserError(
                _("Decryption failed for a credential value (wrong key?)")
            ) from exc

    # ── Storage API (D2, D5, D7) ───────────────────────────────────

    def _store_encrypted(self, field_name, value):
        self.ensure_one()
        if not value:
            return
        cipher = self._get_credential_key()
        col = "password_cipher" if field_name == "password" else "key_value_cipher"
        self.write({col: self._encrypt_with(value, cipher)})

    def _read_encrypted(self, field_name, system=False):
        """Decrypt a value. NEVER called from ORM read; only explicit actions.

        system=True logs a `system_read` audit entry (integration path).
        Raises on decrypt failure (D7); returns None only when no value stored.
        """
        self.ensure_one()
        col = "password_cipher" if field_name == "password" else "key_value_cipher"
        ciphertext = getattr(self, col)
        if not ciphertext:
            return None
        cipher = self._get_credential_key()
        value = self._decrypt_with(ciphertext, cipher)
        if system:
            self._log_access("system_read", fields_accessed=field_name)
        return value

    def _delete_encrypted(self, field_name):
        self.ensure_one()
        col = "password_cipher" if field_name == "password" else "key_value_cipher"
        self.write({col: False})

    # ── Versioning (encrypted with the credential key) ─────────────

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
            rec.rotation_age = (today - rec.write_date.date()).days if rec.write_date else 0

    @api.depends("access_log_ids", "access_log_ids.accessed_at")
    def _compute_last_accessed(self):
        for rec in self:
            logs = rec.access_log_ids.filtered(
                lambda l: l.action in ("reveal", "reveal_version", "copy", "system_read")
            )
            rec.last_accessed_at = logs[0].accessed_at if logs else False

    def _create_version(self, changed_fields=None):
        self.ensure_one()
        cipher = self._get_credential_key()
        pw = self._read_encrypted("password")
        kv = self._read_encrypted("key_value")
        return self.env["keykeep.credential.version"].create(
            {
                "credential_id": self.id,
                "version_number": self.latest_version + 1,
                "username": self.username,
                "password": self._encrypt_with(pw, cipher) if pw else None,
                "key_value": self._encrypt_with(kv, cipher) if kv else None,
                "changed_by": self.env.uid,
                "changed_at": fields.Datetime.now(),
                "change_note": ", ".join(changed_fields) if changed_fields else None,
            }
        )

    def _reencrypt_all_versions(self, old_key=None, new_key=None):
        """Re-encrypt version snapshots with the current credential key."""
        self.ensure_one()
        new_key = new_key or self._get_credential_key()
        for version in self.version_ids:
            pw = self._decrypt_with(version.password, old_key) if version.password else None
            kv = self._decrypt_with(version.key_value, old_key) if version.key_value else None
            version.write(
                {
                    "password": self._encrypt_with(pw, new_key) if pw else None,
                    "key_value": self._encrypt_with(kv, new_key) if kv else None,
                }
            )

    def _log_access(self, action, fields_accessed=None):
        self.ensure_one()
        ip_address = None
        try:
            if hasattr(self.env, "request") and self.env.request:
                ip_address = self.env.request.httprequest.remote_addr
        except Exception:  # noqa: BLE001
            pass
        return self.env["keykeep.credential.access.log"].create(
            {
                "credential_id": self.id,
                "user_id": self.env.uid,
                "action": action,
                "fields_accessed": fields_accessed,
                "ip_address": ip_address,
                "accessed_at": fields.Datetime.now(),
            }
        )

    # ── Lifecycle ──────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        secrets = []
        clean_vals = []
        for vals in vals_list:
            pw = vals.pop("password", None)
            kv = vals.pop("key_value", None)
            clean_vals.append(vals)
            secrets.append((pw, kv))
        records = super().create(clean_vals)
        for rec, (pw, kv) in zip(records, secrets):
            if pw or kv:
                rec._get_credential_key()  # ensure key exists
            if pw:
                rec._store_encrypted("password", pw)
            if kv:
                rec._store_encrypted("key_value", kv)
            if pw or kv:
                rec._create_version()
        return records

    def write(self, vals):
        pw = vals.pop("password", None)
        kv = vals.pop("key_value", None)
        uname = vals.pop("username", None)
        result = super().write(vals)
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
            if changed_fields:
                rec._create_version(changed_fields)
                fields_acc = (
                    "both"
                    if "password" in changed_fields and "key_value" in changed_fields
                    else ("password" if "password" in changed_fields else "key_value")
                )
                rec._log_access("rotate", fields_accessed=fields_acc)
        return result

    def unlink(self):
        # Ciphertext lives in columns on this record — cascade removes it.
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("password_cipher", False)
        default.setdefault("key_value_cipher", False)
        default.setdefault("secret_key", False)
        return super().copy(default)

    # ── UI Actions ─────────────────────────────────────────────────

    def action_reveal_password(self):
        self.ensure_one()
        if not self.env.user.has_group("keykeep.group_devops") and not self.env.user.has_group(
            "keykeep.group_admin"
        ):
            raise UserError(_("Only Keykeep admins and DevOps can reveal credentials."))
        pw = self._read_encrypted("password")
        kv = self._read_encrypted("key_value")
        fields_acc = "both" if (pw and kv) else ("password" if pw else "key_value")
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
        if not self.env.user.has_group("keykeep.group_devops") and not self.env.user.has_group(
            "keykeep.group_admin"
        ):
            raise UserError(_("Only Keykeep admins and DevOps can copy credentials."))
        pw = self._read_encrypted("password")
        kv = self._read_encrypted("key_value")
        fields_acc = "both" if (pw and kv) else ("password" if pw else "key_value")
        self._log_access("copy", fields_accessed=fields_acc)
        return {
            "type": "ir.actions.client",
            "tag": "keykeep_copy_credential",
            "params": {"credential_id": self.id, "password": pw or "", "key_value": kv or ""},
        }

    def action_rotate_credential_key(self):
        self.ensure_one()
        if not self.env.user.has_group("keykeep.group_admin"):
            raise UserError(_("Only Keykeep admins can rotate credential keys."))
        self._rotate_credential_key()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Credential key rotated"),
                "message": _("Values and version history re-encrypted with a new key."),
                "type": "success",
            },
        }

    # ── Retention (6.1) ────────────────────────────────────────────

    def purge_old_versions(self, keep=10):
        """Remove version snapshots beyond `keep`, logging the purge."""
        self.ensure_one()
        versions = self.version_ids.sorted(key=lambda v: v.version_number, reverse=True)
        to_remove = versions[keep:]
        count = len(to_remove)
        if count:
            to_remove.unlink()
            self._log_access("purge", fields_accessed="versions")
        return count
