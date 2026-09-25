# Copyright (C) 2026 Vertel AB — Keykeep access-rights tests.
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccessRights(TransactionCase):
    """Keykeep access model: menu gating, admin automation, user team right."""

    def test_menu_root_requires_user_group(self):
        menu = self.env.ref('keykeep.menu_keykeep_root')
        self.assertTrue(
            self.env.ref('keykeep.group_user') in menu.groups_id,
            'Keykeep root menu must be gated at Keykeep User')

    def test_settings_user_is_keykeep_admin(self):
        settings = self.env.ref('base.group_system')
        self.assertIn(
            self.env.ref('keykeep.group_admin').id,
            settings.implied_ids.ids,
            'Settings group must imply Keykeep Admin')

    def test_user_has_readonly_credential_access(self):
        """Keykeep User gets read-only credential + reveal read (team right),
        never write/create/unlink."""
        csv = self.env['ir.model.access'].search([
            ('group_id', '=', self.env.ref('keykeep.group_user').id),
            ('model_id.model', '=', 'keykeep.credential'),
        ])
        self.assertTrue(csv, 'Keykeep User needs keykeep.credential access rows')
        self.assertTrue(all(a.perm_read for a in csv))
        self.assertTrue(all(not a.perm_write and not a.perm_create
                            and not a.perm_unlink for a in csv))
        reveal = self.env['ir.model.access'].search([
            ('group_id', '=', self.env.ref('keykeep.group_user').id),
            ('model_id.model', '=', 'keykeep.credential.reveal'),
        ])
        self.assertTrue(reveal and all(r.perm_read for r in reveal))

    def test_user_credential_scoped_by_company_rule(self):
        rule = self.env.ref('keykeep.rule_credential_user_company')
        self.assertIn(self.env.ref('keykeep.group_user').id, rule.groups.ids)
        self.assertIn("user.company_id", rule.domain_force)
