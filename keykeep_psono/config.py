# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Server identity key lookup.

Precedence (design D2 — keys NEVER in the database):
1. odoo.conf parameters keykeep_psono_private_key / keykeep_psono_public_key
   (injected via env / Salt pillar in production)
2. a keys file in the Odoo data dir (bootstrap written by post_init_hook)
3. environment variables KEYKEEP_PSONO_PRIVATE_KEY / KEYKEEP_PSONO_PUBLIC_KEY

Missing keys raise a clear configuration error — never a silent fallback.
"""

import logging
import os

from odoo.tools.config import config

_logger = logging.getLogger(__name__)

DEFAULT_KEYS_FILE = "/var/lib/odoo/keykeep_psono_keys.conf"


def _keys_file_path():
    return os.environ.get("KEYKEEP_PSONO_KEYS_FILE", DEFAULT_KEYS_FILE)


def _read_keys_file():
    path = _keys_file_path()
    if not os.path.exists(path):
        return None, None
    try:
        values = {}
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip()
        return (
            values.get("keykeep_psono_private_key"),
            values.get("keykeep_psono_public_key"),
        )
    except OSError as exc:
        _logger.warning("keykeep_psono: could not read keys file %s: %s", path, exc)
        return None, None


def get_server_keys():
    """Return (private_key_hex, public_key_hex) or raise a clear error."""
    private_key = config.get("keykeep_psono_private_key")
    public_key = config.get("keykeep_psono_public_key")

    if not private_key or not public_key:
        private_key, public_key = _read_keys_file()

    if not private_key or not public_key:
        private_key = os.environ.get("KEYKEEP_PSONO_PRIVATE_KEY")
        public_key = os.environ.get("KEYKEEP_PSONO_PUBLIC_KEY")

    if not private_key or not public_key:
        raise ValueError(
            "keykeep_psono server identity keys are not configured. "
            "Add keykeep_psono_private_key / keykeep_psono_public_key to "
            "odoo.conf (or set KEYKEEP_PSONO_PRIVATE_KEY/PUBLIC_KEY env), "
            "or run the module install once so post_init_hook generates them."
        )
    return private_key, public_key
