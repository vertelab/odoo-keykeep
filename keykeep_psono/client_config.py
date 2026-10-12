# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Client configuration for the psono web client (design D1/D2/D3).

The vendored psono-web build reads its configuration from
``<web_client>/config.json`` — both via a relative ``fetch("config.json")``
and via the Remote Config flow (``info.web_client + "/config.json"``). Both
land on the same URL, which this module now serves dynamically.

Two kinds of values:

- **Global** policy flags come from ``ir.config_parameter`` under the
  ``keykeep_psono.`` namespace. Same truth as the server-side checks.
- **Personal** values come from the signed-in ``res.users``. Only language is
  personal today (design D3); the client applies it via
  ``i18n.changeLanguage(user.language)``.

Precedence rule (D2): global security flags always win. A personal value must
never override ``allow_custom_server`` or ``authentication_methods``.
"""

import json
import logging

from odoo import http

from .util import odoo_lang_to_psono

_logger = logging.getLogger(__name__)

PARAM = "keykeep_psono."

# Flags the client reads. Kept in one place so the server-side checks and the
# generated configuration cannot drift apart.
GLOBAL_FLAGS = (
    ("allow_registration", "1"),
    ("allow_lost_password", "1"),
    ("allow_delete_account", "0"),
    ("allow_custom_server", "1"),
)

# Methods this server actually implements. Never derived from user input.
AUTHENTICATION_METHODS = ["AUTHKEY"]

MORE_LINKS = [
    {
        "href": "https://doc.psono.com/",
        "title": "DOCUMENTATION",
        "class": "fa-book",
    },
    {
        "href": "privacy-policy.html",
        "title": "PRIVACY_POLICY",
        "class": "fa-user-secret",
    },
    {
        "href": "https://www.psono.com",
        "title": "ABOUT_US",
        "class": "fa-info-circle",
    },
]


def _param(env, name, default):
    return env["ir.config_parameter"].sudo().get_param(PARAM + name, default)


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def build_config(env, host, session_uid=None):
    """Build the client configuration.

    ``session_uid`` is the authenticated Odoo user id, or None. Personal
    values are applied only when it resolves to a real user.
    """
    config = {
        "backend_servers": [
            {
                "title": "Vertel",
                "url": "/keykeep/psono",
                "domain": host or "",
            }
        ],
        "authentication_methods": list(AUTHENTICATION_METHODS),
        "more_links": [dict(link) for link in MORE_LINKS],
    }

    # ── global flags (authoritative) ──────────────────────────────
    for name, default in GLOBAL_FLAGS:
        config[name] = _as_bool(_param(env, name, default))

    # ── personal values (only for an authenticated session) ───────
    lang = "en"
    if session_uid:
        user = env["res.users"].sudo().browse(session_uid).exists()
        if user:
            lang = odoo_lang_to_psono(user.lang)
    config["language"] = lang

    return config


def load_static_config():
    """Read the shipped static config.json, or None if unavailable.

    Used as the fallback for clients that cannot reach the dynamic endpoint
    (e.g. an extension hitting a stale cached asset path).
    """
    import os

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static",
        "src",
        "psono_web",
        "config.json",
    )
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        _logger.warning("keykeep_psono: could not read static config: %s", exc)
        return None
