# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class KeykeepPaymentMethod(models.Model):
    _name = "keykeep.payment.method"
    _description = "Keykeep Payment Method"
    _order = "name"

    name = fields.Char(required=True)
    method_type = fields.Selection(
        selection=[
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
            ("paypal", "PayPal"),
            ("invoice", "Invoice"),
            ("direct_debit", "Direct Debit"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    card_last_four = fields.Char(
        string="Card Last 4 Digits",
        size=4,
        help="Last four digits of the card number (PCI-DSS safe).",
    )
    card_expiry_date = fields.Date(string="Card Expiry Date")
    card_holder_name = fields.Char(string="Card Holder Name")
    notes = fields.Text(string="Notes")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    subscription_ids = fields.One2many(
        comodel_name="keykeep.subscription",
        inverse_name="payment_method_id",
        string="Subscriptions",
    )
