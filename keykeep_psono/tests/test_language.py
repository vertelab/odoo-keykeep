# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Language mapping tests (design D4).

The psono web client only calls i18n.changeLanguage() when the code is in its
own supportedLngs list. An unmapped Odoo code (sv_SE) would be rejected and
silently fall back to English, so the mapping must always produce a code the
client ships.
"""

from odoo.tests.common import TransactionCase

from ..util import SUPPORTED_LANGUAGES, odoo_lang_to_psono


class TestLanguageMapping(TransactionCase):
    def test_base_language_stripped(self):
        self.assertEqual(odoo_lang_to_psono("sv_SE"), "sv")
        self.assertEqual(odoo_lang_to_psono("en_US"), "en")
        self.assertEqual(odoo_lang_to_psono("de_DE"), "de")
        self.assertEqual(odoo_lang_to_psono("fr_FR"), "fr")

    def test_region_variants_preserved(self):
        self.assertEqual(odoo_lang_to_psono("pt_BR"), "pt-BR")
        self.assertEqual(odoo_lang_to_psono("zh_Hans"), "zh-Hans")
        self.assertEqual(odoo_lang_to_psono("zh_Hant"), "zh-Hant")

    def test_norwegian_variants_collapse(self):
        self.assertEqual(odoo_lang_to_psono("nb_NO"), "no")
        self.assertEqual(odoo_lang_to_psono("nn_NO"), "no")

    def test_unknown_falls_back_to_english(self):
        self.assertEqual(odoo_lang_to_psono("xx_YY"), "en")
        self.assertEqual(odoo_lang_to_psono("kl_GL"), "en")

    def test_empty_falls_back_to_english(self):
        self.assertEqual(odoo_lang_to_psono(""), "en")
        self.assertEqual(odoo_lang_to_psono(None), "en")

    def test_result_is_always_supported_by_the_client(self):
        """The whole point: never hand the client a code it will reject."""
        for lang in (
            "sv_SE", "en_US", "pt_BR", "zh_Hans", "zh_Hant", "nb_NO",
            "xx_YY", "", None, "de", "sv", "no_NO", "kl_GL", "ar_SA",
        ):
            self.assertIn(
                odoo_lang_to_psono(lang),
                SUPPORTED_LANGUAGES,
                "mapping produced a code the client does not ship: %r" % lang,
            )
