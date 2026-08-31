# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Crypto layer — the ONLY place that touches keys and primitives.

Byte-exact psono wire format (spike-verified against psono-server 7.3.6):

- SecretBox (XSalsa20-Poly1305): authenticated symmetric encryption.
  Wire format: {"nonce": hex(24 bytes), "text": hex(ciphertext)}.
- Box (Curve25519-XSalsa20-Poly1305): asymmetric encryption for login.
  Same {"nonce": hex, "text": hex} wire format.
- SigningKey (Ed25519): /info/ signature. The server identity PRIVATE_KEY
  bytes double as the Ed25519 seed (psono's generate_signature pattern).
"""

import binascii

import nacl.secret
import nacl.public
import nacl.signing
import nacl.encoding
import nacl.utils


# ── Symmetric (SecretBox) ──────────────────────────────────────────

def encrypt_symmetric(secret_key_hex, msg):
    """Encrypt bytes with a hex secret key. Returns {"nonce": hex, "text": hex}."""
    nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
    secret_box = nacl.secret.SecretBox(bytes.fromhex(secret_key_hex))
    encrypted = secret_box.encrypt(msg, nonce)
    text = encrypted[nacl.secret.SecretBox.NONCE_SIZE:]
    return {
        "nonce": nonce.hex(),
        "text": text.hex(),
    }


def decrypt_symmetric(secret_key_hex, nonce_hex, text_hex):
    """Decrypt a {"nonce": hex, "text": hex} payload. Returns bytes.
    Raises nacl.exceptions.CryptoError on invalid ciphertext."""
    secret_box = nacl.secret.SecretBox(bytes.fromhex(secret_key_hex))
    return secret_box.decrypt(bytes.fromhex(text_hex), bytes.fromhex(nonce_hex))


def secretbox_key():
    """Generate a fresh 32-byte SecretBox key (hex)."""
    return nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE).hex()


def secretbox_nonce():
    return nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE).hex()


def generate_box_keypair():
    """Generate a fresh Curve25519 keypair for a login session.
    Returns {"private": hex, "public": hex}."""
    box = nacl.public.PrivateKey.generate()
    return {
        "private": box.encode(encoder=nacl.encoding.HexEncoder).decode(),
        "public": box.public_key.encode(encoder=nacl.encoding.HexEncoder).decode(),
    }


# ── Asymmetric (Box) ───────────────────────────────────────────────

def box_encrypt(private_key_hex, public_key_hex, msg, nonce=None):
    """Encrypt bytes with Box(private, remote_public).
    Returns {"nonce": hex, "text": hex}."""
    nonce = nonce or nacl.utils.random(nacl.public.Box.NONCE_SIZE)
    box = nacl.public.Box(
        nacl.public.PrivateKey(bytes.fromhex(private_key_hex)),
        nacl.public.PublicKey(bytes.fromhex(public_key_hex)),
    )
    encrypted = box.encrypt(msg, nonce)
    text = encrypted[nacl.public.Box.NONCE_SIZE:]
    return {
        "nonce": nonce.hex(),
        "text": text.hex(),
    }


def box_decrypt(private_key_hex, public_key_hex, nonce_hex, text_hex):
    """Decrypt a Box payload. Returns bytes."""
    box = nacl.public.Box(
        nacl.public.PrivateKey(bytes.fromhex(private_key_hex)),
        nacl.public.PublicKey(bytes.fromhex(public_key_hex)),
    )
    return box.decrypt(bytes.fromhex(text_hex), bytes.fromhex(nonce_hex))


# ── Signing (Ed25519, /info/ TOFU) ─────────────────────────────────

def sign_info(private_key_hex, info_json):
    """Sign the /info/ JSON string, exactly like psono's generate_signature().

    signature = first 128 hex chars of the Ed25519 signature (512 bits).
    verify_key = hex of the Ed25519 verify key (the client's TOFU fingerprint).
    """
    signing_box = nacl.signing.SigningKey(bytes.fromhex(private_key_hex))
    verify_key = signing_box.verify_key.encode(encoder=nacl.encoding.HexEncoder)
    signature = binascii.hexlify(signing_box.sign(info_json.encode()))[:128]
    return {
        "info": info_json,
        "signature": signature.decode("ascii"),
        "verify_key": verify_key.decode("ascii"),
    }
