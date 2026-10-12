# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Small stdlib helpers (no Odoo imports — safe to import anywhere)."""

import datetime as _dt

# psono-web ships these as region-specific locale files. Odoo uses an
# underscore for the same region (pt_BR, zh_Hans, zh_Hant), so a plain
# split("_") would produce a code the client rejects.
_REGION_VARIANTS = {
    "pt_br": "pt-BR",
    "zh_hans": "zh-Hans",
    "zh_hant": "zh-Hant",
    # Odoo uses nb_NO / nn_NO for Norwegian; psono ships a single "no".
    "nb_no": "no",
    "nn_no": "no",
}

# Every locale the vendored psono-web build ships (translations/locale-*.json).
# The client only calls changeLanguage() when the code is in this list —
# anything else silently falls back to English.
SUPPORTED_LANGUAGES = {
    "ar", "bn", "ca", "cs", "da", "de", "en", "es", "fi", "fr", "he",
    "hi", "hr", "hu", "it", "ja", "ko", "nl", "no", "pl", "pt",
    "pt-BR", "ru", "sk", "sv", "uk", "vi", "zh", "zh-Hans", "zh-Hant",
}


def odoo_lang_to_psono(lang):
    """Map an Odoo language code to a psono-web locale code (design D4).

    Odoo:  sv_SE   en_US   pt_BR   zh_Hans   xx_YY
    psono: sv      en      pt-BR   zh-Hans   en (fallback)

    Returns "en" for anything the client does not ship, so that
    changeLanguage() is never called with an unsupported code.
    """
    if not lang:
        return "en"
    raw = str(lang).strip()
    if not raw:
        return "en"
    variant = _REGION_VARIANTS.get(raw.lower())
    if variant:
        return variant
    base = raw.split("_")[0].split("-")[0].lower()
    return base if base in SUPPORTED_LANGUAGES else "en"


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
