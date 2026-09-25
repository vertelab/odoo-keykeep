# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""keykeep.psono.user — 1:1 vault identity linked to res.users.

Zero-knowledge: only client-generated key material is stored. The master
password and unwrapped keys NEVER exist server-side. The authkey is a bcrypt
hash of the client-derived authkey (verified at login, never stored plain).
"""

from odoo import fields, models

DEFAULT_HASHING_ALGORITHM = "scrypt"
DEFAULT_HASHING_PARAMETERS = {"u": 14, "r": 8, "p": 1, "l": 64}


class KeykeepPsonoUser(models.Model):
    _name = "keykeep.psono.user"
    _description = "Psono Vault User"
    _order = "username"

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Odoo User",
        required=True,
        ondelete="cascade",
        index=True,
    )
    username = fields.Char(
        string="Username",
        required=True,
        index=True,
        help="Lowercased email address, matching the linked res.users login.",
    )
    email = fields.Char(string="Email")
    email_bcrypt = fields.Char(string="Email (bcrypt)")
    authkey = fields.Char(
        string="Authkey (bcrypt hash)",
        help="bcrypt hash of the client-derived authkey. Never plaintext.",
    )
    # Client-generated key material — wrapped with keys derived from the
    # user's master password in the browser. The server only stores them.
    public_key = fields.Char(string="Public Key (hex)")
    private_key = fields.Char(string="Private Key (wrapped)")
    private_key_nonce = fields.Char(string="Private Key Nonce")
    secret_key = fields.Char(string="Secret Key (wrapped)")
    secret_key_nonce = fields.Char(string="Secret Key Nonce")
    user_sauce = fields.Char(string="User Sauce")
    hashing_algorithm = fields.Char(
        string="Hashing Algorithm", default=DEFAULT_HASHING_ALGORITHM
    )
    hashing_parameters = fields.Json(
        string="Hashing Parameters", default=dict(DEFAULT_HASHING_PARAMETERS)
    )
    authentication = fields.Char(string="Authentication", default="AUTHKEY")
    is_email_active = fields.Boolean(string="Email Verified", default=False)
    is_active = fields.Boolean(string="Active", default=True)
    language = fields.Char(string="Language", default="en")
    require_password_change = fields.Boolean(string="Require Password Change", default=False)
    activation_code = fields.Char(string="Activation Code (hash)")
    activation_code_expire = fields.Datetime(string="Activation Code Expiry")

    _sql_constraints = [
        ("username_uniq", "unique (username)", "A vault user with this username already exists."),
        ("user_uniq", "unique (user_id)", "An Odoo user can have only one vault."),
    ]

    # ── helpers ────────────────────────────────────────────────────

    def _log(self, action, detail=None):
        """Record a content-agnostic access log entry (never payload)."""
        return self.env["keykeep.psono.access.log"].create(
            {
                "user_id": self.user_id.id,
                "action": action,
                "detail": detail,
            }
        )
