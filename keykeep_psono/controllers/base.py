# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Base helpers for the psono protocol controllers.

Wire contract (spike-verified against psono-server 7.3.6):
- Unauthenticated endpoints: plaintext JSON.
- Authenticated endpoints: request bodies SecretBox-encrypted with the token's
  session secret key as {"nonce": hex, "text": hex}; responses always
  {"data": {"text": hex, "nonce": hex}}.
- Errors: psono-style {"non_field_errors": [...]} / {"field": [...]}.
"""

import hashlib
import json
import logging

import werkzeug

from odoo import http
from odoo import fields as odoo_fields

from ..util import parse_iso_datetime as _parse_iso_datetime

from .. import crypto

_logger = logging.getLogger(__name__)


class PsonoError(Exception):
    """Raised by handlers; converted to a psono-compatible response."""

    def __init__(self, message, status=400, field=None, token=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field
        self.token = token

    def payload(self):
        if self.field:
            return {self.field: [self.message]}
        return {"non_field_errors": [self.message]}

    def to_response(self):
        if self.token is not None:
            return PsonoBase.encrypted_response(self.token, self.payload(), self.status)
        return PsonoBase.plain_response(self.payload(), self.status)


class PsonoBase(object):
    """Mixin providing response helpers and token authentication."""

    # ── responses ─────────────────────────────────────────────────

    @staticmethod
    def plain_response(payload, status=200):
        return werkzeug.wrappers.Response(
            json.dumps(payload),
            status=status,
            content_type="application/json",
        )

    @staticmethod
    def encrypted_response(token, payload, status=200):
        # psono wire contract: the raw response body IS the encrypted payload
        # {text: hex, nonce: hex}. The client adds its own "data" wrapper.
        encrypted = crypto.encrypt_symmetric(
            token.secret_key, json.dumps(payload).encode()
        )
        return werkzeug.wrappers.Response(
            json.dumps(encrypted),
            status=status,
            content_type="application/json",
        )

    @staticmethod
    def parse_json_body():
        raw = http.request.httprequest.get_data(as_text=True)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise PsonoError("INVALID_JSON", status=400) from exc

    # ── authentication ────────────────────────────────────────────

    @staticmethod
    def _header_authorization():
        return http.request.httprequest.headers.get("Authorization", "")

    def _require_token(self, allow_inactive=False):
        """Authenticate the request and return the token record.

        Raises PsonoError with a psono-compatible message on any failure.
        Enforces replay protection + device fingerprint when the token
        carries a client_date / device_fingerprint (design D6).
        """
        auth_parts = self._header_authorization().split()
        if not auth_parts or auth_parts[0].lower() != "token":
            raise PsonoError(
                "Invalid token header. No token header present.", status=401
            )
        if len(auth_parts) != 2:
            raise PsonoError(
                "Invalid token header. Incorrect format in token header.",
                status=401,
            )
        clear_key = auth_parts[1]
        token_hash = hashlib.sha512(clear_key.encode()).hexdigest()
        token = (
            http.request.env["keykeep.psono.token"]
            .sudo()
            .with_context(active_test=False)
            .search([("key", "=", token_hash)], limit=1)
        )
        if not token or not token.user_id:
            raise PsonoError("Invalid token or not yet activated.", status=401)
        if not allow_inactive and not token.active:
            raise PsonoError("Invalid token or not yet activated.", status=401)
        if token.is_expired():
            raise PsonoError("Invalid token or not yet activated.", status=401)

        # Replay + device protection (only enforced when the token carries
        # the metadata, matching psono's conditional validation).
        if token.device_fingerprint or token.client_date:
            validator = self._decrypt_validator(token)
            self._check_replay(token, validator)

        return token

    def _decrypt_validator(self, token):
        raw = http.request.httprequest.headers.get("Authorization-Validator", "")
        if not raw:
            raise PsonoError(
                "Invalid token header. Incorrect format in token header.",
                status=401,
            )
        try:
            validator = json.loads(raw)
            decrypted = crypto.decrypt_symmetric(
                token.secret_key, validator["nonce"], validator["text"]
            )
            return json.loads(decrypted.decode())
        except (KeyError, ValueError) as exc:
            raise PsonoError(
                "Invalid token header. Incorrect format in token header.",
                status=401,
            ) from exc

    def _check_replay(self, token, validator):
        request_date = validator.get("request_time") or validator.get("request_date")
        if not request_date:
            self._reject_token(token, "Replay Protection: request_time missing")
        try:
            request_date = _parse_iso_datetime(request_date)
        except (ValueError, TypeError):
            self._reject_token(token, "Replay Protection: invalid request_time")

        now = odoo_fields.Datetime.now()
        client_date = token.client_date or token.create_date
        create_date = token.create_date
        time_difference = abs(
            ((client_date - create_date) - (request_date - now)).total_seconds()
        )
        window = int(
            http.request.env["ir.config_parameter"]
            .sudo()
            .get_param("keykeep_psono.replay_window_seconds", "20")
        )
        if time_difference > window:
            self._reject_token(
                token, "Replay Protection: Time difference too big"
            )

        request_fingerprint = validator.get(
            "request_device_session",
            validator.get("request_device_fingerprint"),
        )
        if not request_fingerprint or request_fingerprint != token.device_fingerprint:
            self._reject_token(
                token, "Device Fingerprint Protection: mismatch"
            )

    def _reject_token(self, token, reason):
        token.sudo().unlink()
        raise PsonoError("Invalid token or not yet activated.", status=401)

    def _decrypt_body(self, token):
        """Decrypt an authenticated request body (SecretBox)."""
        body = self.parse_json_body()
        try:
            decrypted = crypto.decrypt_symmetric(
                token.secret_key, body["nonce"], body["text"]
            )
        except (KeyError, ValueError) as exc:
            raise PsonoError("INVALID_BODY", status=400) from exc
        try:
            return json.loads(decrypted.decode())
        except ValueError as exc:
            raise PsonoError("INVALID_BODY", status=400) from exc

    # ── audit ─────────────────────────────────────────────────────

    def _audit(self, user, action, detail=None):
        try:
            ip_address = http.request.httprequest.remote_addr
        except Exception:  # noqa: BLE001
            ip_address = None
        return (
            http.request.env["keykeep.psono.access.log"]
            .sudo()
            .create(
                {
                    "user_id": user.id if user else False,
                    "action": action,
                    "detail": detail,
                    "ip_address": ip_address,
                }
            )
        )
