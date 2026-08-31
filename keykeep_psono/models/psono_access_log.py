# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""keykeep.psono.access.log — content-agnostic audit trail.

Zero-knowledge: the server cannot log what was decrypted, only that an
event happened (register/login/logout/verify/activate/token_rejected/
import/export). `detail` carries metadata such as format + count for
import/export — NEVER payload content.
"""

from odoo import fields, models


class KeykeepPsonoAccessLog(models.Model):
    _name = "keykeep.psono.access.log"
    _description = "Psono Access Log"
    _order = "accessed_at desc"

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        index=True,
    )
    action = fields.Selection(
        selection=[
            ("register", "Register"),
            ("verify_email", "Verify Email"),
            ("activate_token", "Activate Token"),
            ("login", "Login"),
            ("login_failed", "Login Failed"),
            ("logout", "Logout"),
            ("token_rejected", "Token Rejected"),
            ("import", "Import"),
            ("export", "Export"),
        ],
        string="Action",
        required=True,
    )
    detail = fields.Char(
        string="Detail",
        help="Metadata (e.g. 'firefox_csv, 12 entries') — never secret content.",
    )
    ip_address = fields.Char(string="IP Address")
    accessed_at = fields.Datetime(
        string="Accessed At",
        required=True,
        default=fields.Datetime.now,
    )
