# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Small stdlib helpers (no Odoo imports — safe to import anywhere)."""

import datetime as _dt


def parse_iso_datetime(value):
    """Parse an ISO-8601 datetime string to naive UTC (stdlib only)."""
    if isinstance(value, _dt.datetime):
        value = value.isoformat()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = _dt.datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return parsed
