# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""res.users extension — Personal Vault tab (design D12).

Shows vault status (registered / email-verified) and actions to open the
vault and deep-link to psono-web import/export views. Never displays secret
material. Computed via sudo() because keykeep.psono.* models are restricted
to the system (zero-knowledge).
"""

from odoo import api, fields, models


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

    @api.depends("login")
    def _compute_psono_vault(self):
        PsonoUser = self.env["keykeep.psono.user"].sudo()
        for rec in self:
            psono = PsonoUser.search([("user_id", "=", rec.id)], limit=1)
            rec.psono_user_id = psono.id
            rec.psono_registered = bool(psono)
            rec.psono_verified = bool(psono and psono.is_email_active)

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
