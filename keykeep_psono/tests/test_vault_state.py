# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Vault lifecycle state tests (design D5).

vault_state is a derived, non-writable summary:

    none ──register──► pending ──verify──► ready ──used──► active

psono_registered / psono_verified keep their original meaning and must never
contradict the state.
"""

import uuid

from odoo.tests.common import TransactionCase

from .. import crypto


class TestVaultState(TransactionCase):
    def setUp(self):
        super().setUp()
        self.odoo_user = self.env["res.users"].create(
            {
                "name": "State Test User",
                "login": "statetest-%s@test.local" % uuid.uuid4().hex[:12],
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def _make_vault(self, verified=False):
        return (
            self.env["keykeep.psono.user"]
            .sudo()
            .create(
                {
                    "user_id": self.odoo_user.id,
                    "username": self.odoo_user.login,
                    "email": self.odoo_user.login,
                    "authkey": "$2b$12$abcdefghijklmnopqrstuv",
                    "public_key": crypto.generate_box_keypair()["public"],
                    "user_sauce": crypto.secretbox_nonce(),
                    "is_email_active": verified,
                }
            )
        )

    # ── state transitions ─────────────────────────────────────────

    def test_state_none_without_vault(self):
        self.assertEqual(self.odoo_user.psono_vault_state, "none")
        self.assertFalse(self.odoo_user.psono_registered)

    def test_state_pending_when_unverified(self):
        self._make_vault(verified=False)
        self.odoo_user.invalidate_recordset()
        self.assertEqual(self.odoo_user.psono_vault_state, "pending")
        self.assertTrue(self.odoo_user.psono_registered)
        self.assertFalse(self.odoo_user.psono_verified)

    def test_state_ready_when_verified_but_unused(self):
        self._make_vault(verified=True)
        self.odoo_user.invalidate_recordset()
        self.assertEqual(self.odoo_user.psono_vault_state, "ready")
        self.assertTrue(self.odoo_user.psono_verified)

    def test_state_active_after_first_secret(self):
        vault = self._make_vault(verified=True)
        datastore = (
            self.env["keykeep.psono.datastore"]
            .sudo()
            .create(
                {
                    "user_id": vault.id,
                    "type": "password",
                    "description": "Default",
                }
            )
        )
        self.env["keykeep.psono.secret"].sudo().create(
            {
                "user_id": vault.id,
                "parent_datastore_id": datastore.id,
                "data": "ct",
                "data_nonce": "n",
                "type": "password",
                "link_id": "l1",
            }
        )
        self.odoo_user.invalidate_recordset()
        self.assertEqual(self.odoo_user.psono_vault_state, "active")

    def test_state_active_after_first_token(self):
        vault = self._make_vault(verified=True)
        Token = self.env["keykeep.psono.token"].sudo()
        clear = Token.generate_clear_key()
        Token.create(
            {
                "key": Token.hash_key(clear),
                "user_id": vault.id,
                "secret_key": crypto.secretbox_key(),
                "session_key": "s" * 64,
                "user_validator": "v" * 64,
                "valid_till": "2030-01-01 00:00:00",
                "active": False,
            }
        )
        self.odoo_user.invalidate_recordset()
        self.assertEqual(self.odoo_user.psono_vault_state, "active")

    # ── invariants ────────────────────────────────────────────────

    def test_state_is_not_writable(self):
        """The state summarises data it does not own — it must be read-only."""
        field = self.env["res.users"]._fields["psono_vault_state"]
        self.assertFalse(field.store)
        self.assertTrue(field.compute)
        self.assertFalse(field.readonly is False and field.inverse)

    def test_flags_never_contradict_state(self):
        """none ⇒ not registered; registered ⇒ state != none."""
        self.assertEqual(self.odoo_user.psono_vault_state, "none")
        self.assertFalse(self.odoo_user.psono_registered)

        self._make_vault(verified=True)
        self.odoo_user.invalidate_recordset()
        self.assertNotEqual(self.odoo_user.psono_vault_state, "none")
        self.assertTrue(self.odoo_user.psono_registered)

    def test_recovery_flags_default_false(self):
        self._make_vault(verified=True)
        self.odoo_user.invalidate_recordset()
        self.assertFalse(self.odoo_user.psono_recovery_registered)
        self.assertFalse(self.odoo_user.psono_recovery_created_at)
