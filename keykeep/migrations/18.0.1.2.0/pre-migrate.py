# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Pre-migrate 18.0.1.1.0 → 18.0.1.2.0 — credential hardening.

Migrates credentials from the old storage (Fernet value in
ir.config_parameter, single master key) to the hardened storage:
- per-credential key wrapped by the env master key (secret_key)
- ciphertext in columns (password_cipher / key_value_cipher)

Idempotent: runs only for credentials without secret_key.

The master key MUST be present in the Odoo configuration
(keykeep_encryption_key). If missing, the migration raises with
instructions and the module upgrade aborts.
"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from odoo.tools.config import config

_logger = logging.getLogger(__name__)


def _old_key(cr):
    """The legacy master key (Fernet) from ir.config_parameter."""
    cr.execute(
        "SELECT value FROM ir_config_parameter WHERE key = 'keykeep.encryption_key'"
    )
    row = cr.fetchone()
    return row[0] if row else False


def _legacy_param(cr, name):
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (name,))
    row = cr.fetchone()
    return row[0] if row else False


def migrate(cr, version):
    if not version:
        return

    key_b64 = config.get("keykeep_encryption_key", False)
    if not key_b64:
        raise RuntimeError(
            "keykeep_encryption_key is missing from odoo.conf. Migration cannot "
            "run. Add: keykeep_encryption_key=<Fernet key> and retry."
        )
    master = Fernet(key_b64.encode())

    old_master_b64 = _old_key(cr)
    old_master = Fernet(old_master_b64.encode()) if old_master_b64 else None

    # Credentials that still need migration (no secret_key yet)
    cr.execute(
        "SELECT id, password_cipher, key_value_cipher FROM keykeep_credential "
        "WHERE secret_key IS NULL OR secret_key = ''"
    )
    rows = cr.fetchall()
    migrated = 0
    for cred_id, pw_cipher, kv_cipher in rows:
        # 1. Per-credential key, wrapped by the new env master key
        cred_key = Fernet.generate_key()
        wrapped = master.encrypt(cred_key).decode()
        cr.execute(
            "UPDATE keykeep_credential SET secret_key = %s WHERE id = %s",
            (wrapped, cred_id),
        )

        # 2. Migrate legacy ir.config_parameter values (old Fernet) into columns
        for field, col, has_value in (("password", "password_cipher", pw_cipher),
                                      ("key_value", "key_value_cipher", kv_cipher)):
            legacy = _legacy_param(cr, "keykeep_credential_%s_%s" % (cred_id, field))
            if legacy and old_master:
                try:
                    plain = old_master.decrypt(legacy.encode()).decode()
                except InvalidToken:
                    _logger.warning(
                        "Could not decrypt legacy %s for credential %s", field, cred_id
                    )
                    continue
                new_cipher = Fernet(cred_key).encrypt(plain.encode()).decode()
                cr.execute(
                    "UPDATE keykeep_credential SET %s = %%s WHERE id = %%s"
                    % col,
                    (new_cipher, cred_id),
                )
        migrated += 1

    # 3. Re-encrypt version snapshots (were encrypted with the old master key)
    cr.execute("SELECT id, credential_id, password, key_value FROM keykeep_credential_version")
    for ver_id, cred_id, v_pw, v_kv in cr.fetchall():
        cr.execute("SELECT secret_key FROM keykeep_credential WHERE id = %s", (cred_id,))
        row = cr.fetchone()
        if not row or not row[0]:
            continue
        cred_key = master.decrypt(row[0].encode())
        updates = []
        for col, val in (("password", v_pw), ("key_value", v_kv)):
            if not val:
                continue
            try:
                plain = old_master.decrypt(val.encode()).decode()
                new_cipher = Fernet(cred_key).encrypt(plain.encode()).decode()
                updates.append((col, new_cipher))
            except (InvalidToken, AttributeError):
                _logger.warning("Legacy version %s (%s) not re-encrypted", ver_id, col)
        for col, new_cipher in updates:
            cr.execute(
                "UPDATE keykeep_credential_version SET %s = %%s WHERE id = %%s" % col,
                (new_cipher, ver_id),
            )

    # 4. Remove legacy config params (delayed cleanup — after success)
    cr.execute("DELETE FROM ir_config_parameter WHERE key = 'keykeep.encryption_key'")
    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key LIKE 'keykeep_credential_%'"
    )

    _logger.info("Keykeep migration: %s credentials hardened", migrated)
