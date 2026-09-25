# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Serve the psono-web SPA (built client) from Odoo, same origin.

The built web client lives in static/src/psono_web/. index.html is served
only to authenticated Odoo sessions (defense-in-depth; the API itself is
protected by psono tokens). Other assets are served as-is with the SPA's
relative asset paths (publicPath relative in the build).
"""

import logging
import os

from odoo import http

_logger = logging.getLogger(__name__)

WEB_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static",
    "src",
    "psono_web",
)


class PsonoWebController(http.Controller):
    @http.route(
        "/keykeep/psono/web/",
        type="http", auth="user", csrf=False, methods=["GET"],
    )
    def web_index(self, **kw):
        return self._serve("index.html")

    @http.route(
        "/keykeep/psono/web/<path:filepath>",
        type="http", auth="public", csrf=False, methods=["GET"],
    )
    def web_asset(self, filepath, **kw):
        return self._serve(filepath)

    def _serve(self, filepath):
        # prevent path traversal
        filepath = (filepath or "").replace("\\", "/")
        if filepath.startswith("/") or ".." in filepath.split("/"):
            return http.Response(status=404)
        full = os.path.join(WEB_ROOT, filepath)
        if not os.path.isfile(full):
            # SPA fallback: unknown deep links serve index.html so hash
            # routes (#/other/import) work on refresh.
            full = os.path.join(WEB_ROOT, "index.html")
            if not os.path.isfile(full):
                return http.Response(
                    "psono-web is not built yet. Run the build step "
                    "(task 5.3) to place the web client in static/src/psono_web/.",
                    status=503,
                )
        with open(full, "rb") as fh:
            content = fh.read()
        ctype = self._content_type(full)
        return http.Response(content, content_type=ctype)

    @staticmethod
    def _content_type(path):
        ext = os.path.splitext(path)[1].lower()
        return {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript",
            ".mjs": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".txt": "text/plain",
            ".map": "application/json",
        }.get(ext, "application/octet-stream")
