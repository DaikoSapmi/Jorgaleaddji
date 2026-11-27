# Jorgaleaddji & Divvun Studio (Gemini 4 Edition)

Et helhetlig oversettelses-, språkvask- og korrekturverktøy for nordsamisk (*davvisámegiella*), tilpasset Docker (Apple Silicon / Linux) og konfigurert på **port 8090**.

## Støttede arbeidsmåter
1. **Norsk → davvisámegiella:** Oversettelse til nordsamisk.
2. **Svensk → davvisámegiella:** Oversettelse til nordsamisk.
3. **Finsk → davvisámegiella:** Oversettelse til nordsamisk.
4. **Engelsk → davvisámegiella:** Oversettelse til nordsamisk.
5. **Davvisámegiella → davvisámegiella:** Språkvask og korrektur av eksisterende nordsamisk tekst, uten oversettelse gjennom TartuNLP.

For de fire oversettelsesspråkene forsøker systemet først å hente et utkast fra TartuNLP. Hvis TartuNLP ikke leverer et fullstendig utkast, kan Gemini oversette direkte når Gemini er aktivert og tilgjengelig. Uten Tartu-utkast og Gemini blir det ikke produsert en oversettelse.

Et tilgjengelig nordsamisk utkast eller en opprinnelig nordsamisk tekst kontrolleres først med Divvun. Automatisk bruk av Divvuns forslag i denne første runden kan slås av i innstillingene. Når Gemini er aktivert og tilgjengelig, brukes Giellaverdde-instruksjonene til videre oversettelse eller språkvask; Gemini kan også slå opp språkfaglige referanser ved behov. Resultatet sjekkes til slutt med Divvun og lokale språkregler. Sluttkontrollen foreslår endringer, men retter ikke teksten automatisk.

Gemini kan slås av. Da vises Tartu-utkastet eller den opprinnelige nordsamiske teksten, eventuelt med automatiske rettinger fra den første Divvun-runden. Resultater og forslag bør alltid vurderes av brukeren; hvis en tjeneste ikke fullfører, vises advarsler.

