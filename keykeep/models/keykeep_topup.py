# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class KeykeepTopup(models.Model):
    _name = "keykeep.topup"
    _description = "Keykeep Top-up"
    _order = "date desc, id desc"

    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
        ondelete="cascade",
        index=True,
    )
    provider_id = fields.Many2one(
        comodel_name="res.partner",
        string="Provider",
        related="subscription_id.partner_id",
        store=True,
        index=True,
        domain="[('is_bifrost_provider', '=', True)]",
        help="Provider (res.partner) the top-up was made for — convenience, related from subscription.",
    )
    date = fields.Datetime(string="Date", required=True, default=fields.Datetime.now)
    amount = fields.Monetary(
        currency_field="currency_id",
        string="Amount",
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="subscription_id.currency_id",
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="subscription_id.company_id",
        store=True,
    )
    method = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("auto", "Auto"),
            ("api", "API"),
        ],
        string="Method",
        default="manual",
        required=True,
        help="manual = gjord av operatören; auto = auto-top-up-konfig; api = provider-API-exekvering.",
    )
    source = fields.Selection(
        selection=[
            ("provider_portal", "Provider Portal"),
            ("provider_api", "Provider API"),
            ("bifrost_budget", "Bifrost Budget"),
            ("other", "Other"),
        ],
        string="Source",
        default="provider_portal",
    )
    credential_id = fields.Many2one(
        comodel_name="keykeep.credential",
        string="Credential",
        ondelete="set null",
        help="Motstående konto/nyckel (valfritt).",
    )
    payment_method_id = fields.Many2one(
        comodel_name="keykeep.payment.method",
        string="Payment Method",
        ondelete="set null",
    )
    receipt_ref = fields.Char(
        string="Receipt Reference",
        help="Kvitto/order-ref från providern.",
    )
    invoice_stub_id = fields.Many2one(
        comodel_name="keykeep.invoice.stub",
        string="Invoice Stub",
        ondelete="set null",
        help="Om top-up:en faktureras vidare.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("reconciled", "Reconciled"),
        ],
        string="Status",
        default="draft",
        required=True,
        help="Bara confirmed/reconciled räknas in i prognoserna.",
    )
    note = fields.Text(string="Note")

    _sql_constraints = [
        (
            "topup_receipt_uniq",
            "UNIQUE(subscription_id, date, receipt_ref)",
            "A top-up with the same subscription, date and receipt reference already exists.",
        )
    ]

    def action_confirm(self):
        self.ensure_one()
        if self.state == "draft":
            self.state = "confirmed"
        return True

    def action_reconcile(self):
        self.ensure_one()
        self.state = "reconciled"
        return True
