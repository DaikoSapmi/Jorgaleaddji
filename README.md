# Jorgaleaddji & Divvun Studio (Gemini 4 Edition)

Et helhetlig oversettelses-, språkvask- og korrekturverktøy for nordsamisk (*davvisámegiella*), tilpasset Docker (Apple Silicon / Linux) og konfigurert på **port 8090**.

## Støttede arbeidsmåter
1. **Norsk → Davvisámegiella:** Oversettelse med TartuNLP, UiT Divvun API og Gemini 4 språkvask.
2. **Svensk → Davvisámegiella:** Oversettelse fra svensk med TartuNLP (med automatisk direkte-fallback til Gemini 4 ved behov) og Divvun.
3. **Finsk → Davvisámegiella:** Oversettelse fra finsk med særskilt kontroll mot finske partisipp-/kasuskalker og falske venner.
4. **Engelsk → Davvisámegiella:** Oversettelse fra engelsk med konvertering til samisk tegnsetting (`”...”`), tallnorm og aktiv verbstil.
5. **Davvisámegiella → Davvisámegiella (Direkte språkvask & korrektur):** Skånsom, normtro språkvask av nordsamisk tekst som retter ortografi, stadieveksling, rekšuvdna, tegnsetting og substantivsyke uten å viske ut forfatterens stemme.

## Nytt i Gemini 4 Edition
- **Google GenAI SDK (`google-genai >= 3.2.0`) & Interactions API:** Støtter `gemini-4-argon` (standard), `gemini-4-carbon`, `gemini-4-hydrogen` (også på gratisnivå) og `gemini-3.5-flash-lite`, med valgbar tenkedybde (`low`, `medium`, `high`).
- **Egen ordliste / terminologi & hurtigoppslag i Sátni.org:** Legg inn faste fagtermer (`kildeord = samisk term`) og slå opp markerte ord direkte i Giellagáldus termbase på [Sátni.org](https://satni.org).
- **Endringsvisning (Diff) & samisk spesialtegn-rad:** Se nøyaktig hvilke ord som ble endret i språkvasken, og sett raskt inn `Á á Č č Đ đ Ŋ ŋ Š š Ŧ ŧ Ž ž ” –`.
- **Raskt, selvstendig webgrensesnitt uten CDN-avhengigheter:** Ingen ekstern JS-kompilering ved oppstart, full tastatur- og skjermleserstøtte, avbryt-knapp (`AbortController`) og sikker nøkkelhåndtering via HTTP-headere.

## Språklig normgrunnlag
1. **Sámediggi & Sámi Giellagáldu: Riektačállinrávvagat (reviderejuvvon 2019)** – Tegnsetting (`”...”`, komma, tankestrek `–`, skråstrek), sammensatte ord og flerordsuttrykk (*Min Áigi -aviisa*), store/små forbokstaver, tall- og datobøyning, fremmedord og laktapartihkkalat.
2. **NRK Sámi Giellagiehtagirji** – Verbspråk mot substantivsyke, aktiv form fremfor unødvendig passiv, refleksivt *iežas* vs. *su*, spørrepartikkel *-go*, *vai* vs. *dahje*, og kasusstyring (rekšuvdna).
3. **UiT Giellatekno & Divvun API** – Morfologisk og syntaktisk kontroll før og etter LLM-språkvask, med beskyttelse av egennavn.

## Oppstart med Docker Compose

```bash
cp .env.example .env
# Legg inn GEMINI_API_KEY i .env (eller legg den rett inn under Innstillinger i nettleseren)
docker compose up -d --build
```

Åpne deretter `http://localhost:8090` i nettleseren.

## Kjøre tester

```bash
docker compose exec sami-translator pytest
# eller lokalt i et virtuelt miljø:
pytest
```
