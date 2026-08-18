# Copyright (C) 2026 Vertel Sverige AB (<https://vertel.se>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ──────────────────────────────────────────────────────────────────
    # Background Jobs — cron administration (same pattern as ai_agent_core)
    # ──────────────────────────────────────────────────────────────────

    keykeep_cron_line_ids = fields.One2many(
        'keykeep.cron.line', 'settings_id', string='Cron-rader')

    @api.model
    def get_values(self):
        res = super().get_values()
        crons = self.env['ir.cron'].search(
            [('cron_name', 'in', KEYKEEP_CRON_NAMES)], order='cron_name')
        res['keykeep_cron_line_ids'] = [(0, 0, {
            'cron_id': cron.id,
            'cron_active': cron.active,
            'cron_interval_number': cron.interval_number,
            'cron_interval_type': cron.interval_type,
        }) for cron in crons]
        return res

    def set_values(self):
        super().set_values()
        for line in self.keykeep_cron_line_ids:
            if line.cron_id:
                line.cron_id.write({
                    'active': line.cron_active,
                    'interval_number': line.cron_interval_number,
                    'interval_type': line.cron_interval_type,
                })


KEYKEEP_CRON_NAMES = [
    'Keykeep: Update Renewal Dates',
    'Keykeep: Send Renewal Notifications',
    'Keykeep: Check Credential Expiry',
    'Keykeep: Check Credential Rotation Health',
    'Keykeep: Cleanup Old Access Logs',
    'Keykeep: Generate Cost Forecast',
]


class KeykeepCronLine(models.TransientModel):
    """Per-cron konfigurationsrad i Background Jobs-blocket."""
    _name = 'keykeep.cron.line'
    _description = 'Keykeep cron configuration line'

    settings_id = fields.Many2one('res.config.settings', ondelete='cascade')
    cron_id = fields.Many2one('ir.cron', string='Cron', required=True,
                              ondelete='cascade')
    cron_name = fields.Char(related='cron_id.cron_name', string='Namn',
                            readonly=True)
    cron_active = fields.Boolean(string='Aktiv', default=True)
    cron_interval_number = fields.Integer(string='Intervall', default=1)
    cron_interval_type = fields.Selection([
        ('minutes', 'Minuter'),
        ('hours', 'Timmar'),
        ('days', 'Dagar'),
        ('weeks', 'Veckor'),
        ('months', 'Months'),
    ], string='Period', default='days')
    cron_lastcall = fields.Datetime(related='cron_id.lastcall',
                                    string='Last run', readonly=True)
    cron_failure_count = fields.Integer(related='cron_id.failure_count',
                                        string='Fel', readonly=True)
    cron_code = fields.Text(related='cron_id.code', string='Metod',
                            readonly=True)

    def action_run_now(self):
        """Run the cron immediately."""
        self.ensure_one()
        if not self.cron_id:
            return False
        model_name = self.cron_id.model
        code = self.cron_id.code
        if model_name and code:
            model = self.env[model_name]
            if code.startswith('model.'):
                method = code[len('model.'):]
                if hasattr(model, method):
                    getattr(model, method)()
        self.cron_id._trigger(at=fields.Datetime.now())
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cron triggad',
                'message': f'{self.cron_name} is running now.',
                'type': 'success',
            },
        }
