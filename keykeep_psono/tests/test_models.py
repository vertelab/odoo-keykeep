# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Model tests — zero-knowledge guarantees and lifecycle rules.

Verifies: token never stores the clear key (only sha512), secret
create/update auto-snapshots history, vault user is tied 1:1 to res.users.
"""

from odoo.tests.common import TransactionCase

from .. import crypto
from ..models.psono_token import KeykeepPsonoToken


class TestPsonoModels(TransactionCase):
    def setUp(self):
        super().setUp()
        # Use a dedicated fresh res.users so tests are isolated from existing
        # vault users in the database.
        self.odoo_user = self.env["res.users"].create(
            {
                "name": "Vault Test User",
                "login": "vaulttest%d@test.local" % self.env["res.users"].search_count([]),
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.psono_user = (
            self.env["keykeep.psono.user"]
            .sudo()
            .create(
                {
                    "user_id": self.odoo_user.id,
                    "username": self.odoo_user.login,
                    "email": self.odoo_user.login,
                    "authkey": "$2b$12$abcdefghijklmnopqrstuv",  # dummy bcrypt
                    "public_key": crypto.generate_box_keypair()["public"],
                    "private_key": crypto.secretbox_key(),
                    "private_key_nonce": crypto.secretbox_nonce(),
                    "secret_key": crypto.secretbox_key(),
                    "secret_key_nonce": crypto.secretbox_nonce(),
                    "user_sauce": crypto.secretbox_nonce(),
                    "is_email_active": True,
                }
            )
        )

    def test_token_stores_hash_not_clear(self):
        Token = self.env["keykeep.psono.token"].sudo()
        clear_key = Token.generate_clear_key()
        token = Token.create(
            {
                "key": Token.hash_key(clear_key),
                "user_id": self.psono_user.id,
                "secret_key": crypto.secretbox_key(),
                "session_key": "s" * 64,
                "user_validator": "v" * 64,
                "valid_till": "2030-01-01 00:00:00",
                "active": False,
            }
        )
        self.assertNotEqual(token.key, clear_key)
        self.assertEqual(token.key, KeykeepPsonoToken.hash_key(clear_key))

    def test_secret_history_auto_snapshot(self):
        datastore = (
            self.env["keykeep.psono.datastore"]
            .sudo()
            .create(
                {
                    "user_id": self.psono_user.id,
                    "type": "password",
                    "description": "Default",
                }
            )
        )
        secret = (
            self.env["keykeep.psono.secret"]
            .sudo()
            .create(
                {
                    "user_id": self.psono_user.id,
                    "parent_datastore_id": datastore.id,
                    "data": "ciphertext-v1",
                    "data_nonce": "nonce-v1",
                    "type": "password",
                    "link_id": "link-1",
                }
            )
        )
        self.assertEqual(len(secret.history_ids), 1)
        secret.write({"data": "ciphertext-v2", "data_nonce": "nonce-v2"})
        self.assertEqual(len(secret.history_ids), 2)
        # history stores ciphertext snapshots, never plaintext
        self.assertIn("ciphertext", secret.history_ids[0].data)

    def test_vault_user_unique_per_odoo_user(self):
        with self.cr.savepoint():
            with self.assertRaises(Exception):
                (
                    self.env["keykeep.psono.user"]
                    .sudo()
                    .create(
                        {
                            "user_id": self.odoo_user.id,
                            "username": "another@vertel.local",
                            "email": "another@vertel.local",
                        }
                    )
                )

    def test_res_users_vault_status(self):
        users = self.env["res.users"].browse(self.odoo_user.id)
        self.assertTrue(users.psono_registered)
        self.assertTrue(users.psono_verified)
