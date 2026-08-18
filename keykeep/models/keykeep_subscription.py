# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class KeykeepSubscription(models.Model):
    _name = "keykeep.subscription"
    _description = "Keykeep Subscription"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "next_renewal_date asc, name asc"

    # === Basic Information ===
    name = fields.Char(required=True, string="Service Name", tracking=True)
    logo = fields.Binary(string="Logo", attachment=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Supplier",
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
    )
    category_id = fields.Many2one(
        comodel_name="keykeep.category",
        string="Category",
        tracking=True,
    )
    
    billing_model = fields.Selection(
        selection=[
            ("prepaid", "Prepaid"),
            ("postpaid", "Postpaid"),
            ("unknown", "Unknown"),
        ],
        string="Billing Model",
        default="unknown",
        index=True,
        help="prepaid = credits/top-up  postpaid = invoice i afterwards ",)

    state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        default="active",
        tracking=True,
    )
    url = fields.Char(string="Service URL")
    notes = fields.Html(string="Notes")

    @api.model
    def default_get(self, fields_list):
        """When created from a supplier (partner_id via context), default the
        Service URL from the partner's website if not explicitly provided.
        Also set Start Date to today when creating a new subscription."""
        res = super().default_get(fields_list)
        partner_id = self.env.context.get("default_partner_id")
        if partner_id and not res.get("url"):
            partner = self.env["res.partner"].browse(partner_id)
            if partner.website:
                res["url"] = partner.website
        if not res.get("start_date"):
            res["start_date"] = fields.Date.context_today(self)
        return res

    # === Financial Info ===
    cost_amount = fields.Monetary(currency_field="currency_id", string="Cost", tracking=True)
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    payment_method_id = fields.Many2one(
        comodel_name="keykeep.payment.method",
        string="Payment Method",
    )

    # === Renewal Info ===
    start_date = fields.Date(string="Start Date", tracking=True)
    next_renewal_date = fields.Date(
        compute="_compute_next_renewal_date",
        store=True,
        readonly=False,
        string="Next Renewal",
        tracking=True,
    )
    cancellation_date = fields.Date(string="Cancellation Date", tracking=True)
    renewal_frequency = fields.Selection(
        selection=[
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
            ("custom", "Custom"),
        ],
        default="monthly",
        required=True,
    )
    renewal_cycle = fields.Integer(
        default=1,
        string="Renewal Cycle",
        help="Number of frequency units between renewals (e.g. 3 for quarterly means every 3 months).",
    )
    auto_renew = fields.Boolean(default=True, string="Auto Renew")
    notify_days_before = fields.Integer(
        default=14,
        string="Notify Days Before",
        help="Send notification this many days before the next renewal date.",
    )

    # === Replacement ===
    replacement_subscription_id = fields.Many2one(
        comodel_name="keykeep.subscription",
        string="Replacement Service",
        help="Service that replaced this subscription.",
    )

    # === Related Records ===
    credential_ids = fields.One2many(
        comodel_name="keykeep.credential",
        inverse_name="subscription_id",
        string="Credentials & API Keys",
    )
    credential_count = fields.Integer(compute="_compute_credential_count")
    invoice_ids = fields.Many2many(
        comodel_name="account.move",
        relation="keykeep_subscription_account_move_rel",
        column1="subscription_id",
        column2="move_id",
        string="Linked Invoices",
        domain="[('move_type', '=', 'in_invoice'), ('partner_id', '=', partner_id)]",
        copy=False,
    )
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    journal_entry_ids = fields.Many2many(
        comodel_name="account.move",
        relation="keykeep_subscription_account_move_entry_rel",
        column1="subscription_id",
        column2="move_id",
        string="Journal Entries",
        domain="[('move_type', '=', 'entry')]",
        copy=False,
    )
    cost_forecast_ids = fields.One2many(
        comodel_name="keykeep.cost.forecast",
        inverse_name="subscription_id",
        string="Cost Forecasts",
    )

    # ── Top-ups (händelsejournal) ────────────────────────────────────────
    topup_ids = fields.One2many(
        comodel_name="keykeep.topup",
        inverse_name="subscription_id",
        string="Top-ups",
    )
    topup_count = fields.Integer(
        string="Top-ups",
        compute="_compute_topup_count",
    )
    forecast_count = fields.Integer(
        string="Forecast",
        compute="_compute_forecast_count",
    )

    @api.depends("topup_ids", "topup_ids.state", "topup_ids.amount")
    def _compute_topup_count(self):
        for rec in self:
            rec.topup_count = len(rec.topup_ids)

    @api.depends("cost_forecast_ids")
    def _compute_forecast_count(self):
        for rec in self:
            rec.forecast_count = len(rec.cost_forecast_ids)

    def action_view_topups(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Top-ups",
            "res_model": "keykeep.topup",
            "domain": [("subscription_id", "=", self.id)],
            "view_mode": "list,form",
            "context": {"default_subscription_id": self.id},
        }

    def action_view_forecast(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Cost Forecast",
            "res_model": "keykeep.cost.forecast",
            "domain": [("subscription_id", "=", self.id)],
            "view_mode": "list,form",
            "context": {"default_subscription_id": self.id},
        }

    def action_add_topup(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Record Top-up",
            "res_model": "keykeep.topup.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_subscription_id": self.id},
        }
    active = fields.Boolean(default=True)

    # === Computed Display Fields (Kanban) ===
    days_until_renewal = fields.Integer(
        compute="_compute_days_until_renewal",
        string="Days Until Renewal",
    )
    kanban_state = fields.Selection(
        selection=[
            ("ok", "OK"),
            ("warning", "Expiring Soon"),
            ("critical", "Overdue"),
            ("inactive", "Inactive"),
        ],
        compute="_compute_kanban_state",
        store=True,
        string="Status",
    )

    # === Renewal semaphore (green/yellow/red) ===
    # Green = ok; Yellow = within notify window; Red = overdue/expired/inactive.
    # Extended by bifrost_keykeep to also consider budget days/burn rate.
    renewal_semaphore = fields.Selection(
        selection=[
            ("green", "Green"),
            ("yellow", "Yellow"),
            ("red", "Red"),
        ],
        compute="_compute_renewal_semaphore",
        store=True,
        index=True,
        string="Renewal Semaphore",
        help="green = ok; yellow = within notify window; red = overdue/expired/inactive.",
    )

    @api.depends("state", "active", "next_renewal_date", "notify_days_before")
    def _compute_renewal_semaphore(self):
        today = date.today()
        for rec in self:
            if rec.state != "active" or not rec.active:
                rec.renewal_semaphore = "red"
                continue
            if rec.next_renewal_date and rec.next_renewal_date < today:
                rec.renewal_semaphore = "red"
                continue
            if rec.next_renewal_date and \
                    (rec.next_renewal_date - today).days <= rec.notify_days_before:
                rec.renewal_semaphore = "yellow"
                continue
            rec.renewal_semaphore = "green"

    

    contract_type = fields.Selection(
        selection=[
            ("subscription", "Subscription"),
            ("top_up", "Top-up"),
            ("subscription_plus_topup", "Subscription + Top-up"),
        ],
        string="Contract Type",
        default="subscription",
        help="Renewal type",
    )

    # ══════════════════════════════════════════════════════════════════
    # Balance & Forecast — ägs av keykeep (basmodul).
    #
    # Fälten uppdateras normalt av bifrost_keykeep (balance-koll, cron,
    # prognos-körningar), men keykeep äger definitionerna så att de finns
    # även utan bifrost-bryggan. Onchange beräknar burn/days/projected när
    # användaren ändrar last_balance eller burn_rate_day i formuläret.
    # ══════════════════════════════════════════════════════════════════

    last_forecast_recommendation = fields.Text(
        string="Last Forecast Recommendation",
        readonly=True,
        help="Latest recommendation generated from the consumption forecast.",
    )
    budget_limit = fields.Float(
        string="Budget Limit (USD)",
        digits=(16, 4),
        help="Provider budget ceiling in USD (bifrost governance max_limit).",
    )
    last_balance = fields.Monetary(
        string="Balance",
        currency_field="balance_currency",
        help="Senast kända kreditsaldo hos providern (USD eller provider-valuta).",
    )
    balance_currency = fields.Many2one(
        "res.currency",
        string="Balance Currency",
        help="Valuta för last_balance (default USD).",
    )
    last_balance_checked_at = fields.Datetime(
        string="Date",
        help="När saldot senast avlästes (API eller manuellt).",
    )
    balance_source = fields.Selection(
        selection=[
            ("deepseek_balance", "DeepSeek /user/balance"),
            ("openrouter_credits", "OpenRouter /api/v1/credits"),
            ("manual", "Manual"),
            ("none", "None"),
        ],
        string="Balance Source",
        default="none",
        help="Hur providerns faktiska kreditsaldo avläses.",
    )
    burn_rate_day = fields.Monetary(
        string="Burn Rate (day)",
        currency_field="balance_currency",
        digits=(16, 4),
        readonly=True,
        help="Rolling average daily cost (mirrored from the provider / computed from last_balance).",
    )
    days_until_empty = fields.Float(
        string="Remaining days",
        digits=(16, 1),
        readonly=True,
        help="(budget_limit − current_usage) / burn_rate_day (mirrored).",
    )
    projected_empty_date = fields.Date(
        string="Forecasted Date",
        readonly=True,
        help="Today + days_until_empty (mirrored).",
    )
    budget_warning_threshold = fields.Float(
        string="Warning Threshold (%)",
        default=20.0,
        help="Warn when remaining balance drops below this % of the budget.",
    )
    budget_critical_threshold = fields.Float(
        string="Critical Threshold (%)",
        default=10.0,
        help="Flag critical when remaining balance drops below this % of the budget.",
    )
    abnormal_spike_multiplier = fields.Float(
        string="Abnormal Spike Multiplier",
        default=3.0,
        help="Multiplier over rolling average flagged as abnormal consumption.",
    )
    abnormal_window = fields.Integer(
        string="Abnormal Window (days)",
        default=7,
        help="Look-back window for abnormal consumption detection.",
    )
    tripwire_enabled = fields.Boolean(
        string="Tripwire Enabled",
        default=True,
        help="Hard tripwire that auto-excludes a provider on critical thresholds.",
    )
    auto_exclude_on_critical = fields.Boolean(
        string="Auto-exclude on Critical",
        default=False,
        help="Automatically exclude the provider when the tripwire trips.",
    )

    @api.onchange("last_balance")
    def _onchange_last_balance(self):
        """When last_balance changes, recompute burn rate (from provider
        snapshots when available), days until empty and projected empty date,
        and stamp the checked-at timestamp."""
        from datetime import timedelta
        for rec in self:
            partner = rec.partner_id
            if not partner:
                rec.last_balance_checked_at = fields.Datetime.now()
                continue
            # Ask the provider for its burn-rate forecast (snapshot-based)
            if hasattr(partner, "_compute_burn_forecast"):
                partner._compute_burn_forecast()
                rec.burn_rate_day = partner.burn_rate_day
                rec.days_until_empty = partner.days_until_empty
                rec.projected_empty_date = partner.projected_empty_date
            elif rec.burn_rate_day and rec.last_balance:
                days = rec.last_balance / rec.burn_rate_day
                rec.days_until_empty = round(days, 1)
                rec.projected_empty_date = fields.Date.today() + timedelta(days=days)
            rec.last_balance_checked_at = fields.Datetime.now()

    @api.onchange("burn_rate_day")
    def _onchange_burn_rate_day(self):
        """When burn_rate_day changes, recompute days_until_empty and
        projected_empty_date from the current last_balance."""
        from datetime import timedelta
        for rec in self:
            if rec.burn_rate_day and rec.last_balance:
                days = rec.last_balance / rec.burn_rate_day
                rec.days_until_empty = round(days, 1)
                rec.projected_empty_date = fields.Date.today() + timedelta(days=days)
            else:
                rec.days_until_empty = False
                rec.projected_empty_date = False



    @api.depends("start_date", "renewal_frequency", "renewal_cycle")
    def _compute_next_renewal_date(self):
        """Compute next_renewal_date from start_date + frequency + cycle.
        Recomputes whenever frequency/cycle/start_date change."""
        for rec in self:
            if rec.start_date:
                freq_map = {
                    "monthly": relativedelta(months=rec.renewal_cycle),
                    "quarterly": relativedelta(months=3 * rec.renewal_cycle),
                    "yearly": relativedelta(years=rec.renewal_cycle),
                    "custom": None,
                }
                delta = freq_map.get(rec.renewal_frequency)
                if delta:
                    rec.next_renewal_date = rec.start_date + delta

    @api.onchange("renewal_frequency", "renewal_cycle", "start_date")
    def _onchange_renewal_frequency(self):
        """When renewal frequency/cycle/start changes, set next renewal from
        the frequency (next_renewal_date is a stored compute — assign directly
        so the form reflects it immediately)."""
        for rec in self:
            if not rec.start_date or not rec.renewal_frequency:
                continue
            freq_map = {
                "monthly": relativedelta(months=rec.renewal_cycle or 1),
                "quarterly": relativedelta(months=3 * (rec.renewal_cycle or 1)),
                "yearly": relativedelta(years=rec.renewal_cycle or 1),
                "custom": None,
            }
            delta = freq_map.get(rec.renewal_frequency)
            if delta:
                rec.next_renewal_date = rec.start_date + delta

    @api.depends("next_renewal_date")
    def _compute_days_until_renewal(self):
        today = date.today()
        for rec in self:
            if rec.next_renewal_date and rec.state == "active":
                rec.days_until_renewal = (rec.next_renewal_date - today).days
            else:
                rec.days_until_renewal = 0

    @api.depends("next_renewal_date", "state", "active", "credential_ids", "credential_ids.expiry_date", "credential_ids.rotation_age")
    def _compute_kanban_state(self):
        today = date.today()
        for rec in self:
            if rec.state != "active" or not rec.active:
                rec.kanban_state = "inactive"
                continue
            # Check renewal status
            if rec.next_renewal_date and rec.next_renewal_date < today:
                rec.kanban_state = "critical"
                continue
            # Check credential health: any expired credentials → critical
            expired_creds = rec.credential_ids.filtered(
                lambda c: c.expiry_date and c.expiry_date < today
            )
            if expired_creds:
                rec.kanban_state = "critical"
                continue
            # Check renewal warning
            if rec.next_renewal_date and (rec.next_renewal_date - today).days <= rec.notify_days_before:
                rec.kanban_state = "warning"
                continue
            # Check credential health: any expiring within notify_days_before
            expiring_creds = rec.credential_ids.filtered(
                lambda c: c.expiry_date and 0 <= (c.expiry_date - today).days <= rec.notify_days_before
            )
            if expiring_creds:
                rec.kanban_state = "warning"
                continue
            rec.kanban_state = "ok"

    @api.depends("credential_ids")
    def _compute_credential_count(self):
        for rec in self:
            rec.credential_count = len(rec.credential_ids)

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    # --- Actions ---

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Linked Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {"create": False},
        }

    def action_view_credentials(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Credentials"),
            "res_model": "keykeep.credential",
            "view_mode": "list,form",
            "domain": [("subscription_id", "=", self.id)],
        }

    def action_fetch_logo(self):
        """Auto-fetch logo from Clearbit Logo API based on URL domain."""
        self.ensure_one()
        if not self.url:
            raise ValidationError(_("Set a URL first to auto-fetch the logo."))
        import urllib.parse

        parsed = urllib.parse.urlparse(self.url)
        domain = parsed.netloc or self.url
        clearbit_url = f"https://logo.clearbit.com/{domain}"
        try:
            import urllib.request

            req = urllib.request.Request(clearbit_url, headers={"User-Agent": "Odoo-Keykeep/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                self.logo = response.read()
        except Exception as e:
            _logger.warning("Could not fetch logo from %s: %s", clearbit_url, e)
            raise ValidationError(
                _("Could not fetch logo from %s. Try uploading manually.") % clearbit_url
            )

    # --- Cron: Update renewal dates ---

    @api.model
    def _cron_update_renewal_dates(self):
        """Daily cron: advance next_renewal_date for auto-renew subscriptions
        where the date has passed."""
        today = date.today()
        subs = self.search([("auto_renew", "=", True), ("next_renewal_date", "<=", today), ("state", "=", "active")])
        for sub in subs:
            freq_map = {
                "monthly": relativedelta(months=sub.renewal_cycle),
                "quarterly": relativedelta(months=3 * sub.renewal_cycle),
                "yearly": relativedelta(years=sub.renewal_cycle),
                "custom": None,
            }
            delta = freq_map.get(sub.renewal_frequency)
            if delta:
                sub.next_renewal_date = sub.next_renewal_date + delta
        _logger.info("Keykeep: Updated renewal dates for %d subscriptions.", len(subs))

    # --- Cron: Send notifications ---

    @api.model
    def _cron_send_renewal_notifications(self):
        """Daily cron: notify responsible users about upcoming renewals."""
        today = date.today()
        subs = self.search([("state", "=", "active"), ("next_renewal_date", "!=", False), ("responsible_id", "!=", False)])
        for sub in subs:
            if not sub.notify_days_before:
                continue
            notify_date = sub.next_renewal_date - timedelta(days=sub.notify_days_before)
            if notify_date == today:
                sub.message_post(
                    body=_(
                        "⏰ **Renewal Reminder**: %(name)s is due for renewal on %(date)s.\n"
                        "Cost: %(amount)s %(currency)s"
                    )
                    % {
                        "name": sub.name,
                        "date": sub.next_renewal_date,
                        "amount": sub.cost_amount,
                        "currency": sub.currency_id.name,
                    },
                    partner_ids=sub.responsible_id.partner_id.ids,
                )

    # --- Cron: Credential expiry warnings ---

    @api.model
    def _cron_check_credential_expiry(self):
        """Daily cron: warn about credentials expiring within 30, 14, or 7 days."""
        today = date.today()
        thresholds = [30, 14, 7]
        creds = self.env["keykeep.credential"].search([
            ("expiry_date", "!=", False),
            ("renewal_reminder", "=", True),
        ])
        for cred in creds:
            days_left = (cred.expiry_date - today).days
            if days_left in thresholds:
                cred.subscription_id.message_post(
                    body=_(
                        "⚠️ **Credential Expiry**: '%(cred)s' (%(type)s) for %(sub)s "
                        "expires in %(days)d days on %(date)s."
                    )
                    % {
                        "cred": cred.name,
                        "type": cred.get_credential_type_display(),
                        "sub": cred.subscription_id.name,
                        "days": days_left,
                        "date": cred.expiry_date,
                    },
                    partner_ids=cred.subscription_id.responsible_id.partner_id.ids,
                )

    # --- Cron: Credential rotation health ---

    @api.model
    def _cron_check_credential_rotation(self):
        """Daily cron: warn about credentials not rotated for >90 days."""
        today = date.today()
        creds = self.env["keykeep.credential"].search([])
        for cred in creds:
            if cred.rotation_age and cred.rotation_age > 90:
                cred.subscription_id.message_post(
                    body=_(
                        "🔄 **Rotation Needed**: '%(cred)s' (%(type)s) for %(sub)s "
                        "has not been rotated for %(days)d days."
                    )
                    % {
                        "cred": cred.name,
                        "type": cred.get_credential_type_display(),
                        "sub": cred.subscription_id.name,
                        "days": cred.rotation_age,
                    },
                    partner_ids=cred.subscription_id.responsible_id.partner_id.ids,
                )

    # --- Cron: Access log cleanup ---

    @api.model
    def _cron_cleanup_access_logs(self):
        """Daily cron: delete access log entries older than retention period."""
        retention_days = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "keykeep.access_log_retention_days", "730"
            )
        )
        if retention_days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        logs = self.env["keykeep.credential.access.log"].search([
            ("accessed_at", "<", cutoff),
        ])
        count = len(logs)
        logs.unlink()
        _logger.info("Keykeep: Cleaned up %d access log entries older than %d days.", count, retention_days)

    # --- Constraints ---

    @api.constrains("renewal_frequency", "renewal_cycle")
    def _check_renewal_cycle(self):
        for rec in self:
            if rec.renewal_frequency == "custom" and rec.renewal_cycle <= 0:
                raise ValidationError(_("Renewal cycle must be positive."))


    # ── Add API key / Add Credential (samma som på provider-formuläret) ─

    def action_add_api_key(self):
        """Öppna wizarden för att registrera en provider API-nyckel i Keykeep."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bifrost.provider.api.key.wizard',
            'name': 'Add Provider API Key',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_provider_id': self.partner_id.id},
        }

    def action_add_credential(self):
        """Öppna wizarden för att registrera login-credentials / email-link."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bifrost.provider.credential.wizard',
            'name': 'Add Provider Credential',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_provider_id': self.partner_id.id},
        }
