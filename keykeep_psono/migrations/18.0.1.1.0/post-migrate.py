# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Post-migration 18.0.1.1.0 — align vault state with the Odoo user.

Design D4 / D11: `keykeep.psono.user.language` was never linked to
`res.users.lang`, and `is_active` was never linked to `res.users.active`.
Both are now synced on write; this migration brings existing rows in line so
no vault is left disagreeing with its user.

Idempotent — safe to re-run.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Import lazily: the module may not be fully loaded when this runs.
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["keykeep.psono.user"].search([])
    if not users:
        return

    from odoo.addons.keykeep_psono.util import odoo_lang_to_psono

    updated = 0
    for vault in users:
        odoo_user = vault.user_id
        if not odoo_user:
            continue
        vals = {}
        wanted_lang = odoo_lang_to_psono(odoo_user.lang)
        if vault.language != wanted_lang:
            vals["language"] = wanted_lang
        if vault.is_active != odoo_user.active:
            vals["is_active"] = odoo_user.active
        if vals:
            vault.write(vals)
            updated += 1

    _logger.info(
        "keykeep_psono 18.0.1.1.0: aligned %d/%d vault(s) with their Odoo user",
        updated,
        len(users),
    )
