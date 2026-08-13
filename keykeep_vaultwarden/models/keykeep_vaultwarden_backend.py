# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Keykeep Vaultwarden bridge.

Autonomt krav: keykeep fungerar utan denna modul installerad/konfigurerad.
Bryggan är ADDITIV — när vault-URL + token är konfigurerade lagras/läses
keykeep-credential-värden som Bitwarden-items i valvet i stället för i
keykeep-kolumnerna. Anropare (reveal-wizard, bifrost_keykeep) märker inget.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.config import config

_logger = logging.getLogger(__name__)


class KeykeepVaultwardenBackend(models.Model):
    _name = "keykeep.vaultwarden.backend"
    _description = "Keykeep Vaultwarden Backend"

    name = fields.Char(default="Vaultwarden", required=True)
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)
    vault_url = fields.Char(string="Vault URL")
    token_ref = fields.Char(
        string="Token reference (env key)", default="keykeep_vaultwarden_token"
    )
    collection_name = fields.Char(
        string="Collection",
        help="Collection in the vault where keykeep items are stored.",
        default="Keykeep",
    )

    @api.constrains("vault_url")
    def _check_vault_url(self):
        for rec in self:
            if rec.vault_url and not rec.vault_url.startswith("https://"):
                raise UserError(_("Vault URL must start with https://"))

    def _get_token(self):
        self.ensure_one()
        return config.get(self.token_ref or "keykeep_vaultwarden_token", False)

    def _is_configured(self):
        self.ensure_one()
        return bool(self.vault_url and self._get_token())

    @api.model
    def _get_active(self):
        return self.search([("active", "=", True)], limit=1) or self.search([], limit=1)

    # ── Item operations (org items, encrypted) ─────────────────────

    def store_item(self, credential, field_name, value):
        """Create/update a Bitwarden item holding the credential value."""
        self.ensure_one()
        if not self._is_configured():
            raise UserError(_("Vaultwarden bridge is not configured."))
        # TODO(spike): SDK encryption with org key + create/update cipher.
        # Endpoint: POST /api/ciphers with EncString fields (login type).
        raise UserError(
            _("Vaultwarden item write requires the bitwarden-sdk (spike pending).")
        )

    def read_item(self, credential, field_name, system=False):
        """Read+decrypt a credential value from the vault."""
        self.ensure_one()
        if not self._is_configured():
            raise UserError(_("Vaultwarden bridge is not configured."))
        # TODO(spike): SDK decrypt of the org item.
        raise UserError(
            _("Vaultwarden item read requires the bitwarden-sdk (spike pending).")
        )

    def delete_item(self, credential):
        self.ensure_one()
        # TODO(spike): DELETE /api/ciphers/{id} via org token.
        raise UserError(
            _("Vaultwarden item delete requires the bitwarden-sdk (spike pending).")
        )


class KeykeepCredential(models.Model):
    """Storage backend switch: internal (default) vs Vaultwarden (bridge)."""

    _inherit = "keykeep.credential"

    vault_item_id = fields.Char(string="Vault item id", readonly=True)

    def _vault_backend(self):
        backend = self.env["keykeep.vaultwarden.backend"]._get_active()
        return backend and backend._is_configured()

    def _backend(self):
        if self._vault_backend():
            return self.env["keykeep.vaultwarden.backend"]._get_active()
        return None

    def _store_encrypted(self, field_name, value):
        backend = self._backend()
        if backend:
            backend.store_item(self, field_name, value)
        else:
            return super()._store_encrypted(field_name, value)

    def _read_encrypted(self, field_name, system=False):
        backend = self._backend()
        if backend:
            value = backend.read_item(self, field_name, system=system)
            if system:
                self._log_access("system_read", fields_accessed=field_name)
            return value
        return super()._read_encrypted(field_name, system=system)

    def _delete_encrypted(self, field_name):
        backend = self._backend()
        if backend:
            backend.delete_item(self)
        else:
            return super()._delete_encrypted(field_name)
