import json
import os
import re
import types
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import main


class TestJorgaleaddjiCore(unittest.TestCase):
    def test_long_text_splitting_preserves_every_character(self):
        samples = [
            ("Oassi sámegillii.\n\n" * 800) + "Loahppa.",
            "x" * 8000,
            ("árbevierru " * 900).rstrip(),
            " \n\n" + ("linnjá\n" * 800) + "\n",
        ]
        for sample in samples:
            with self.subTest(length=len(sample)):
                parts = main.split_pipeline_text(sample)
                self.assertGreater(len(parts), 1)
                self.assertEqual("".join(text + separator for text, separator in parts), sample)
                self.assertTrue(all(0 < len(text) <= main.PIPELINE_CHUNK_SIZE for text, _ in parts))
        paragraphs = main.split_pipeline_text(("avsnitt\n\n" * 1000) + "slutt")
        self.assertTrue(all(separator == "\n\n" for _, separator in paragraphs[:-1]))

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

    def test_all_local_tips_are_translated_and_interpolated(self):
        source = "1997\n2000\n2001"
        sami = (
            "In dieđe jos enngo ektui gávnnahii olggos olggosoaidnit "
            "dahkkojuvvui dieđus ge 25% 25%-mearri Tansaniija “hei”.\n"
            "Boađátgo ihttin dahje bearjadaga?"
        )
        original = main.local_heuristic_checks(source, sami)
        self.assertEqual({tip["rule"] for tip in original}, set(main.TIP_TRANSLATIONS))
        for language in main.UI_LANGUAGES:
            with self.subTest(language=language):
                tips = main.local_heuristic_checks(source, sami, language)
                self.assertEqual(len(tips), len(original))
                self.assertEqual(tips[0]["rule"], tips[0]["translations"][language]["rule"])
                self.assertTrue(all("{" not in tip["message"] for tip in tips))
                self.assertTrue(any("Tansaniija" in tip["message"] for tip in tips))
                self.assertTrue(any("1997" in tip["message"] for tip in tips))

    def test_server_messages_cover_all_languages(self):
        self.assertTrue(all(len(messages) == len(main.UI_LANGUAGES) for messages in main.SERVER_MESSAGES.values()))
        for language in main.UI_LANGUAGES:
            self.assertIn("Test", main.ui_message(language, "step1_translation", language="Test"))

    def test_ui_catalogs_have_matching_keys_and_placeholders(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "ui-strings.js")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        catalog = json.loads(source.removeprefix("export const UI_STRINGS = ").removesuffix(";\n"))
        self.assertEqual(set(catalog), set(main.UI_LANGUAGES))
        for language, messages in catalog.items():
            with self.subTest(language=language):
                self.assertEqual(set(messages), set(catalog["nor"]))
                for key, message in messages.items():
                    self.assertTrue(message, key)
                    self.assertEqual(
                        set(re.findall(r"\{(\w+)\}", message)),
                        set(re.findall(r"\{(\w+)\}", catalog["nor"][key])),
                        key,
                    )

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
    async def test_model_discovery_only_offers_configured_choices(self):
        async def models():
            for name in ("gemini-4-carbon", "gemini-3.8-flash", "gemini-4-hydrogen", "gemini-4-argon"):
                yield types.SimpleNamespace(name=f"models/{name}")

        fake_client = MagicMock()
        fake_client.aio.models.list = AsyncMock(return_value=models())
        with patch("main.genai.Client", return_value=fake_client):
            available = await main.fetch_available_gemini_models("test-key")
        self.assertEqual(
            [model["id"] for model in available],
            ["gemini-4-hydrogen", "gemini-4-argon", "gemini-3.8-flash"],
        )

    async def test_gemini_fallback_order_never_adds_unlisted_models(self):
        error = Exception("404 Not Found")
        error.code = 404
        interaction = types.SimpleNamespace(
            status="completed",
            output_text='{"final_translation":"Sámi teaksta","improvements":[]}',
            steps=[],
        )
        for selected, expected in (
            ("gemini-4-hydrogen", ["gemini-4-hydrogen", "gemini-3.8-flash", "gemini-3.5-flash-lite"]),
            ("gemini-4-argon", ["gemini-4-argon", "gemini-4-hydrogen", "gemini-3.8-flash", "gemini-3.5-flash-lite"]),
        ):
            with self.subTest(model=selected):
                client = MagicMock()
                client.aio.interactions.create = AsyncMock(side_effect=[error] * (len(expected) - 1) + [interaction])
                with (
                    patch("main.genai.Client", return_value=client),
                    patch("main.fetch_available_gemini_models", new=AsyncMock()) as discovery,
                ):
                    result = await main.call_gemini_refiner(
                        source_text="Sámi teaksta", tartu_draft=None, divvun_corrected=None,
                        divvun_errs=[], local_tips=[], override_key="test-key",
                        override_model=selected, source_lang="sme",
                    )
                self.assertEqual(
                    [call.kwargs["model"] for call in client.aio.interactions.create.await_args_list],
                    expected,
                )
                self.assertEqual(result["used_model"], "gemini-3.5-flash-lite")
                self.assertTrue(result["llm_active"])
                discovery.assert_not_awaited()

    async def test_long_sami_pipeline_preserves_text_and_adjusts_error_offsets(self):
        source = ("Álgo sámi teaksta.\n\n" * 2499) + "Loahppa."
        self.assertGreater(len(source), 45000)
        self.assertLessEqual(len(source), 50000)
        req = main.TranslateRequest(text=source, source_lang="sme", use_llm=True)

        async def fake_refiner(**kwargs):
            return {
                "final_translation": kwargs["source_text"],
                "improvements": [],
                "llm_active": True,
                "used_model": "gemini-4-hydrogen",
            }

        async def fake_grammar(text):
            return {"errs": [{"start_index": 0, "end_index": 4, "error_text": text[:4], "suggestions": []}]}

        with (
            patch("main.call_divvun_grammar", new=AsyncMock(side_effect=fake_grammar)),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[])),
            patch("main.call_gemini_refiner", new=AsyncMock(side_effect=fake_refiner)) as refiner,
        ):
            events = [event async for event in main.run_translation_pipeline_events(req)]

        result = events[-1]["data"]
        self.assertEqual(result["step3_final_text"], source)
        self.assertFalse(result["result_incomplete"])
        self.assertGreater(refiner.await_count, 1)
        self.assertTrue(all(len(call.kwargs["source_text"]) <= main.PIPELINE_CHUNK_SIZE for call in refiner.await_args_list))
        for error in result["final_divvun_errors"]:
            self.assertEqual(source[error["start_index"]:error["end_index"]], error["error_text"])
        progress = [event for event in events if event["type"] == "progress"]
        self.assertTrue(any("part 2 of" in event["translations"]["eng"]["detail"].lower() for event in progress))

    async def test_long_pipeline_flags_failed_segment_without_losing_source(self):
        source = ("Sámi teaksta.\n\n" * 600) + "Loahppa."
        req = main.TranslateRequest(text=source, source_lang="sme", use_llm=True)
        calls = 0

        async def fake_refiner(**kwargs):
            nonlocal calls
            calls += 1
            return {
                "final_translation": kwargs["source_text"],
                "improvements": ["Gemini failed"] if calls == 2 else [],
                "llm_active": calls != 2,
                "used_model": "gemini-4-hydrogen",
            }

        with (
            patch("main.call_divvun_grammar", new=AsyncMock(return_value={"errs": []})),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[])),
            patch("main.call_gemini_refiner", new=AsyncMock(side_effect=fake_refiner)),
        ):
            events = [event async for event in main.run_translation_pipeline_events(req)]
        result = events[-1]["data"]
        self.assertTrue(result["result_incomplete"])
        self.assertEqual(result["step3_final_text"], source)
        self.assertTrue(any("2" in message and "Gemini" in message for message in result["step3_improvements"]))

    async def test_incomplete_gemini_response_is_not_reported_as_success(self):
        fake_client = MagicMock()
        fake_client.aio.interactions.create = AsyncMock(return_value=types.SimpleNamespace(
            status="incomplete",
            output_text='{"final_translation":"partial","improvements":[]}',
            steps=[],
        ))
        with patch("main.genai.Client", return_value=fake_client):
            result = await main.call_gemini_refiner(
                source_text="original", tartu_draft="original", divvun_corrected="original",
                divvun_errs=[], local_tips=[], override_key="test-key", source_lang="sme",
            )
        self.assertFalse(result["llm_active"])
        self.assertEqual(result["final_translation"], "original")
        self.assertTrue(any("incomplete" in translations["eng"] for translations in result["improvement_translations"].values()))

    async def test_divvun_failures_are_reported_instead_of_clean_check(self):
        req = main.TranslateRequest(text="Sámi teaksta", source_lang="sme", use_llm=False)
        with (
            patch("main.call_divvun_grammar", new=AsyncMock(return_value={"errs": [], "api_error": "HTTP 413"})),
            patch("main.call_divvun_speller", new=AsyncMock(side_effect=main.DivvunSpellerError("HTTP 503"))),
        ):
            events = [event async for event in main.run_translation_pipeline_events(req)]
        result = events[-1]["data"]
        self.assertTrue(result["divvun_check_incomplete"])
        self.assertEqual(result["step3_final_text"], req.text)
        self.assertTrue(any("HTTP 413" in message for message in result["step3_improvements"]))
        self.assertTrue(any("HTTP 503" in message for message in result["step3_improvements"]))

    async def test_divvun_http_failures_keep_the_status_code(self):
        async def handler(request):
            return httpx.Response(413, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            @asynccontextmanager
            async def borrow():
                yield client

            with patch("main.borrow_http_client", borrow):
                grammar = await main.call_divvun_grammar("tekst")
                with self.assertRaisesRegex(main.DivvunSpellerError, "HTTP 413"):
                    await main.call_divvun_speller("tekst")
        self.assertEqual(grammar["api_error"], "HTTP 413")

    async def test_chunked_grammar_keeps_successful_offsets_when_one_part_fails(self):
        text = ("a" * main.DIVVUN_GRAMMAR_CHUNK_SIZE) + " " + (
            "b" * main.DIVVUN_GRAMMAR_CHUNK_SIZE
        ) + " c"

        async def grammar(part):
            if part.startswith("a"):
                return {"errs": [{"start_index": 0, "end_index": 1, "error_text": "a"}]}
            if part.startswith("b"):
                return {"errs": [], "api_error": "timeout after 20 seconds"}
            return {"errs": [{"start_index": 0, "end_index": 1, "error_text": "c"}]}

        with patch("main.call_divvun_grammar", new=AsyncMock(side_effect=grammar)) as mock:
            result = await main.call_divvun_grammar_chunked(text)

        self.assertEqual(mock.await_count, 3)
        self.assertEqual(
            [(err["start_index"], err["end_index"]) for err in result["errs"]],
            [(0, 1), (2 * main.DIVVUN_GRAMMAR_CHUNK_SIZE + 2,
                      2 * main.DIVVUN_GRAMMAR_CHUNK_SIZE + 3)],
        )
        self.assertEqual(result["api_errors"], [{
            "current": 2, "total": 3, "error": "timeout after 20 seconds",
        }])

    async def test_translation_finishes_and_reports_only_failed_grammar_parts(self):
        text = ("sámi orð " * 300).strip()
        request = main.TranslateRequest(text=text, source_lang="sme", use_llm=False)
        grammar_calls = 0

        async def grammar(part):
            nonlocal grammar_calls
            grammar_calls += 1
            if grammar_calls <= 3:
                return {"errs": []}
            if grammar_calls == 5:
                return {"errs": [], "api_error": "timeout after 20 seconds"}
            return {"errs": [{
                "start_index": 0, "end_index": 4, "error_text": part[:4],
                "suggestions": [],
            }]}

        with (
            patch("main.call_divvun_grammar", new=AsyncMock(side_effect=grammar)),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[])),
        ):
            events = [event async for event in main.run_translation_pipeline_events(request)]

        result = events[-1]["data"]
        self.assertEqual(result["step3_final_text"], text)
        self.assertTrue(result["divvun_check_incomplete"])
        self.assertEqual(len(result["final_divvun_errors"]), 2)
        warning = result["divvun_warnings"][0]["nor"]
        self.assertIn("del 2 av 3", warning)
        self.assertIn("røde streker viser bare funn", warning)

    async def test_partial_tartu_failure_does_not_mix_source_into_translation(self):
        @asynccontextmanager
        async def borrow():
            yield MagicMock()

        with (
            patch("main.borrow_http_client", borrow),
            patch("main._tartu_translate_chunk", new=AsyncMock(side_effect=[
                ("Oversatt avsnitt", False), (None, False),
            ])),
        ):
            result = await main.call_tartu_mt("A" * 4000 + "\nSecond paragraph", src="nor")
        self.assertIsNone(result)

    async def test_long_manual_check_preserves_error_offsets_and_reports_failures(self):
        text = ("sámi teaksta\n\n" * 700) + "loahppa"
        request = main.ProofreadRequest(text=text, source_lang="eng")

        async def grammar(chunk):
            return {"errs": [{"start_index": 0, "end_index": 4, "error_text": chunk[:4]}]}

        with (
            patch("main.call_divvun_grammar", new=AsyncMock(side_effect=grammar)) as grammar_mock,
            patch("main.call_divvun_speller", new=AsyncMock(side_effect=main.DivvunSpellerError("HTTP 413"))),
        ):
            result = await main.proofread_only(request)
        self.assertGreater(grammar_mock.await_count, 1)
        self.assertTrue(result["divvun_check_incomplete"])
        self.assertIn("HTTP 413", result["warnings"][0])
        for error in result["errs"]:
            self.assertEqual(text[error["start_index"]:error["end_index"]], error["error_text"])

    async def test_proofread_uses_requested_language_and_accepts_alias(self):
        req = main.ProofreadRequest(text="25%", source_lang="en")
        with (
            patch("main.call_divvun_grammar", new=AsyncMock(return_value={"errs": []})),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[{
                "error_text": "25%", "start_index": 0, "end_index": 3,
                "source": "speller", "suggestions": [],
            }])),
        ):
            result = await main.proofread_only(req)
        self.assertIn("space", result["language_tips"][0]["message"])
        self.assertEqual(result["errs"][0]["title"], "Spelling error (Divvun Speller)")
        self.assertEqual(result["errs"][0]["translations"]["swe"]["title"], "Stavfel (Divvun Speller)")

    async def test_pipeline_localizes_progress_and_local_notices(self):
        req = main.TranslateRequest(text="25%", source_lang="sme", use_llm=False)
        with (
            patch("main.call_divvun_grammar", new=AsyncMock(return_value={"errs": []})),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[])),
        ):
            events = [event async for event in main.run_translation_pipeline_events(req)]
        progress = events[0]
        self.assertIn("Lávki", progress["title"])
        self.assertIn("Step", progress["translations"]["eng"]["title"])
        result = events[-1]["data"]
        notice = result["step3_improvements"][0]
        self.assertIn("disabled", result["improvement_translations"][notice]["eng"])
        self.assertIn("gaska", result["language_tips"][0]["message"])

    async def test_translated_tartu_draft_gets_localized_tips(self):
        req = main.TranslateRequest(text="Hello", source_lang="eng", use_llm=False)
        with (
            patch("main.call_tartu_mt", new=AsyncMock(return_value="25%")) as tartu,
            patch("main.call_divvun_grammar", new=AsyncMock(return_value={"errs": []})),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[])),
        ):
            events = [event async for event in main.run_translation_pipeline_events(req)]
        tartu.assert_awaited_once_with("Hello", src="eng", tgt="sme")
        self.assertIn("Step 1", events[0]["title"])
        self.assertEqual(events[-1]["data"]["step3_final_text"], "25%")
        self.assertIn("space", events[-1]["data"]["language_tips"][0]["message"])

    async def test_final_divvun_check_never_applies_suggestions_after_gemini(self):
        req = main.TranslateRequest(
            text="Original source",
            source_lang="sme",
            use_llm=True,
            auto_apply_divvun=True,
        )
        initial_error = {
            "error_text": "oldword",
            "start_index": 0,
            "end_index": 7,
            "suggestions": ["oldfix"],
        }
        final_error = {
            "error_text": "geminiword",
            "start_index": 0,
            "end_index": 10,
            "suggestions": ["divvunfix"],
        }
        spell_error = {
            "error_text": "otherword",
            "start_index": 11,
            "end_index": 20,
            "suggestions": ["spellfix"],
            "source": "speller",
        }

        with (
            patch("main.call_divvun_grammar", new=AsyncMock(side_effect=[
                {"errs": [initial_error]},
                {"errs": [final_error]},
            ])),
            patch("main.apply_divvun_suggestions", return_value="initially corrected") as apply_suggestions,
            patch("main.call_gemini_refiner", new=AsyncMock(return_value={
                "final_translation": "geminiword otherword",
                "improvements": [],
                "llm_active": True,
                "used_model": "gemini-4-hydrogen",
            })),
            patch("main.call_divvun_speller", new=AsyncMock(return_value=[spell_error])),
        ):
            events = [event async for event in main.run_translation_pipeline_events(req)]

        data = events[-1]["data"]
        self.assertEqual(data["step3_final_text"], "geminiword otherword")
        self.assertEqual(apply_suggestions.call_count, 1)
        self.assertEqual(
            {error["source"] for error in data["final_divvun_errors"]},
            {"grammar", "speller"},
        )
        grammar_result = next(error for error in data["final_divvun_errors"] if error["source"] == "grammar")
        self.assertEqual(grammar_result["suggestions"], ["divvunfix"])
        speller_result = next(error for error in data["final_divvun_errors"] if error["source"] == "speller")
        self.assertEqual(speller_result["suggestions"], ["spellfix"])

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
