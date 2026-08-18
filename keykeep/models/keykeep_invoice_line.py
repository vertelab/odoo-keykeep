# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class KeykeepInvoiceLine(models.Model):
    _name = "keykeep.invoice.line"
    _description = "Keykeep Invoice Line"
    _order = "sequence, id"
    _parent_store = True
    _parent_name = "parent_id"

    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        comodel_name="keykeep.invoice.line",
        string="Parent Line",
        ondelete="cascade",
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        comodel_name="keykeep.invoice.line",
        inverse_name="parent_id",
        string="Child Lines",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.subscription_id.company_id
        if self.subscription_id else self.env.company,
    )
    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        domain="[('purchase_ok', '=', True)]",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
    )
    name = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    price_unit = fields.Float(string="Unit Price")
    tax_ids = fields.Many2many(
        comodel_name="account.tax",
        string="Taxes",
        domain="[('type_tax_use', '=', 'purchase')]",
    )
    analytic_distribution = fields.Json(
        string="Analytic Distribution",
        help="Analytic accounts with distribution percentages.",
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            if not self.name:
                self.name = self.product_id.display_name
