# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class KeykeepCostForecast(models.Model):
    _name = "keykeep.cost.forecast"
    _description = "Keykeep Cost Forecast"
    _order = "forecast_date asc"

    subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Subscription",
        required=True,
        ondelete="cascade",
    )
    forecast_date = fields.Date(string="Forecast Date", required=True)
    forecast_amount = fields.Monetary(
        currency_field="currency_id", string="Forecast Amount"
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

    _sql_constraints = [
        (
            "sub_forecast_month_uniq",
            "unique (subscription_id, forecast_date)",
            "Only one forecast entry per subscription per month.",
        )
    ]
