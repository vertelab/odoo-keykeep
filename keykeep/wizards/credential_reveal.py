# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class KeykeepCredentialReveal(models.TransientModel):
    """Wizard to display decrypted credential values with audit context."""

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
    environment = fields.Selection(
        related="credential_id.environment", readonly=True
    )
    username = fields.Char(related="credential_id.username", readonly=True)
    # Plaintext values for display + copy (computed from decrypted value)
    email = fields.Char(string="E-mail", compute="_compute_plaintext", readonly=True)
    password = fields.Char(string="Password", compute="_compute_plaintext", readonly=True)
    api_key = fields.Text(string="API Key / Token", compute="_compute_plaintext", readonly=True)
    subscription = fields.Char(
        related="credential_id.subscription_id.name", readonly=True
    )
    decrypted_value = fields.Text(
        string="Decrypted Value",
        compute="_compute_decrypted",
        readonly=True,
    )
    # Audit info
    audit_user = fields.Char(
        string="Logged As",
        compute="_compute_audit",
        readonly=True,
    )
    audit_time = fields.Char(
        string="Accessed At",
        compute="_compute_audit",
        readonly=True,
    )
    last_accessed_by = fields.Char(
        string="Last Accessed By",
        compute="_compute_audit",
        readonly=True,
    )
    last_accessed_at = fields.Char(
        string="Last Accessed At",
        compute="_compute_audit",
        readonly=True,
    )
    recent_access = fields.Text(
        string="Recent Access",
        compute="_compute_recent",
        readonly=True,
    )
    reveal_timeout = fields.Integer(
        string="Auto-Close (seconds)",
        compute="_compute_timeout",
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

    def _compute_plaintext(self):
        """Split the decrypted value into separate plaintext fields for
        display + copy buttons."""
        for wiz in self:
            cred = wiz.credential_id
            wiz.email = cred.username or ""
            wiz.password = ""
            wiz.api_key = ""
            if not cred:
                continue
            ct = cred.credential_type
            if ct in ("api_key", "token", "other"):
                wiz.api_key = cred._read_encrypted("key_value") or ""
            elif ct == "login":
                wiz.password = cred._read_encrypted("password") or ""

    def _compute_audit(self):
        for wiz in self:
            wiz.audit_user = wiz.env.user.name
            wiz.audit_time = fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cred = wiz.credential_id
            if cred and cred.last_accessed_at:
                last = cred.access_log_ids.filtered(
                    lambda l: l.action in ("reveal", "copy") and l.id != cred.access_log_ids[0].id
                )
                if last:
                    wiz.last_accessed_by = last[0].user_id.name
                    wiz.last_accessed_at = last[0].accessed_at.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    wiz.last_accessed_by = "-"
                    wiz.last_accessed_at = "-"
            else:
                wiz.last_accessed_by = "Never"
                wiz.last_accessed_at = "Never"

    def _compute_recent(self):
        for wiz in self:
            cred = wiz.credential_id
            if cred:
                logs = cred.access_log_ids[:3]
                lines = []
                for l in logs:
                    lines.append(
                        f"{l.accessed_at.strftime('%Y-%m-%d %H:%M')} | {l.user_id.name} | {l.action}"
                    )
                wiz.recent_access = "\n".join(lines) if lines else "No previous access"
            else:
                wiz.recent_access = ""

    def _compute_timeout(self):
        for wiz in self:
            timeout = wiz.env["ir.config_parameter"].sudo().get_param(
                "keykeep.reveal_timeout_seconds", "60"
            )
            wiz.reveal_timeout = int(timeout)
