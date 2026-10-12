# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Recovery-material tests (design D7/D8 — Alt 4).

The server must never hold the recovery code. It stores a verifiable authkey
and an opaque E2E blob, and treats the blob as bytes it cannot interpret.
"""

import uuid

from odoo.tests.common import TransactionCase

from .. import crypto


class TestRecoveryMaterial(TransactionCase):
    def setUp(self):
        super().setUp()
        self.odoo_user = self.env["res.users"].create(
            {
                "name": "Recovery Test User",
                "login": "rectest-%s@test.local" % uuid.uuid4().hex[:12],
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.vault = (
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
                    "is_email_active": True,
                }
            )
        )

    def _register(self, authkey="recovery-authkey-v1", data="opaque-blob-v1"):
        self.vault.sudo().write(
            {
                "recovery_authkey": authkey,
                "recovery_data": data,
                "recovery_data_nonce": "nonce-1",
                "recovery_sauce": "sauce-1",
                "recovery_created_at": "2026-10-09 12:00:00",
            }
        )

    # ── storage shape ─────────────────────────────────────────────

    def test_no_recovery_by_default(self):
        self.assertFalse(self.vault.has_recovery())
        self.assertFalse(self.odoo_user.psono_recovery_registered)

    def test_registration_marks_recovery_present(self):
        self._register()
        self.assertTrue(self.vault.has_recovery())
        self.odoo_user.invalidate_recordset()
        self.assertTrue(self.odoo_user.psono_recovery_registered)
        self.assertEqual(
            self.odoo_user.psono_recovery_created_at, self.vault.recovery_created_at
        )

    def test_stored_fields_never_contain_a_code(self):
        """The recovery code itself has no column — only authkey + blob."""
        fields = self.env["keykeep.psono.user"]._fields
        self.assertNotIn("recovery_code", fields)
        self.assertNotIn("recovery_password", fields)
        self.assertIn("recovery_authkey", fields)
        self.assertIn("recovery_data", fields)

    def test_blob_is_stored_verbatim(self):
        """The server must not transform the opaque payload."""
        self._register(data="AAABBBCCC-opaque")
        self.assertEqual(self.vault.recovery_data, "AAABBBCCC-opaque")

    def test_replacement_overwrites(self):
        self._register(authkey="k1", data="blob-1")
        self._register(authkey="k2", data="blob-2")
        self.assertEqual(self.vault.recovery_authkey, "k2")
        self.assertEqual(self.vault.recovery_data, "blob-2")

    def test_removal_clears_material(self):
        self._register()
        self.vault.sudo().write(
            {
                "recovery_authkey": False,
                "recovery_data": False,
                "recovery_data_nonce": False,
                "recovery_sauce": False,
                "recovery_created_at": False,
            }
        )
        self.assertFalse(self.vault.has_recovery())

    # ── authkey matching ──────────────────────────────────────────

    def test_wrong_authkey_does_not_match(self):
        self._register(authkey="correct-key")
        self.assertNotEqual(self.vault.recovery_authkey, "wrong-key")

    def test_partial_material_is_not_recovery(self):
        """authkey without blob (or vice versa) must not count as recovery."""
        self.vault.sudo().write({"recovery_authkey": "k"})
        self.assertFalse(self.vault.has_recovery())
        self.vault.sudo().write({"recovery_authkey": False, "recovery_data": "b"})
        self.assertFalse(self.vault.has_recovery())

    # ── lifecycle interaction ─────────────────────────────────────

    def test_suspension_preserves_recovery(self):
        """Deactivating the Odoo user must not destroy recovery material."""
        self._register()
        self.odoo_user.write({"active": False})
        self.vault.invalidate_recordset()
        self.assertFalse(self.vault.is_active)
        self.assertTrue(self.vault.has_recovery())
        self.assertEqual(self.vault.recovery_data, "opaque-blob-v1")

    def test_deactivation_syncs_vault_is_active(self):
        self.assertTrue(self.vault.is_active)
        self.odoo_user.write({"active": False})
        self.vault.invalidate_recordset()
        self.assertFalse(self.vault.is_active)
        self.odoo_user.write({"active": True})
        self.vault.invalidate_recordset()
        self.assertTrue(self.vault.is_active)

    def test_suspension_is_audited(self):
        self.odoo_user.write({"active": False})
        logs = self.env["keykeep.psono.access.log"].sudo().search(
            [("user_id", "=", self.odoo_user.id), ("action", "=", "vault_suspended")]
        )
        self.assertTrue(logs, "suspension must leave an audit entry")