## Nytt i Gemini 4 Edition
- **Google GenAI SDK (`google-genai >= 3.2.0`) & Interactions API:** Modellvalget omfatter `gemini-4-hydrogen` (standard), `gemini-4-argon`, `gemini-3.8-flash` og `gemini-3.5-flash-lite`, med valgbar tenkedybde (`low`, `medium`, `high`). Ved utilgjengelig modell eller kvoteproblemer forsøkes Hydrogen, deretter Flash og Flash-Lite, uten å prøve Argon automatisk. Tilgjengelighet, kvoter og priser avhenger av Google og API-prosjektet; sjekk [Googles priser](https://ai.google.dev/gemini-api/docs/pricing). Gemini-forespørsler har en timeout på 10 minutter.
- **Egen ordliste / terminologi & hurtigoppslag i Sátni.org:** Legg inn faste fagtermer (`kildeord = samisk term`) og slå opp markerte ord direkte i Giellagáldus termbase på [Sátni.org](https://satni.org).
- **Endringsvisning (Diff) & samisk spesialtegn-rad:** Se nøyaktig hvilke ord som ble endret i språkvasken, og sett raskt inn `Á á Č č Đ đ Ŋ ŋ Š š Ŧ ŧ Ž ž ” –`.
- **Ikke-påtrengende sluttkontroll:** Etter Gemini markerer Divvun grammatikk- og staveforslag for vurdering. Sluttkontrollen endrer ikke teksten automatisk; forslag brukes bare når brukeren klikker på dem. Innstillingen for automatisk Divvun-retting gjelder første runde før Gemini.
- **Lange tekster:** Tekster på opptil 50 000 tegn deles automatisk opp ved linjeskift eller mellomrom før behandling og settes sammen igjen. Divvuns grammatikkontroll deles videre i biter på opptil 1 200 tegn (inntil fire samtidige kall per kontroll). En feil i én bit stopper ikke de andre kontrollene eller resten av pipelinen. «Språkvask & råd» viser hva som ikke ble kontrollert; stavekontrollen kjøres separat. Markeringene viser bare tilgjengelige funn. Fremdriften viser hvilken tekstdel som behandles.
- **Raskt webgrensesnitt:** Ingen ekstern JS-kompilering ved oppstart, tastatur- og skjermleserstøtte, avbryt-knapp (`AbortController`) og nøkkelhåndtering via HTTP-headere. Enkelte nettlesere kan laste polyfills fra eksterne CDN-er; se krediteringene nederst.
- **Språkvalg:** Grensesnitt, fremdrift og lokale språkråd følger valgt kildespråk (norsk, svensk, finsk, engelsk eller nordsamisk). Gemini-genererte råd og merknader fra eksterne tjenester kan foreløpig ha et annet språk.

### Vedlikehold av språkversjoner

Når du skal rette eller forbedre en oversettelse i grensesnittet, oppdater den tilsvarende teksten i alle fem språkene:

- `static/ui-strings.js` inneholder synlige grensesnittstekster, statusmeldinger, tilgjengelighetstekster og de innebygde språkreglene. Nøklene skal være identiske for `nor`, `swe`, `fin`, `eng` og `sme`.
- `static/tips.json` inneholder oversettelsene av lokale, automatiske språkråd. Behold regelenes ID-er og `{plassholdere}` uendret; de kobles til resultatene fra `local_heuristic_checks` i `main.py`.
- `static/server-messages.json` inneholder fremdriftsmeldinger og servergenererte, lokale varsler. Hvert element i en språkoversettelse følger rekkefølgen norsk, svensk, finsk, engelsk og nordsamisk.
- `static/app.js` kobler katalogtekstene til grensesnittet og håndterer språkbytte. Legg nye synlige tekster i katalogen, ikke som enkeltstående strenger i visningslogikken.

Kontroller at plassholdere som `{count}` finnes i alle språkversjoner, og kjør testene etter endringer:

```bash
pytest
```

Gemini-genererte råd og forklaringer direkte fra eksterne tjenester er ikke dekket av disse katalogene ennå.

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

I Innstillinger finnes en veiledning ved Gemini API-nøkkelfeltet. En nøkkel som legges inn der, lagres i nettleseren; tøm feltet og klikk utenfor for å fjerne den fra nettleseren.

### Feilsøking og logger

Docker Compose lagrer tekniske hendelser i det vedvarende volumet `diagnostic-logs`. Se den løpende loggen med:

```bash
docker compose exec sami-translator tail -f /app/logs/diagnostics.log
```

Loggen har tidsstempel og tilfeldig forespørsels-ID, samt blant annet tekstlengde, språk, tjenestestatus, feiltyper, delnummer og varighet. Den lagrer ikke tekst, ordliste, API-nøkler, IP-adresser eller feiltekster fra tjenestene. Filen roteres ved 5 MB; opptil fire eldre filer beholdes. Volumet beholdes ved vanlig omstart og gjenoppbygging. Beskytt likevel tilgang til loggene og slett dem etter behov. `docker compose down -v` sletter volumet.

Ved kjøring uten Compose kan fil-logg aktiveres ved å sette miljøvariabelen `JORGALEADDJI_LOG_DIR` til en skrivbar mappe med begrenset tilgang. Den vanlige konsollloggen vises fortsatt med `docker compose logs -f sami-translator` og kan inneholde mer detaljerte feilmeldinger fra tjenestene.

## Kjøre tester

```bash
docker compose exec sami-translator pytest
# eller lokalt i et virtuelt miljø:
pytest
```

For JavaScript-testene lokalt kreves Node.js:

```bash
node --test test_suggestions.cjs
```

## Eksterne tjenester og kreditering

Takk til utviklerne og språkfagmiljøene bak tjenestene og ressursene prosjektet bruker:

- **[TartuNLP / Universitetet i Tartu](https://tartunlp.ai/)** – maskinoversettelse til nordsamisk. Se [API-dokumentasjonen](https://api.tartunlp.ai/translation/docs) og [prosjektets dokumentasjon](https://github.com/TartuNLP/translation-api).
- **[Divvun](https://divvun.no/), UiT Norges arktiske universitet** – grammatikk- og stavekontroll gjennom [Divvun API](https://github.com/divvun/divvun-api).
- **[Google Gemini API](https://ai.google.dev/gemini-api/docs)** – oversettelse og språkvask når Gemini er aktivert. [Google Gen AI SDK](https://github.com/googleapis/python-genai) brukes til API-kall; se også [vilkårene for Gemini API](https://ai.google.dev/gemini-api/terms).
- **[Sátni.org](https://satni.org/)** – ord- og termoppslag som åpnes på brukerens initiativ. Se [Sátni.org-prosjektet](https://github.com/divvun/satni-frontend).
- **[esm.sh](https://esm.sh/)** – leverer `@microsoft/focusgroup-polyfill` til nettlesere som trenger den. **[UNPKG](https://unpkg.com/)** leverer [OddBirds popover-polyfill](https://github.com/oddbird/popover-polyfill), med [BSD-3-Clause-lisens](https://github.com/oddbird/popover-polyfill/blob/main/LICENSE), når nettleseren mangler støtte.
- **[Sámediggi](https://samediggi.no) / [Sámi Giellagáldu](https://giella.org) og [NRK Sápmi](https://nrk.no/sapmi)** – språkfaglig normgrunnlag, som beskrevet under «Språklig normgrunnlag». Referansefilene i `.agent/skills/giellaverdde/references/` oppgir også kilder for de enkelte språkreglene.

Tjenestene har egne vilkår og personvernregler. Tekst kan sendes til TartuNLP, Divvun og Google som del av behandlingen; vurder derfor om teksten kan deles med disse leverandørene. Sjekk gjeldende bruksvilkår, lisens og eventuelle krav om synlig kreditering hos hver leverandør før offentlig drift. Kreditering her er ikke en bekreftelse på at alle slike krav eller rettigheter til referansematerialet er avklart.
