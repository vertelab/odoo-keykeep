# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Keykeep — Vaultwarden Bridge",
    "summary": "Pluggable storage backend: store keykeep credential values in Vaultwarden",
    "version": "18.0.1.0.0",
    "development_status": "Alpha",
    "category": "Productivity",
    "author": "Vertel Sverige AB",
    "license": "AGPL-3",
    "installable": True,
    "auto_install": False,
    "external_dependencies": {
        "python": ["requests", "pyotp"],
    },
    "depends": ["keykeep"],
    "data": [
        "security/ir.model.access.csv",
        "views/keykeep_vaultwarden_backend_views.xml",
    ],
}
