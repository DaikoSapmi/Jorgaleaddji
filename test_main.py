import os
import re
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import main


class TestJorgaleaddjiCore(unittest.TestCase):
    def test_quotation_marks_heuristic_allows_valid_sami_quotes(self):
        valid_sami = "Oahpaheaddji dajai: ”Dál mii álgit!”"
        tips_valid = main.local_heuristic_checks("", valid_sami)
        rules_valid = [t["rule"] for t in tips_valid]
        self.assertNotIn("Aisttonmearkkat (Sitattegn)", rules_valid)

        english_quotes = "Oahpaheaddji dajai: “Dál mii álgit!”"
        tips_eng = main.local_heuristic_checks("", english_quotes)
        self.assertIn("Aisttonmearkkat (Sitattegn)", [t["rule"] for t in tips_eng])

        norwegian_guillemets = "Oahpaheaddji dajai: «Dál mii álgit!»"
        tips_nor = main.local_heuristic_checks("", norwegian_guillemets)
        self.assertIn("Aisttonmearkkat (Sitattegn)", [t["rule"] for t in tips_nor])

    def test_dahje_vs_vai_checked_per_sentence(self):
        mixed_text = "Mun boađán ihttin dahje bearjadaga. Boađátgo don maiddái?"
        tips_mixed = main.local_heuristic_checks("", mixed_text)
        self.assertNotIn("Dahje vs. Vai", [t["rule"] for t in tips_mixed])

        wrong_question = "Boađátgo ihttin dahje bearjadaga?"
        tips_wrong = main.local_heuristic_checks("", wrong_question)
        self.assertIn("Dahje vs. Vai", [t["rule"] for t in tips_wrong])

    def test_iija_place_names_vs_sentence_initial_loanwords(self):
        loanword_text = "Biologiija ja energiija leat dehálaččat. Demokratiija nanne servodaga."
        tips_loan = main.local_heuristic_checks("", loanword_text)
        self.assertNotIn("Báikenamat eai noga -iija", [t["rule"] for t in tips_loan])

        place_text = "Son mátkkoštii Tansaniija ja Italiija diibmá."
        tips_place = main.local_heuristic_checks("", place_text)
        self.assertIn("Báikenamat eai noga -iija", [t["rule"] for t in tips_place])

    def test_source_alignment_paragraphs_and_years(self):
        src = "Første avsnitt fra 1997.\n\nAndre avsnitt fra 2026.\n\nTredje avsnitt."
        sami_missing = "Vuosttaš oassi.\n\nNubbi oassi jagis 2026."
        tips = main.local_heuristic_checks(src, sami_missing)
        rules = [t["rule"] for t in tips]
        self.assertIn("Avsnittsstruktur (Fullstendighet)", rules)
        self.assertIn("Årstall fra kildeteksten", rules)

    def test_divvun_fixes_sentence_initial_typo_but_protects_proper_nouns(self):
        text = "Son bođii ikte. Boahhtá ihttin."
        errs = [
            {
                "error_text": "Boahhtá",
                "error_code": "typo",
                "start_index": 16,
                "end_index": 23,
                "suggestions": ["Boahtá"],
            }
        ]
        fixed = main.apply_divvun_suggestions(text, errs, protect_proper_nouns=True)
        self.assertEqual(fixed, "Son bođii ikte. Boahtá ihttin.")

        name_mid = "Mun deaivvadin Wartha ikte."
        errs_mid = [
            {
                "error_text": "Wartha",
                "error_code": "typo",
                "start_index": 15,
                "end_index": 21,
                "suggestions": ["Vártha"],
            }
        ]
        self.assertEqual(
            main.apply_divvun_suggestions(name_mid, errs_mid, protect_proper_nouns=True),
            name_mid,
        )

        name_start = "Son bođii. Warth manai ruoktot."
        errs_start = [
            {
                "error_text": "Warth",
                "error_code": "typo",
                "start_index": 11,
                "end_index": 16,
                "suggestions": ["Várát"],
            }
        ]
        self.assertEqual(
            main.apply_divvun_suggestions(
                name_start,
                errs_start,
                protect_proper_nouns=True,
                source_text="Han kom. Warth gikk hjem.",
            ),
            name_start,
        )

    def test_divvun_skips_overlapping_error_spans_safely(self):
        text = "Guokte olbmot bohte."
        errs = [
            {
                "error_text": "Guokte olbmot",
                "error_code": "gram",
                "start_index": 0,
                "end_index": 13,
                "suggestions": ["Guokte olbmo"],
            },
            {
                "error_text": "olbmot",
                "error_code": "gram",
                "start_index": 7,
                "end_index": 13,
                "suggestions": ["olbmo"],
            },
        ]
        fixed = main.apply_divvun_suggestions(text, errs, protect_proper_nouns=True)
        self.assertEqual(fixed, "Guokte olbmo bohte.")

    def test_sanitize_error_message_hides_api_keys(self):
        secret = "AIzaSySecretKey1234567890"
        raw_err = f"RequestError for url 'https://generativelanguage.googleapis.com/v1beta/models?key={secret}'"
        cleaned = main.sanitize_error_message(raw_err, secret)
        self.assertNotIn(secret, cleaned)
        self.assertNotIn("AIzaSy", cleaned)
        self.assertIn("[SKJULT", cleaned)

    def test_deprecated_model_substitution(self):
        self.assertEqual(main.DEFAULT_GEMINI_MODEL, "gemini-4-hydrogen")

        model, note = main.normalize_gemini_model("gemini-2.5-flash")
        self.assertEqual(model, "gemini-4-hydrogen")
        self.assertIsNotNone(note)

        valid_model, valid_note = main.normalize_gemini_model("gemini-4-argon")
        self.assertEqual(valid_model, "gemini-4-argon")
        self.assertIsNone(valid_note)

    def test_glossary_and_language_specific_system_instruction(self):
        sme_inst = main.build_system_instruction("sme", "kommunestyret = suohkanstivra\n# kommentar")
        self.assertIn("Kildeteksten er allerede skrevet på nordsamisk", sme_inst)
        self.assertNotIn("fra norsk (bokmål/nynorsk)", sme_inst)
        self.assertIn("kommunestyret → suohkanstivra", sme_inst)

        fin_inst = main.build_system_instruction("fin")
        self.assertIn("fra finsk til nordsamisk", fin_inst)
        self.assertIn("hallitus", fin_inst)

    def test_frontend_dom_ids_match_between_html_and_js(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, "static", "index.html")
        js_path = os.path.join(base_dir, "static", "app.js")
        if not (os.path.exists(html_path) and os.path.exists(js_path)):
            self.skipTest("Static files not present in test working dir")

        with open(html_path, encoding="utf-8") as fh:
            html = fh.read()
        with open(js_path, encoding="utf-8") as fj:
            js = fj.read()

        html_ids = set(re.findall(r'\bid="([^"]+)"', html))
        js_static_ids = set(re.findall(r"getElementById\('([^']+)'\)", js))
        missing = js_static_ids - html_ids
        self.assertEqual(missing, set(), f"Missing IDs in index.html: {missing}")
        self.assertNotIn("&rarr;", js)


class TestAsyncPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_tartu_failure_does_not_feed_source_text_into_divvun(self):
        req = main.TranslateRequest(
            text="Länsstyrelsen har gett tillstånd.",
            source_lang="swe",
            use_llm=True,
            auto_apply_divvun=True,
        )

        with (
            patch("main.call_tartu_mt", new=AsyncMock(return_value=None)),
            patch("main.call_divvun_grammar", new=AsyncMock(return_value={"errs": []})) as mock_divvun,
            patch(
                "main.call_gemini_refiner",
                new=AsyncMock(
                    return_value={
                        "final_translation": "Stáhtahálddašeaddji lea addán lobi.",
                        "improvements": ["Direkte oversatt med Gemini 4."],
                        "llm_active": True,
                        "used_model": "gemini-4-argon",
                    }
                ),
            ),
        ):
            events = [ev async for ev in main.run_translation_pipeline_events(req)]
            for ev in events:
                if ev.get("type") == "progress":
                    self.assertNotIn("&rarr;", ev["title"])
            result_ev = [e for e in events if e["type"] == "result"][0]["data"]

            self.assertEqual(mock_divvun.call_count, 1)
            mock_divvun.assert_called_once_with("Stáhtahálddašeaddji lea addán lobi.")
            self.assertFalse(result_ev["step1_had_tartu"])
            self.assertEqual(result_ev["step3_final_text"], "Stáhtahálddašeaddji lea addán lobi.")

    async def test_step4_skips_redundant_divvun_call_when_no_text_changed(self):
        req = main.TranslateRequest(
            text="Mun deaivvadin Wartha ikte.",
            source_lang="sme",
            use_llm=False,
            auto_apply_divvun=True,
        )
        protected_err = {
            "error_text": "Wartha",
            "error_code": "typo",
            "start_index": 15,
            "end_index": 21,
            "suggestions": ["Vártha"],
        }

        with patch(
            "main.call_divvun_grammar",
            new=AsyncMock(return_value={"errs": [protected_err]}),
        ) as mock_divvun:
            await main.translate_pipeline(req)
            # Trinn 2 (1 gang) + Trinn 4 første sjekk (1 gang) = 2 kall, IKKE et 3. kall siden teksten var uendret!
            self.assertEqual(mock_divvun.call_count, 2)

    async def test_gemini_refiner_falls_back_on_429_and_uses_interactions_api(self):
        quota_err = Exception("429 Resource Exhausted")
        quota_err.code = 429

        ok_interaction = types.SimpleNamespace(
            status="completed",
            output_text='{"final_translation": "Suohkanstivra meannudii ášši.", "improvements": ["Snudde passiv til aktiv."]}',
        )

        create_mock = AsyncMock(side_effect=[quota_err, ok_interaction])
        fake_client = MagicMock()
        fake_client.aio.interactions.create = create_mock

        with patch("main.genai.Client", return_value=fake_client) as client_constructor:
            res = await main.call_gemini_refiner(
                source_text="Saken ble behandlet av kommunestyret.",
                tartu_draft="Ášši meannuduvvui suohkanstivrras.",
                divvun_corrected="Ášši meannuduvvui suohkanstivrras.",
                divvun_errs=[],
                local_tips=[],
                override_key="test_valid_key_12345",
                override_model="gemini-4-argon",
                source_lang="nor",
                thinking_level="high",
                glossary="kommunestyret = suohkanstivra",
            )

        client_constructor.assert_called_once_with(
            api_key="test_valid_key_12345",
            http_options={"timeout": main.GEMINI_REQUEST_TIMEOUT_MS},
        )
        self.assertEqual(main.GEMINI_REQUEST_TIMEOUT_MS, 600_000)
        self.assertTrue(res["llm_active"])
        self.assertEqual(res["used_model"], "gemini-4-hydrogen")
        self.assertEqual(res["final_translation"], "Suohkanstivra meannudii ášši.")
        self.assertTrue(any("gemini-4-hydrogen" in imp for imp in res["improvements"]))

        # Verifiser at temperature ikke er med i generation_config, og at thinking_level + response_format er satt riktig
        second_call_kwargs = create_mock.call_args_list[1].kwargs
        self.assertNotIn("temperature", second_call_kwargs["generation_config"])
        self.assertEqual(second_call_kwargs["generation_config"]["thinking_level"], "high")
        self.assertEqual(second_call_kwargs["response_format"]["mime_type"], "application/json")


if __name__ == "__main__":
    unittest.main()
