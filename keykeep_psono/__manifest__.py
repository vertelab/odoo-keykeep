# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Keykeep Psono — Personal Password Vault",
    "summary": "Zero-knowledge personal password vault, psono-protocol compatible",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://github.com/vertelab/odoo-keykeep",
    "author": "Vertel AB",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "external_dependencies": {
        "python": ["pynacl", "bcrypt"],
    },
    "depends": [
        "base",
        "mail",
        "keykeep",
    ],
    "data": [
        "security/keykeep_psono_security.xml",
        "security/ir.model.access.csv",
        "data/keykeep_psono_data.xml",
        "views/res_users_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "keykeep_psono/static/src/js/keykeep_psono.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "tests": ["tests/"],
}
