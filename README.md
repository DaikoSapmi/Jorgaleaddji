# Jorgaleaddji & Divvun Studio (Gemini 3.1 Edition v9) – Mac Mini M1

Et helhetlig oversettelses-, språkvask- og korrekturverktøy for nordsamisk (*davvisámegiella*), spesialtilpasset Docker på Apple Silicon (Mac Mini M1) og konfigurert på **port 8090**.

## Støttede arbeidsmåter:
1. **Norsk &rarr; Davvisámegiella:** Oversettelse med TartuNLP, Divvun API og Gemini språkvask.
2. **Svensk &rarr; Davvisámegiella:** Oversettelse fra svensk via TartuNLP, Divvun og Gemini språkvask.
3. **Finsk &rarr; Davvisámegiella:** Oversettelse fra finsk via TartuNLP, Divvun og Gemini språkvask.
4. **Engelsk &rarr; Davvisámegiella:** Oversettelse fra engelsk via TartuNLP og Gemini språkvask.
5. **Nordsamisk &rarr; Davvisámegiella (Direkte språkvask & korrektur):** Språkvask av nordsamisk tekst som fikser skrivefeil, bøyinger, tegnsetting, verbspråk og stil i tråd med de offisielle normene.

## Språklig normgrunnlag for språkvask:
Systemet følger de offisielle normene og anbefalingene for nordsamisk:
1. **Sámediggi & Sámi Giellagáldu: Riektačállinrávvagat (reviderejuvvon 2019)** – Offisielle regler for tegnsetting (komma, anførselstegn, tankestrek, skråstrek), sammensatte ord og flerordsuttrykk (syntagmer), store/små forbokstaver (stillinger, nasjonaliteter, epoker), tall- og datobøyning, fremmedord og lånord, samt enklitiske partikler.
2. **NRK Sámi Giellagiehtagirji** – Verbspråk mot substantivsyke, aktiv form mot unødvendig passiv, refleksivt *su* vs. *iežas*, spørrepartikkel *-go*, sammenligningsord *go* (ikke *enngo*), og kasusstyring.
3. **UiT Giellatekno & Oahpa-grammatikken** – Morfologisk og syntaktisk presisjon samkjørt med Divvun API.

## Pipeline-trinn:
1. *Klargjøring / TartuNLP Råutkast* (henter førsteutkast fra translate.ut.ee for norsk, svensk, finsk og engelsk; hoppes over ved samisk kildetekst)
2. *Divvun 1. sjekk* (rettskriving og grammatikk via GiellaLT API)
3. *Gemini Språkvask* (idiomatisk omskriving etter Riektačállinrávvagat og Giellagiehtagirji)
4. *Divvun Sluttsjekk & Autoretting* (sikrer feilfri ortografi i sluttproduktet)
