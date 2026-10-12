# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""psono protocol controllers under /keykeep/psono/*.

Route/contract fidelity is spike-verified against psono-server 7.3.6:
- GET  /info/                            signed TOFU info (required before login)
- POST /authentication/prelogin/         hashing params (fake for unknown users)
- POST /authentication/login/            Box key exchange -> token + session
- POST /authentication/register/         client-generated keys (Odoo-session gated)
- POST /authentication/verify-email/     activation code -> email verified
- POST /authentication/activate-token/   token activation (user_validator proof)
- POST /authentication/logout/           delete token
- GET  /user/status/                     status payload
- GET  /avatar/                          {"avatars": []}
- GET  /datastore/ | PUT /datastore/     list / create
- GET  /datastore/<id>/                  detail
- PUT/POST /secret/, GET /secret/<id>/   secret CRUD
- GET  /secret/history/<id>/             version history
- GET  /share/right/                     {"share_rights": []}
"""

import json
import logging
import secrets
from datetime import timedelta

import bcrypt
import werkzeug

from odoo import http
from odoo import fields as odoo_fields

from ..util import parse_iso_datetime as _parse_iso_datetime

from .. import crypto
from ..config import get_server_keys
from .base import PsonoBase, PsonoError

_logger = logging.getLogger(__name__)


class PsonoController(PsonoBase, http.Controller):
    # ── helpers ───────────────────────────────────────────────────

    def _get_psono_user_by_username(self, username):
        return (
            http.request.env["keykeep.psono.user"]
            .sudo()
            .search([("username", "=", username)], limit=1)
        )

    def _info_payload(self):
        private_key, public_key = get_server_keys()
        info = {
            "version": "7.3.6 (Odoo keykeep_psono)",
            "api": 1,
            "log_audit": False,
            "public_key": public_key,
            "authentication_methods": ["AUTHKEY"],
            "domain_synonyms": [],
            "excluded_domains": [],
            "web_client": "/keykeep/psono/web/",
            "management": False,
            "files": False,
            "allowed_second_factors": [],
            "type": "CE",
            "avatar_dimension_x": 256,
            "avatar_dimension_y": 256,
            "avatar_max_size_kb": 100,
            "multifactor_enabled": False,
        }
        return crypto.sign_info(private_key, json.dumps(info))

    def _default_hashing(self, user):
        if user:
            return {
                "hashing_algorithm": user.hashing_algorithm or "scrypt",
                "hashing_parameters": user.hashing_parameters
                or {"u": 14, "r": 8, "p": 1, "l": 64},
            }
        return {
            "hashing_algorithm": "scrypt",
            "hashing_parameters": {"u": 14, "r": 8, "p": 1, "l": 64},
        }

    def _is_session_bound_to(self, user):
        """True when this request carries an Odoo session for `user` (D6).

        This is the only reliable signal that the caller is the Odoo-embedded
        web client rather than a sessionless client (browser extension).
        auth="none" routes can still read the session.
        """
        uid = http.request.session.uid
        return bool(uid) and user and user.user_id.id == uid

    def _email_verification_required(self, user):
        """Whether this login must be blocked for an unverified vault (D6).

        Sessionless clients (the browser extension) ALWAYS require
        verification — it is their only identity bridge. Session-bound
        clients may skip it when the operator allows it.
        """
        if not self._is_session_bound_to(user):
            return True
        allow = (
            http.request.env["ir.config_parameter"]
            .sudo()
            .get_param("keykeep_psono.require_email_verification_for_web", "1")
        )
        return str(allow).strip().lower() in ("1", "true", "yes", "on")

    def _token_valid_seconds(self):
        param = (
            http.request.env["ir.config_parameter"]
            .sudo()
            .get_param("keykeep_psono.token_valid_seconds", "2592000")
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            return 2592000

    def _create_token(self, user, device_fingerprint, device_description, client_date):
        Token = http.request.env["keykeep.psono.token"].sudo()
        clear_key = Token.generate_clear_key()
        secret_key = crypto.secretbox_key()
        valid_till = odoo_fields.Datetime.now() + timedelta(
            seconds=self._token_valid_seconds()
        )
        token = Token.create(
            {
                "key": Token.hash_key(clear_key),
                "user_id": user.id,
                "secret_key": secret_key,
                "session_key": secrets.token_hex(32),
                "user_validator": secrets.token_hex(32),
                "device_fingerprint": device_fingerprint or "",
                "device_description": device_description or "",
                "client_date": client_date,
                "valid_till": valid_till,
                "active": False,
            }
        )
        return token, clear_key

    # ── info / prelogin / login ───────────────────────────────────

    @http.route("/keykeep/psono/info/", type="http", auth="none", csrf=False, methods=["GET"])
    def info(self, **kw):
        try:
            return self.plain_response(self._info_payload())
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/authentication/prelogin/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def prelogin(self, **kw):
        try:
            body = self.parse_json_body()
            username = (body.get("username") or "").lower().strip()
            if not username or "@" not in username:
                raise PsonoError("INVALID_USERNAME_FORMAT", status=400)
            user = self._get_psono_user_by_username(username)
            return self.plain_response(self._default_hashing(user))
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/authentication/login/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def login(self, **kw):
        try:
            body = self.parse_json_body()
            login_info = body.get("login_info", "")
            login_info_nonce = body.get("login_info_nonce", "")
            public_key = body.get("public_key", "")
            session_duration = int(body.get("session_duration") or 0)

            private_key, server_public = get_server_keys()
            try:
                decrypted = crypto.box_decrypt(
                    private_key, public_key, login_info_nonce, login_info
                )
                request_data = json.loads(decrypted.decode())
            except Exception as exc:  # noqa: BLE001
                raise PsonoError("LOGIN_INFO_CANNOT_BE_DECRYPTED", status=400) from exc

            username = (request_data.get("username") or "").lower().strip()
            authkey = request_data.get("authkey") or ""
            if not username or not authkey:
                raise PsonoError("USERNAME_OR_PASSWORD_WRONG", status=400)

            user = self._get_psono_user_by_username(username)
            if not user or not user.authkey or not self._verify_authkey(authkey, user.authkey):
                self._audit(user.user_id if user else None, "login_failed", "wrong authkey")
                raise PsonoError("USERNAME_OR_PASSWORD_WRONG", status=400)
            if not user.is_active:
                raise PsonoError("USER_DISABLED_ASK_ADMIN_TO_ENABLE", status=400)
            if not user.is_email_active and self._email_verification_required(user):
                raise PsonoError("ACCOUNT_NOT_VERIFIED", status=400)

            device_fingerprint = request_data.get("device_fingerprint", "")
            device_description = request_data.get("device_description", "")
            device_time = request_data.get("device_time") or request_data.get(
                "request_date"
            )
            client_date = None
            if device_time:
                try:
                    client_date = _parse_iso_datetime(device_time)
                except (ValueError, TypeError):
                    client_date = None

            token, clear_key = self._create_token(
                user, device_fingerprint, device_description, client_date
            )

            # Server session keypair for the Box exchange
            box = crypto.generate_box_keypair()
            server_session_private = box["private"]
            server_session_public = box["public"]

            # Encrypt the session secret key for the client
            enc_session = crypto.box_encrypt(
                server_session_private, public_key, token.secret_key.encode()
            )
            # Encrypt the user validator for the client
            enc_validator = crypto.box_encrypt(
                server_session_private, user.public_key, token.user_validator.encode()
            )

            response = {
                "token": clear_key,
                "session_key": token.session_key,
                "session_valid_till": token.valid_till.isoformat(),
                "required_multifactors": [],
                "session_public_key": server_session_public,
                "session_secret_key": enc_session["text"],
                "session_secret_key_nonce": enc_session["nonce"],
                "user_validator": enc_validator["text"],
                "user_validator_nonce": enc_validator["nonce"],
                "user": {
                    "username": user.username,
                    "language": user.language or "en",
                    "public_key": user.public_key,
                    "private_key": user.private_key,
                    "private_key_nonce": user.private_key_nonce,
                    "user_sauce": user.user_sauce,
                    "authentication": user.authentication or "AUTHKEY",
                    "hashing_algorithm": user.hashing_algorithm or "scrypt",
                    "hashing_parameters": user.hashing_parameters,
                    "require_password_change": user.require_password_change,
                },
            }

            # Encrypt the whole response with Box(server_private, client_session_public)
            enc_login_info = crypto.box_encrypt(
                private_key, public_key, json.dumps(response).encode()
            )
            self._audit(user.user_id, "login", None)
            return self.plain_response(
                {
                    "login_info": enc_login_info["text"],
                    "login_info_nonce": enc_login_info["nonce"],
                }
            )
        except PsonoError as exc:
            return exc.to_response()

    def _verify_authkey(self, authkey, stored_hash):
        try:
            return bcrypt.checkpw(authkey.encode(), stored_hash.encode())
        except (ValueError, TypeError):
            return False

    # ── registration / verification ───────────────────────────────

    @http.route(
        "/keykeep/psono/authentication/register/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def register(self, **kw):
        try:
            uid = http.request.session.uid
            allow = (
                http.request.env["ir.config_parameter"]
                .sudo()
                .get_param("keykeep_psono.allow_registration", "1")
            )
            if not uid or allow != "1":
                raise PsonoError("REGISTRATION_HAS_BEEN_DISABLED", status=400)
            odoo_user = http.request.env["res.users"].sudo().browse(uid)
            if not odoo_user.exists() or odoo_user.share:
                raise PsonoError("REGISTRATION_HAS_BEEN_DISABLED", status=400)

            body = self.parse_json_body()
            username = (body.get("username") or "").lower().strip()
            email = (body.get("email") or "").lower().strip()
            authkey = body.get("authkey") or ""
            if not username or not email or not authkey:
                raise PsonoError("REGISTRATION_INCOMPLETE", status=400)

            if self._get_psono_user_by_username(username):
                raise PsonoError("USERNAME_ALREADY_EXISTS", field="username", status=400)

            user = http.request.env["keykeep.psono.user"].sudo().create(
                {
                    "user_id": odoo_user.id,
                    "username": username,
                    "email": email,
                    "email_bcrypt": bcrypt.hashpw(email.encode(), bcrypt.gensalt()).decode(),
                    "authkey": bcrypt.hashpw(authkey.encode(), bcrypt.gensalt()).decode(),
                    "public_key": body.get("public_key", ""),
                    "private_key": body.get("private_key", ""),
                    "private_key_nonce": body.get("private_key_nonce", ""),
                    "secret_key": body.get("secret_key", ""),
                    "secret_key_nonce": body.get("secret_key_nonce", ""),
                    "user_sauce": body.get("user_sauce", ""),
                    "hashing_algorithm": body.get("hashing_algorithm") or "scrypt",
                    "hashing_parameters": body.get("hashing_parameters")
                    or {"u": 14, "r": 8, "p": 1, "l": 64},
                    "is_email_active": False,
                }
            )
            user._log("register")
            activation = self._issue_activation_code(user)
            self._send_activation_link(user, activation)
            return self.plain_response({})
        except PsonoError as exc:
            return exc.to_response()

    def _issue_activation_code(self, user):
        import hashlib

        code = secrets.token_hex(48)
        user.sudo().write(
            {
                "activation_code": hashlib.sha256(code.encode()).hexdigest(),
                "activation_code_expire": odoo_fields.Datetime.now()
                + timedelta(hours=72),
            }
        )
        return code

    def _send_activation_link(self, user, code):
        base_url = (
            http.request.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", "https://ledningssystem.vertel.se")
        )
        link = "%s/keykeep/psono/web/activate.html#!/activation-code/%s" % (
            base_url,
            code,
        )
        _logger.warning(
            "keykeep_psono: activation link for %s: %s", user.username, link
        )
        try:
            partner = user.user_id.partner_id
            mail = (
                http.request.env["mail.mail"]
                .sudo()
                .create(
                    {
                        "subject": "Activate your personal vault",
                        "body_html": (
                            "<p>Activate your personal password vault:</p>"
                            '<p><a href="%s">%s</a></p>' % (link, link)
                        ),
                        "email_to": partner.email or user.user_id.login,
                    }
                )
            )
            mail.send()
        except Exception as exc:  # noqa: BLE001
            _logger.warning("keykeep_psono: could not send activation mail: %s", exc)

    @http.route(
        "/keykeep/psono/authentication/verify-email/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def verify_email(self, **kw):
        try:
            import hashlib

            body = self.parse_json_body()
            code = (body.get("activation_code") or "").strip()
            if not code:
                raise PsonoError("ACTIVATION_CODE_INCORRECT", status=400)
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            user = (
                http.request.env["keykeep.psono.user"]
                .sudo()
                .search(
                    [
                        ("activation_code", "=", code_hash),
                        ("is_email_active", "=", False),
                    ],
                    limit=1,
                )
            )
            if not user:
                raise PsonoError("ACTIVATION_CODE_INCORRECT", status=400)
            user.write(
                {
                    "is_email_active": True,
                    "activation_code": False,
                    "activation_code_expire": False,
                }
            )
            user._log("verify_email")
            return self.plain_response({"success": "Successfully activated."})
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/authentication/activate-token/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def activate_token(self, **kw):
        try:
            token = self._require_token(allow_inactive=True)
            body = self._decrypt_body(token)
            verification = body.get("verification", "")
            verification_nonce = body.get("verification_nonce", "")
            if not verification or not verification_nonce:
                raise PsonoError("VERIFICATION_CODE_INCORRECT", status=400, token=token)
            try:
                decrypted = crypto.decrypt_symmetric(
                    token.secret_key, verification_nonce, verification
                ).decode()
            except Exception as exc:  # noqa: BLE001
                raise PsonoError(
                    "VERIFICATION_CODE_INCORRECT", status=400, token=token
                ) from exc
            if not secrets.compare_digest(token.user_validator or "", decrypted):
                raise PsonoError(
                    "VERIFICATION_CODE_INCORRECT", status=400, token=token
                )
            token.write({"active": True, "user_validator": False})
            self._audit(token.user_id.user_id, "activate_token", None)
            user = token.user_id
            payload = {
                "user": {
                    "id": str(user.id),
                    "authentication": user.authentication or "AUTHKEY",
                    "email": user.email or "",
                    "secret_key": user.secret_key or "",
                    "secret_key_nonce": user.secret_key_nonce or "",
                    "registration_date": (
                        user.create_date.isoformat() if user.create_date else ""
                    ),
                    "require_password_change": user.require_password_change,
                }
            }
            return self.encrypted_response(token, payload)
        except PsonoError as exc:
            return exc.to_response()

    # ── logout / status / avatar / share_right ────────────────────

    @http.route(
        "/keykeep/psono/authentication/logout/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def logout(self, **kw):
        try:
            token = self._require_token()
            secret_key = token.secret_key
            self._audit(token.user_id.user_id, "logout", None)
            token.sudo().unlink()
            encrypted = crypto.encrypt_symmetric(secret_key, b"{}")
            return werkzeug.wrappers.Response(
                json.dumps(encrypted),
                status=200,
                content_type="application/json",
            )
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/user/status/",
        type="http", auth="none", csrf=False, methods=["GET"],
    )
    def user_status(self, **kw):
        try:
            token = self._require_token()
            payload = {
                "unaccepted_shares_count": 0,
                "unaccepted_groups_count": 0,
                "unaccepted_forced_groups_count": 0,
                "last_security_report_created": token.create_date.isoformat()
                if token.create_date
                else "",
            }
            return self.encrypted_response(token, payload)
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/avatar/", type="http", auth="none", csrf=False, methods=["GET"]
    )
    def avatar(self, **kw):
        try:
            token = self._require_token()
            return self.encrypted_response(token, {"avatars": []})
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/share/right/",
        type="http", auth="none", csrf=False, methods=["GET"],
    )
    def share_right(self, **kw):
        try:
            token = self._require_token()
            return self.encrypted_response(token, {"share_rights": []})
        except PsonoError as exc:
            return exc.to_response()

    # ── datastore ─────────────────────────────────────────────────

    @http.route(
        "/keykeep/psono/datastore/",
        type="http", auth="none", csrf=False, methods=["GET", "PUT", "POST"],
    )
    def datastore(self, **kw):
        try:
            token = self._require_token()
            method = http.request.httprequest.method
            if method == "GET":
                stores = (
                    http.request.env["keykeep.psono.datastore"]
                    .sudo()
                    .search([("user_id", "=", token.user_id.id)])
                )
                return self.encrypted_response(
                    token, {"datastores": [s.to_list_payload() for s in stores]}
                )
            body = self._decrypt_body(token)
            if method == "PUT":
                store = (
                    http.request.env["keykeep.psono.datastore"]
                    .sudo()
                    .create(
                        {
                            "user_id": token.user_id.id,
                            "type": body.get("type", "password"),
                            "description": body.get("description", "Default"),
                            "data": body.get("data", ""),
                            "data_nonce": body.get("data_nonce", ""),
                            "secret_key": body.get("secret_key", ""),
                            "secret_key_nonce": body.get("secret_key_nonce", ""),
                            "is_default": body.get("is_default", True),
                        }
                    )
                )
                return self.encrypted_response(token, {"datastore_id": store.psono_id}, 201)
            if method == "POST":
                return self._datastore_update(token, body)
            raise PsonoError("METHOD_NOT_ALLOWED", status=405, token=token)
        except PsonoError as exc:
            return exc.to_response()

    def _datastore_update(self, token, body):
        ds_id = body.get("datastore_id")
        if not ds_id:
            raise PsonoError("DATASTORE_ID_NOT_PROVIDED", status=400, token=token)
        store = (
            http.request.env["keykeep.psono.datastore"]
            .sudo()
            .search(
                [("psono_id", "=", ds_id), ("user_id", "=", token.user_id.id)],
                limit=1,
            )
        )
        if not store:
            raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
        vals = {}
        for f in ("data", "data_nonce", "type", "description",
                  "secret_key", "secret_key_nonce", "is_default"):
            if f in body:
                vals[f] = body[f]
        store.write(vals)
        return self.encrypted_response(
            token,
            {
                "write_date": store.write_date.isoformat() if store.write_date else "",
                "is_default": store.is_default,
            },
        )

    @http.route(
        "/keykeep/psono/datastore/<path:datastore_id>/",
        type="http", auth="none", csrf=False, methods=["GET"],
    )
    def datastore_detail(self, datastore_id, **kw):
        try:
            token = self._require_token()
            store = (
                http.request.env["keykeep.psono.datastore"]
                .sudo()
                .search(
                    [("psono_id", "=", datastore_id), ("user_id", "=", token.user_id.id)],
                    limit=1,
                )
            )
            if not store:
                raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
            return self.encrypted_response(token, store.to_detail_payload())
        except PsonoError as exc:
            return exc.to_response()

    # ── secret ────────────────────────────────────────────────────

    @http.route(
        "/keykeep/psono/secret/",
        type="http", auth="none", csrf=False, methods=["GET", "PUT", "POST"],
    )
    def secret(self, **kw):
        try:
            token = self._require_token()
            method = http.request.httprequest.method
            if method == "GET":
                raise PsonoError("SECRET_ID_NOT_PROVIDED", status=400, token=token)
            body = self._decrypt_body(token)
            if method == "PUT":
                return self._secret_create(token, body)
            if method == "POST":
                return self._secret_update(token, body)
            raise PsonoError("METHOD_NOT_ALLOWED", status=405, token=token)
        except PsonoError as exc:
            return exc.to_response()

    def _secret_create(self, token, body):
        parent_datastore = body.get("parent_datastore_id")
        parent_share = body.get("parent_share_id")
        if not parent_datastore and not parent_share:
            raise PsonoError(
                "EITHER_PARENT_DATASTORE_OR_SHARE_NEED_TO_BE_DEFINED",
                status=400, token=token,
            )
        if parent_datastore and parent_share:
            raise PsonoError(
                "EITHER_PARENT_DATASTORE_OR_SHARE_NEED_TO_BE_DEFINED_NOT_BOTH",
                status=400, token=token,
            )
        store = False
        if parent_datastore:
            store = (
                http.request.env["keykeep.psono.datastore"]
                .sudo()
                .search(
                    [
                        ("psono_id", "=", parent_datastore),
                        ("user_id", "=", token.user_id.id),
                    ],
                    limit=1,
                )
            )
            if not store:
                raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
        secret = (
            http.request.env["keykeep.psono.secret"]
            .sudo()
            .create(
                {
                    "user_id": token.user_id.id,
                    "parent_datastore_id": store.id if store else False,
                    "data": body.get("data", ""),
                    "data_nonce": body.get("data_nonce", ""),
                    "type": body.get("type", "password"),
                    "link_id": body.get("link_id", ""),
                }
            )
        )
        return self.encrypted_response(token, {"secret_id": secret.psono_id}, 201)

    def _secret_update(self, token, body):
        secret_id = body.get("secret_id")
        if not secret_id:
            raise PsonoError("SECRET_ID_NOT_PROVIDED", status=400, token=token)
        secret = (
            http.request.env["keykeep.psono.secret"]
            .sudo()
            .search(
                [("psono_id", "=", secret_id), ("user_id", "=", token.user_id.id)],
                limit=1,
            )
        )
        if not secret:
            raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
        vals = {}
        if body.get("data") is not None:
            vals["data"] = body["data"]
        if body.get("data_nonce") is not None:
            vals["data_nonce"] = body["data_nonce"]
        if body.get("type") is not None:
            vals["type"] = body["type"]
        secret.write(vals)
        return self.encrypted_response(token, {"success": "Data updated."})

    @http.route(
        "/keykeep/psono/secret/<path:secret_id>/",
        type="http", auth="none", csrf=False, methods=["GET"],
    )
    def secret_read(self, secret_id, **kw):
        try:
            token = self._require_token()
            secret = (
                http.request.env["keykeep.psono.secret"]
                .sudo()
                .search(
                    [("psono_id", "=", secret_id), ("user_id", "=", token.user_id.id)],
                    limit=1,
                )
            )
            if not secret:
                raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
            secret.write({"read_count": secret.read_count + 1})
            return self.encrypted_response(token, secret.to_read_payload())
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/secret/history/<path:secret_id>/",
        type="http", auth="none", csrf=False, methods=["GET"],
    )
    def secret_history(self, secret_id, **kw):
        try:
            token = self._require_token()
            secret = (
                http.request.env["keykeep.psono.secret"]
                .sudo()
                .search(
                    [("psono_id", "=", secret_id), ("user_id", "=", token.user_id.id)],
                    limit=1,
                )
            )
            if not secret:
                raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
            history = secret.history_ids.sorted("changed_at")
            payload = {
                "history": [
                    {
                        "id": h.psono_id,
                        "create_date": (
                            h.changed_at.isoformat() if h.changed_at else ""
                        ),
                    }
                    for h in history
                ]
            }
            return self.encrypted_response(token, payload)
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/bulk-secret/",
        type="http", auth="none", csrf=False, methods=["PUT"],
    )
    def bulk_secret(self, **kw):
        """Bulk create secrets (used by psono-web import)."""
        try:
            token = self._require_token()
            body = self._decrypt_body(token)
            secrets = body.get("secrets") or []
            parent_datastore = body.get("parent_datastore_id")
            if not secrets:
                raise PsonoError("INVALID_SECRETS", status=400, token=token)
            if not parent_datastore:
                raise PsonoError(
                    "EITHER_PARENT_DATASTORE_OR_SHARE_NEED_TO_BE_DEFINED",
                    status=400, token=token,
                )
            store = (
                http.request.env["keykeep.psono.datastore"]
                .sudo()
                .search(
                    [
                        ("psono_id", "=", parent_datastore),
                        ("user_id", "=", token.user_id.id),
                    ],
                    limit=1,
                )
            )
            if not store:
                raise PsonoError("NO_PERMISSION_OR_NOT_EXIST", status=403, token=token)
            created = []
            for s in secrets:
                secret = (
                    http.request.env["keykeep.psono.secret"]
                    .sudo()
                    .create(
                        {
                            "user_id": token.user_id.id,
                            "parent_datastore_id": store.id,
                            "data": s.get("data", ""),
                            "data_nonce": s.get("data_nonce", ""),
                            "type": "password",
                            "link_id": s.get("link_id", ""),
                        }
                    )
                )
                created.append(
                    {"link_id": s.get("link_id", ""), "secret_id": secret.psono_id}
                )
            self._audit(
                token.user_id.user_id,
                "import",
                "bulk_secret, %d entries" % len(created),
            )
            return self.encrypted_response(token, {"secrets": created}, 201)
        except PsonoError as exc:
            return exc.to_response()

class PsonoRecoveryController(PsonoBase, http.Controller):
    """Recovery-code endpoints (design D7/D8 — Alt 4).

    The recovery code itself NEVER reaches the server. The client generates it
    locally and sends only:

      recovery_authkey = scrypt(recovery_code, ...)   → verifiable
      recovery_data    = encrypt({private_key, secret_key},
                                 recovery_code, recovery_sauce)
                                                       → opaque E2E blob

    The server can verify a submitted code and hand the blob back, but can
    never read it. Same principle as authkey (bcrypt) and private_key (wrapped
    by the master password).
    """

    # ── registration (authenticated) ──────────────────────────────

    @http.route(
        "/keykeep/psono/recoverycode/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def recoverycode(self, **kw):
        """Store/replace recovery material for the authenticated vault."""
        try:
            token = self._require_token()
            body = self._decrypt_body(token)
            authkey = body.get("recovery_authkey") or ""
            data = body.get("recovery_data") or ""
            nonce = body.get("recovery_data_nonce") or ""
            sauce = body.get("recovery_sauce") or ""
            if not authkey or not data:
                raise PsonoError("RECOVERY_DATA_INCOMPLETE", status=400, token=token)

            user = token.user_id
            replacing = user.has_recovery()
            user.sudo().write(
                {
                    "recovery_authkey": authkey,
                    "recovery_data": data,
                    "recovery_data_nonce": nonce,
                    "recovery_sauce": sauce,
                    "recovery_created_at": odoo_fields.Datetime.now(),
                }
            )
            self._audit(
                user.user_id,
                "recovery_replace" if replacing else "recovery_register",
                None,
            )
            return self.encrypted_response(token, {"success": "Recovery data updated."})
        except PsonoError as exc:
            return exc.to_response()

    # ── recovery exchange (unauthenticated) ───────────────────────

    @http.route(
        "/keykeep/psono/password/",
        type="http", auth="none", csrf=False, methods=["POST"],
    )
    def password_step1(self, **kw):
        """Step 1: verify the recovery authkey and return the encrypted blob.

        No Authorization header — called while logged out. Must answer
        identically for an unknown username and a wrong authkey so it does not
        disclose whether an account exists.
        """
        try:
            body = self.parse_json_body()
            username = (body.get("username") or "").lower().strip()
            authkey = body.get("recovery_authkey") or ""
            user = self._lookup_recovery_user(username, authkey)
            if not user:
                raise PsonoError("USER_NOT_FOUND", status=400)
            return self.plain_response(
                {
                    "recovery_data": user.recovery_data,
                    "recovery_data_nonce": user.recovery_data_nonce,
                    "recovery_sauce": user.recovery_sauce,
                    "user_sauce": user.user_sauce,
                    "policies": {},
                }
            )
        except PsonoError as exc:
            return exc.to_response()

    @http.route(
        "/keykeep/psono/password/",
        type="http", auth="none", csrf=False, methods=["PUT"],
    )
    def password_step2(self, **kw):
        """Step 2: install the new authkey and re-wrapped key material."""
        try:
            body = self.parse_json_body()
            username = (body.get("username") or "").lower().strip()
            authkey = body.get("recovery_authkey") or ""
            update_data = body.get("update_data") or ""
            update_nonce = body.get("update_data_nonce") or ""
            if not update_data:
                raise PsonoError("UPDATE_DATA_INCOMPLETE", status=400)

            user = self._lookup_recovery_user(username, authkey)
            if not user:
                # Same response as a wrong authkey — no username disclosure.
                raise PsonoError("USER_NOT_FOUND", status=400)

            # update_data is E2E-encrypted with the recovery code; the server
            # cannot read it. psono's contract: the server applies the new
            # authkey here. It MUST be bcrypt-hashed exactly like register()
            # does, or the login path (bcrypt.checkpw) can never match it.
            new_authkey = body.get("new_authkey") or authkey
            vals = {
                "authkey": bcrypt.hashpw(
                    new_authkey.encode(), bcrypt.gensalt()
                ).decode()
            }
            if body.get("hashing_algorithm"):
                vals["hashing_algorithm"] = body["hashing_algorithm"]
            if body.get("hashing_parameters"):
                vals["hashing_parameters"] = body["hashing_parameters"]
            user.sudo().write(vals)
            self._audit(user.user_id, "recovery_use", None)
            return self.plain_response({"success": "Password updated."})
        except PsonoError as exc:
            return exc.to_response()

    # ── helpers ───────────────────────────────────────────────────

    def _lookup_recovery_user(self, username, authkey):
        """Return the vault whose recovery authkey matches, or None.

        Deliberately returns None for both "no such user" and "wrong authkey"
        so the caller cannot distinguish them.
        """
        if not username or not authkey:
            return None
        user = (
            http.request.env["keykeep.psono.user"]
            .sudo()
            .search([("username", "=", username)], limit=1)
        )
        if not user or not user.recovery_authkey or not user.has_recovery():
            return None
        # The client derives recovery_authkey with scrypt and sends a bcrypt-
        # comparable value only in psono-server; here the client sends the
        # scrypt output and we compare it directly (constant-time).
        if not secrets.compare_digest(user.recovery_authkey, authkey):
            return None
        return user


class PsonoAccountController(PsonoBase, http.Controller):
    """Account deletion (design D10 — disabled by default)."""

    @http.route(
        "/keykeep/psono/user/delete/",
        type="http", auth="none", csrf=False, methods=["DELETE"],
    )
    def user_delete(self, **kw):
        """Delete the caller's own vault. Irreversible.

        Requires the vault authkey AND the master password. Disabled unless
        `keykeep_psono.allow_delete_account` is enabled. Never available to a
        sessionless client.
        """
        try:
            token = self._require_token()
            allow = (
                http.request.env["ir.config_parameter"]
                .sudo()
                .get_param("keykeep_psono.allow_delete_account", "0")
            )
            if str(allow).strip().lower() not in ("1", "true", "yes", "on"):
                raise PsonoError("ACCOUNT_DELETION_DISABLED", status=403, token=token)

            # Sessionless clients may not delete (design D10).
            uid = http.request.session.uid
            user = token.user_id
            if not uid or user.user_id.id != uid:
                raise PsonoError("ACCOUNT_DELETION_DISABLED", status=403, token=token)

            body = self.parse_json_body()
            authkey = body.get("authkey") or ""
            password = body.get("password") or ""
            if not authkey or not password:
                raise PsonoError("AUTHKEY_OR_PASSWORD_MISSING", status=400, token=token)
            if not self._verify_authkey(authkey, user.authkey):
                raise PsonoError("USERNAME_OR_PASSWORD_WRONG", status=400, token=token)

            # Verify the master password against the linked Odoo user.
            try:
                user.user_id.sudo()._check_credentials(
                    {
                        "login": user.user_id.login,
                        "password": password,
                        "type": "password",
                    },
                    {"interactive": True},
                )
            except Exception:  # noqa: BLE001
                raise PsonoError("USERNAME_OR_PASSWORD_WRONG", status=400, token=token)

            # Audit BEFORE removal so the trail survives the delete.
            self._audit(user.user_id, "delete_account", "vault deleted")
            user.sudo().unlink()
            return self.plain_response({})
        except PsonoError as exc:
            return exc.to_response()

    def _verify_authkey(self, authkey, stored_hash):
        try:
            return bcrypt.checkpw(authkey.encode(), stored_hash.encode())
        except (ValueError, TypeError):
            return False
