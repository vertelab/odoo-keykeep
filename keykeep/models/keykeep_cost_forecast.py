# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class KeykeepCostForecast(models.Model):
    _name = "keykeep.cost.forecast"
    _description = "Keykeep Cost Forecast"
    _order = "forecast_date asc"

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
        help="Provider the forecast row applies to (related from subscription partner).",
    )
    category_id = fields.Many2one(
        comodel_name="keykeep.category",
        string="Category",
        related="subscription_id.category_id",
        store=True,
        index=True,
        help="Kategori från subscription — för pivot/analys.",
    )
    forecast_date = fields.Date(string="Forecast Date", required=True)
    forecast_amount = fields.Monetary(
        currency_field="currency_id", string="Forecast Amount"
    )
    source = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("computed", "Computed"),
        ],
        string="Source",
        default="manual",
        help="manual = operatörssatt (bevaras); computed = genererad av prognos-cronen.",
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

    @api.model
    def generate_computed_forecasts(self, days=30):
        """Generate computed forecast rows per provider per day.

        Reads daily consumption from bifrost.provider.usage.snapshot
        (source=histogram) when the bifrost module is installed, plus top-up
        history from keykeep.topup. Manual rows are never overwritten.
        """
        from datetime import timedelta

        today = fields.Date.today()
        usage_model = self.env.get("bifrost.provider.usage.snapshot")
        if usage_model is None:
            _logger.info("keykeep forecast: bifrost usage snapshot not available")
            return 0

        # Aggregate consumption per provider per day (last N days)
        snaps = usage_model.search([
            ("source", "=", "histogram"),
            ("snapshot_time", ">=", fields.Datetime.now() - timedelta(days=days)),
        ])
        usage_by_provider = {}
        for snap in snaps:
            day = snap.snapshot_time.date()
            usage_by_provider.setdefault(snap.provider_id.id, {})
            usage_by_provider[snap.provider_id.id][day] = (
                usage_by_provider[snap.provider_id.id].get(day, 0.0) + snap.cost_usd
            )

        # Top-ups per provider (confirmed/reconciled only)
        topup_model = self.env["keykeep.topup"]
        topups = topup_model.search([("state", "in", ["confirmed", "reconciled"])])
        topup_by_sub = {}
        for t in topups:
            topup_by_sub.setdefault(t.subscription_id.id, 0.0)
            topup_by_sub[t.subscription_id.id] += t.amount

        created = 0
        subscriptions = self.env["keykeep.subscription"].search([])
        for sub in subscriptions:
            usage_by_day = usage_by_provider.get(sub.partner_id.id or 0, {})
            if not usage_by_day:
                continue
            days_used = len(usage_by_day)
            total_usage = sum(usage_by_day.values())
            burn = total_usage / days_used if days_used else 0.0
            topup_sum = topup_by_sub.get(sub.id, 0.0)
            # contract_type-semantik: top_up → bas = top-up-historik;
            # subscription/plus → bas = cost_amount (+ top-ups).
            contract_type = getattr(sub, "contract_type", "subscription")
            if contract_type == "top_up":
                base = topup_sum
            else:
                base = (sub.cost_amount or 0.0) + topup_sum
            for i in range(days):
                fdate = today - timedelta(days=i)
                # Projected remaining budget: bas − konsumtion
                projected = base - total_usage
                existing = self.search([
                    ("subscription_id", "=", sub.id),
                    ("forecast_date", "=", fdate),
                    ("source", "=", "computed"),
                ], limit=1)
                vals = {
                    "subscription_id": sub.id,
                    "forecast_date": fdate,
                    "forecast_amount": projected,
                    "source": "computed",
                }
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)
                    created += 1
        _logger.info("keykeep forecast: %d computed rows created", created)
        return created
