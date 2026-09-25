# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""keykeep.psono.token — psono session tokens.

The clear token key is returned to the client exactly once at login; the
database stores only its SHA-512 hash plus the session secret key used for
SecretBox request/response encryption and the Authorization-Validator.
"""

import hashlib
import secrets

from odoo import fields, models


class KeykeepPsonoToken(models.Model):
    _name = "keykeep.psono.token"
    _description = "Psono Session Token"
    _order = "create_date desc"

    key = fields.Char(string="Token Key (sha512)", index=True)
    user_id = fields.Many2one(
        comodel_name="keykeep.psono.user",
        string="Vault User",
        required=True,
        ondelete="cascade",
        index=True,
    )
    secret_key = fields.Char(
        string="Session Secret Key (hex)",
        required=True,
        help="SecretBox key for encrypted request/response bodies.",
    )
    session_key = fields.Char(string="Session Key")
    user_validator = fields.Char(string="User Validator")
    device_fingerprint = fields.Char(string="Device Fingerprint")
    device_description = fields.Char(string="Device Description")
    client_date = fields.Datetime(string="Client Date")
    valid_till = fields.Datetime(string="Valid Until", required=True)
    active = fields.Boolean(string="Active", default=False)
    create_date = fields.Datetime(string="Created", readonly=True, default=fields.Datetime.now)
    write_date = fields.Datetime(string="Last Updated", readonly=True)

    _sql_constraints = [
        ("key_uniq", "unique (key)", "A token with this key already exists."),
    ]

    # ── helpers ────────────────────────────────────────────────────

    @staticmethod
    def hash_key(clear_key):
        return hashlib.sha512(clear_key.encode()).hexdigest()

    @staticmethod
    def generate_clear_key():
        return secrets.token_hex(32)

    def is_expired(self):
        from odoo import fields as f

        now = f.Datetime.now()
        return bool(self.valid_till) and self.valid_till < now

    def revoke(self):
        self.sudo().unlink()
