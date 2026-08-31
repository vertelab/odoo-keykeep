# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""post_init_hook — generate the persistent server identity keypair.

The psono protocol requires a persistent server identity keypair
(Curve25519 private/public; the same private bytes double as the Ed25519
seed for /info/ signing). The keypair MUST live outside the database
(design D2): a keys file in the Odoo data dir, or the odoo.conf parameters
keykeep_psono_private_key / keykeep_psono_public_key injected via env/pillar.

Never stores key material in ir.config_parameter or any table.
"""

import logging
import os

_logger = logging.getLogger(__name__)

DEFAULT_KEYS_FILE = "/var/lib/odoo/keykeep_psono_keys.conf"


def _keys_file_path():
    return os.environ.get("KEYKEEP_PSONO_KEYS_FILE", DEFAULT_KEYS_FILE)


def generate_keys():
    """Generate a Curve25519 keypair (hex), same pattern as psono's
    generateserverkeys.py (PRIVATE_KEY / PUBLIC_KEY)."""
    try:
        from nacl.public import PrivateKey
        from nacl.encoding import HexEncoder
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PyNaCl is required for keykeep_psono "
            "(pip install pynacl --break-system-packages)"
        ) from exc
    box = PrivateKey.generate()
    return (
        box.encode(encoder=HexEncoder).decode(),
        box.public_key.encode(encoder=HexEncoder).decode(),
    )


def _write_keys_file(private_key, public_key):
    path = _keys_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("keykeep_psono_private_key = %s\n" % private_key)
            fh.write("keykeep_psono_public_key = %s\n" % public_key)
        os.chmod(path, 0o600)
        _logger.warning(
            "keykeep_psono: server identity keypair generated and written to %s "
            "(backup this file together with the database)", path)
        return True
    except OSError as exc:
        _logger.warning("keykeep_psono: could not write keys file %s: %s", path, exc)
        return False


def post_init_hook(env):
    """Generate server identity keys if none are configured anywhere.

    Precedence: odoo.conf / env parameters (managed by pillar in production)
    first; a keys file in the Odoo data dir as fallback bootstrap.
    """
    from odoo.tools.config import config

    if config.get("keykeep_psono_private_key") and config.get("keykeep_psono_public_key"):
        _logger.info("keykeep_psono: server identity keys already configured in odoo.conf")
        return

    keys_file = _keys_file_path()
    if os.path.exists(keys_file):
        _logger.info("keykeep_psono: server identity keys file present at %s", keys_file)
        return

    private_key, public_key = generate_keys()
    _logger.warning(
        "keykeep_psono: no server identity keys configured; generated a new keypair. "
        "In production inject them via odoo.conf/pillar "
        "(keykeep_psono_private_key / keykeep_psono_public_key).")
    _write_keys_file(private_key, public_key)
