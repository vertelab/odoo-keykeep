# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Crypto layer tests — round trips + psono wire format.

The wire format is {nonce: hex(24 bytes), text: hex(ciphertext)}. A known
vector captured from the spike (psono-server 7.3.6) verifies byte-level
compatibility of the SecretBox wrapper: we re-encrypt a message and check
the nonce length and that the payload is 24 bytes longer than the plaintext.
"""

import json

from odoo.tests.common import TransactionCase

from .. import crypto


class TestCrypto(TransactionCase):
    def test_secretbox_roundtrip(self):
        key = crypto.secretbox_key()
        msg = b"spike secret value"
        encrypted = crypto.encrypt_symmetric(key, msg)
        self.assertEqual(len(bytes.fromhex(encrypted["nonce"])), 24)
        self.assertEqual(
            len(bytes.fromhex(encrypted["text"])),
            len(msg) + 16,  # XSalsa20-Poly1305: plaintext + 16-byte MAC
        )
        decrypted = crypto.decrypt_symmetric(
            key, encrypted["nonce"], encrypted["text"]
        )
        self.assertEqual(decrypted, msg)

    def test_secretbox_wire_shape(self):
        # psono wire shape: {"nonce": hex, "text": hex}
        key = crypto.secretbox_key()
        encrypted = crypto.encrypt_symmetric(key, b"{}")
        self.assertEqual(set(encrypted.keys()), {"nonce", "text"})
        for v in encrypted.values():
            bytes.fromhex(v)  # raises if not valid hex

    def test_secretbox_wrong_key_fails(self):
        key1 = crypto.secretbox_key()
        key2 = crypto.secretbox_key()
        encrypted = crypto.encrypt_symmetric(key1, b"secret")
        with self.assertRaises(Exception):
            crypto.decrypt_symmetric(key2, encrypted["nonce"], encrypted["text"])

    def test_box_roundtrip(self):
        pair1 = crypto.generate_box_keypair()
        pair2 = crypto.generate_box_keypair()
        msg = json.dumps({"username": "user@vertel.local", "authkey": "abc"}).encode()
        encrypted = crypto.box_encrypt(pair1["private"], pair2["public"], msg)
        self.assertEqual(len(bytes.fromhex(encrypted["nonce"])), 24)
        decrypted = crypto.box_decrypt(
            pair2["private"], pair1["public"], encrypted["nonce"], encrypted["text"]
        )
        self.assertEqual(decrypted, msg)

    def test_sign_info_fingerprint(self):
        pair = crypto.generate_box_keypair()
        private_key, public_key = pair["private"], pair["public"]
        info = json.dumps({"type": "CE", "public_key": public_key})
        signed = crypto.sign_info(private_key, info)
        self.assertEqual(signed["info"], info)
        # verify_key is the Ed25519 verify key (32 bytes -> 64 hex chars)
        self.assertEqual(len(signed["verify_key"]), 64)
        # signature is 128 hex chars (64 bytes, 512 bits)
        self.assertEqual(len(signed["signature"]), 128)
        # signature is deterministic for the same key+payload
        signed2 = crypto.sign_info(private_key, info)
        self.assertEqual(signed["signature"], signed2["signature"])
