# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""res.users extension — Personal Vault tab (design D5/D9/D11).

Shows vault status (state, registered, email-verified, recovery readiness)
and actions to open the vault and deep-link to psono-web import/export views.
Never displays secret material. Computed via sudo() because keykeep.psono.*
models are restricted to the system (zero-knowledge).
"""

from odoo import api, fields, models

VAULT_STATES = [
    ("none", "Not Set Up"),
    ("pending", "Pending Verification"),
    ("ready", "Ready"),
    ("active", "Active"),
]


class ResUsers(models.Model):
    _inherit = "res.users"

    psono_user_id = fields.Many2one(
        comodel_name="keykeep.psono.user",
        string="Personal Vault",
        compute="_compute_psono_vault",
    )
    psono_registered = fields.Boolean(
        string="Vault Registered", compute="_compute_psono_vault"
    )
    psono_verified = fields.Boolean(
        string="Vault Email Verified", compute="_compute_psono_vault"
    )
    psono_vault_state = fields.Selection(
        selection=VAULT_STATES,
        string="Vault State",
        compute="_compute_psono_vault",
        help="Lifecycle state of the vault: not set up, pending verification, "
             "ready but unused, or in active use.",
    )
    psono_recovery_registered = fields.Boolean(
        string="Recovery Registered",
        compute="_compute_psono_vault",
        help="True when recovery material is registered. The recovery code "
             "itself is never stored and can never be displayed.",
    )
    psono_recovery_created_at = fields.Datetime(
        string="Recovery Registered At",
        compute="_compute_psono_vault",
    )

    @api.depends("login", "active")
    def _compute_psono_vault(self):
        PsonoUser = self.env["keykeep.psono.user"].sudo()
        Token = self.env["keykeep.psono.token"].sudo()
        Secret = self.env["keykeep.psono.secret"].sudo()
        for rec in self:
            psono = PsonoUser.search([("user_id", "=", rec.id)], limit=1)
            rec.psono_user_id = psono.id
            rec.psono_registered = bool(psono)
            rec.psono_verified = bool(psono and psono.is_email_active)
            rec.psono_recovery_registered = bool(psono and psono.has_recovery())
            rec.psono_recovery_created_at = psono.recovery_created_at if psono else False
            rec.psono_vault_state = self._compute_vault_state(psono, Token, Secret)

    def _compute_vault_state(self, psono, Token, Secret):
        """Derive the lifecycle state (design D5).

        none ──register──► pending ──verify──► ready ──used──► active

        `active` means the vault has actually been used: at least one secret
        stored, or at least one session token ever issued.

        NOTE: keykeep.psono.token.active is an Odoo `active` field, so the
        default active_test would hide tokens that were issued but not yet
        activated. "Ever issued" must count them, hence active_test=False.
        """
        if not psono:
            return "none"
        if not psono.is_email_active:
            return "pending"
        used = bool(
            Secret.search_count([("user_id", "=", psono.id)], limit=1)
            or Token.with_context(active_test=False).search_count(
                [("user_id", "=", psono.id)], limit=1
            )
        )
        return "active" if used else "ready"

    def action_open_personal_vault(self):
        """Open psono-web (same origin, gated by the Odoo session)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/keykeep/psono/web/",
            "target": "self",
        }

    def action_open_vault_import(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/keykeep/psono/web/index.html#/other/import",
            "target": "self",
        }

    def action_open_vault_export(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/keykeep/psono/web/index.html#/other/export",
            "target": "self",
        }

    # ── lifecycle sync (design D11) ───────────────────────────────

    def write(self, vals):
        """Mirror `active` onto the linked vault (design D11).

        Deactivating an Odoo user must suspend vault access without
        destroying data. `login()` already rejects a vault with
        is_active=False, so this is the missing link.
        """
        res = super().write(vals)
        if "active" in vals:
            PsonoUser = self.env["keykeep.psono.user"].sudo()
            for rec in self:
                vault = PsonoUser.search([("user_id", "=", rec.id)], limit=1)
                if not vault or vault.is_active == rec.active:
                    continue
                vault.write({"is_active": rec.active})
                vault._log(
                    "vault_reactivated" if rec.active else "vault_suspended",
                    "res.users.active=%s" % rec.active,
                )
        return res
