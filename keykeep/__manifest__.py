# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Keykeep — SaaS Subscription Manager",
    "summary": "Manage SaaS subscriptions, credentials, API keys, and costs",
    "version": "18.0.1.24.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://github.com/vertelab/odoo-keykeep",
    "author": "Vertel AB",
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    "auto_install": False,
    "external_dependencies": {"python": ["cryptography"]},
    "depends": [
        "base",
        "mail",
        "account",
        "contacts",
    ],
    "data": [
        "security/keykeep_security.xml",
        "security/ir.model.access.csv",
        "views/keykeep_category_views.xml",
        "views/keykeep_payment_method_views.xml",
        "views/keykeep_credential_views.xml",
        "views/keykeep_subscription_views.xml",
        "views/keykeep_topup_views.xml",
        "views/keykeep_invoice_stub_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/keykeep_menu.xml",
        "data/keykeep_category_data.xml",
        "data/ir_cron_data.xml",
        "data/keykeep_config_data.xml",
        "wizards/create_journal_entry_views.xml",
        "wizards/topup_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "keykeep/static/src/js/keykeep.js",
            "keykeep/static/src/scss/keykeep.scss",
        ],
    },
}
