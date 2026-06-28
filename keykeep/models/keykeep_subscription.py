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
    logo_url = fields.Char(
        string="Logo URL",
        help="URL to auto-fetch the logo from (e.g. Clearbit).",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
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

    @api.depends("start_date", "renewal_frequency", "renewal_cycle")
    def _compute_next_renewal_date(self):
        """Compute next_renewal_date from start_date + frequency + cycle.
        Only computed when next_renewal_date is not manually set.
        """
        for rec in self:
            if rec.start_date and not rec.next_renewal_date:
                freq_map = {
                    "monthly": relativedelta(months=rec.renewal_cycle),
                    "quarterly": relativedelta(months=3 * rec.renewal_cycle),
                    "yearly": relativedelta(years=rec.renewal_cycle),
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

    @api.depends("next_renewal_date", "state", "active")
    def _compute_kanban_state(self):
        today = date.today()
        for rec in self:
            if rec.state != "active" or not rec.active:
                rec.kanban_state = "inactive"
            elif rec.next_renewal_date and rec.next_renewal_date < today:
                rec.kanban_state = "critical"
            elif rec.next_renewal_date and (rec.next_renewal_date - today).days <= rec.notify_days_before:
                rec.kanban_state = "warning"
            else:
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
            "view_mode": "tree,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": {"create": False},
        }

    def action_view_credentials(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Credentials"),
            "res_model": "keykeep.credential",
            "view_mode": "tree,form",
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
                self.logo_url = clearbit_url
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

    # --- Constraints ---

    @api.constrains("renewal_frequency", "renewal_cycle")
    def _check_renewal_cycle(self):
        for rec in self:
            if rec.renewal_frequency == "custom" and rec.renewal_cycle <= 0:
                raise ValidationError(_("Renewal cycle must be positive."))
