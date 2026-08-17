# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Minimal Vaultwarden client for the keykeep bridge.

Item read/write requires the bitwarden-sdk for org-key encryption (spike);
this client exposes the health check and auth primitives that work today.
"""

import logging

import requests

_logger = logging.getLogger(__name__)


class VaultClient:
    def __init__(self, vault_url, token=None):
        self.base = (vault_url or "").rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.timeout = 15

    def health(self):
        try:
            resp = self.session.get(f"{self.base}/alive", timeout=10)
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def _org_headers(self):
        if not self.token:
            raise Exception("No org access token configured")
        return {"Authorization": f"Bearer {self.token}"}
