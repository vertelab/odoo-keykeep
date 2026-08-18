# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from dateutil.relativedelta import relativedelta

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
        help="Valuta för forecast_amount (subscription- eller bilagans valuta).",
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

    # ──────────────────────────────────────────────────────────────────
    # Prognos — rullande 12 månader framåt, månadsvis
    #
    # Belopp = subscription.cost_amount + genomsnittliga top-ups under
    # perioden, justerat efter trenden från historiska fakturor
    # (samma nivå / ökad / minskad). Alla belopp omvandlas till bilagans
    # valuta (forecast-currency) via res.currency._convert.
    # ──────────────────────────────────────────────────────────────────

    def _get_invoice_currency(self, subscription):
        """Valuta för forecasten: senaste fakturans valuta, annars
        subscription-valutan, annars företagets valuta."""
        inv = subscription.invoice_ids.filtered(
            lambda i: i.state == "posted"
        )[:1]
        if inv and inv.currency_id:
            return inv.currency_id
        if subscription.currency_id:
            return subscription.currency_id
        return subscription.company_id.currency_id

    def _monthly_cost(self, subscription, currency, today):
        """Grundbelopp per månad: cost_amount + genomsnittlig top-up,
        omräknat till forecast-valutan."""
        # Grundkostnad
        base = subscription.cost_amount or 0.0
        base = subscription.currency_id._convert(
            base, currency, subscription.company_id, today)

        # Genomsnittliga top-ups per månad (senaste 12 mån)
        topups = self.env["keykeep.topup"].search([
            ("subscription_id", "=", subscription.id),
            ("state", "in", ["confirmed", "reconciled"]),
            ("date", ">=", today - relativedelta(months=12)),
        ])
        if topups:
            avg_topup = sum(topups.mapped("amount")) / 12.0
            avg_topup = subscription.currency_id._convert(
                avg_topup, currency, subscription.company_id, today)
        else:
            avg_topup = 0.0
        return base + avg_topup

    def _trend_factor(self, subscription, currency, today):
        """Trend från historiska fakturor:
        - ingen faktura → 1.0 (samma nivå)
        - fakturor > grundkostnad → ökning (faktor > 1)
        - fakturor < grundkostnad → minskning (faktor < 1)
        Faktorn klampas till [0.5, 1.5] för att undvika extrema hopp."""
        invoices = subscription.invoice_ids.filtered(
            lambda i: i.state == "posted"
            and i.invoice_date >= (today - relativedelta(months=12))
        )
        if not invoices:
            return 1.0
        total = 0.0
        for inv in invoices:
            inv_cur = inv.currency_id or subscription.currency_id
            total += inv_cur._convert(
                inv.amount_total, currency, subscription.company_id, today)
        avg_invoice = total / len(invoices)
        base = self._monthly_cost(subscription, currency, today)
        if base <= 0:
            return 1.0
        factor = avg_invoice / base
        return max(0.5, min(1.5, factor))

    @api.model
    def generate_forecast(self, months=12):
        """Generera rullande månadsprognos (12 månader framåt).

        - En rad per subscription och månad
        - Belopp = cost_amount + snitt top-ups, trendjusterat
        - Alla belopp i bilagans valuta (currency conversion)
        - Befintliga computed-rader uppdateras; manual-rader rörs inte
        """
        today = fields.Date.today()
        subscriptions = self.env["keykeep.subscription"].search([])
        created = 0
        updated = 0
        for sub in subscriptions:
            currency = self._get_invoice_currency(sub)
            base = self._monthly_cost(sub, currency, today)
            factor = self._trend_factor(sub, currency, today)
            amount = round(base * factor, 2)

            for i in range(1, months + 1):
                fdate = (today + relativedelta(months=i)).replace(day=1)
                existing = self.search([
                    ("subscription_id", "=", sub.id),
                    ("forecast_date", "=", fdate),
                    ("source", "=", "computed"),
                ], limit=1)
                vals = {
                    "subscription_id": sub.id,
                    "forecast_date": fdate,
                    "forecast_amount": amount,
                    "currency_id": currency.id,
                    "source": "computed",
                }
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    self.create(vals)
                    created += 1
        _logger.info(
            "keykeep forecast: %d created, %d updated (months=%d)",
            created, updated, months)
        return {"created": created, "updated": updated}
