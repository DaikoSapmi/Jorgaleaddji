import os
import re
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Dáro-Davvisámi Jorgaleaddji & Divvun (Gemini Edition v9)")

TARTU_API_URL = "https://api.tartunlp.ai/translation/v2"
DIVVUN_GRAMMAR_URL = "https://api-giellalt.uit.no/grammar/se"
DIVVUN_SPELLER_URL = "https://api-giellalt.uit.no/speller/se"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")

SAMI_GUIDELINES_PROMPT = """
Du er en ekspertoversetter og språkvasker fra norsk til nordsamisk (davvisámegiella), 
opplært etter:
- Sámediggi & Sámi Giellagáldu: Riektačállinrávvagat (reviderejuvvon 2019)
- NRK Sámi Giellagiehtagirji
- UiT Giellatekno og Oahpa-grammatikken

Når du reviderer og oversetter teksten, MÅ du følge disse reglene og rettskrivingsnormene nøye:

1. FULLSTENDIGHET:
   Du MÅ oversette ALLE avsnitt, sitater og overskrifter i den norske kildeteksten. Ikke hopp over et eneste avsnitt eller en setning!

2. VEARBAGIELLA (Verbspråk mot substantivsyke):
   Unngå norsk substantivsyke! Gjør tunge norske substantivuttrykk om til samiske verb og verbavledninger (-goahtit, -stit, -lit, -hit, -ut, -nit, -odit, -muvvat).
   Eks: "Statsforvalteren har gitt fellingstillatelse på bjørn" -> "Stáhtahálddašeaddji lea addán lobi báhčit guovžža" eller "lea suovvan báhčit guovžža".

3. AKTIIVA GIELLA (Aktivt språk):
   Hvis en passiv setning med -(oj)uvvot nevner hvem som utfører handlingen (subjekt/agent), MÅ setningen skrives om til aktiv ("Ášši meannuduvvui suohkanstivrras" -> "Suohkanstivra meannudii ášši").
   Passiv med -hallat brukes kun når noe er uheldig for den som rammes, med agenten i illativ ("Áhkku vuojáhalai boastabiilii").

4. SU vs. IEŽAS (Refleksivt pronomen):
   Bruk refleksivt pronomen (iežan, iežat, iežas, iežame, iežade, iežaska, iežamet, iežadet, iežaset) når eieren er setningens subjekt ("Son borrá iežas njálgáid").
   Bruk su/sudno/sin KUN når det viser til noen andre enn subjektet ("Son borrá su njálgáid"). Habitiv følger samme regel ("Mus lea alddán dállu", "Sudnos lea alddiska biila").

5. LOHKU + SUBSTANTIIVA & LOGUID SOJAHEAPMI (Tallord og tallbøying):
   - Etter tallord over 1 (2, 3... samt moadde, máŋga, galle) skal substantivet stå i ENTALL GENITIV (f.eks. "guokte olbmo", "vihtta viesu"), mens verbet står i flertall ("Guokte olbmo bohte").
   - I andre kasus: Merk at i entall lokativ og illativ står tallordet i genitiv mens substantivet står i lokativ/illativ ("dan guovtti mánnái", "golmma mánás").
   - Tall fra 1 til 10 skrives med bokstaver i løpende tekst ("ovtta", "guokte", "golbma"...).
   - Tall under 1 million skrives i ETT ord med bokstaver ("čiežalogigolbma", "guoktečuođi", "vihttaduhát"), over 1 mill. i to ord ("logi miljovnna").
   - Bøying av tall med kolon (uten mellomrom): "16:i" (illativ), "16:s" (lokativ), "16:in" (komitativ), "16:t" (nominativ flertall).
   - Ordenstall bøyes med -da/-dii/-dis: "16." (nominativ), "16:da" (gen/akk), "16:dii" (illativ), "16:dis" (lokativ).
   - Prosent og måleenheter: Alltid mellomrom foran prosenttegn og forkortelser ("25 %", "10 kg", "50 km"). I løpende tekst skrives "proseantamearri" (aldri "%-mearri").

6. GOALLOSSÁNIT & SÁTNEGIHPUT (Sammensatte ord ifølge Riektačállinrávvagat 2019):
   - Skrives i ett ord når forleddet er nominativ entall ("gilvoviehkan", "lávllagirji", "bohccobiergu").
   - Bindestrek brukes når et ledd er navn, tall, bokstav, forkortelse eller fremmedord ("Elle-oambealli", "1950-lohku", "25-jahkásaš", "C-vitamiidna", "e-boasta", "ON-beaivi").
   - MELLOMROM FORAN BINDESTREK ved flerords forledd (syntagme): "Min Áigi -aviisa", "New Yorka -mátki", "Boeing 737 -girdi", "Paulus Utsi -áššedovdi". (Men "Ánne-Máret-muoŧŧá").
   - Felles ledd: "mánáid- ja nuoraidskuvla", "sáme-, suoma- ja ruoŧagiella".
   - Retnings- og stedsord: "duogábealde", "vuolábeallai" (ett ord ved sammensetningsform), men "Eanodaga bealde", "dán beallai", "Ruošša beale" (to ord ved genitiv).

7. GASKAMEARKKAT & TEGNSETTING (Riektačállinrávvagat 2019):
   - Komma (Rihkku):
     * Alltid komma etter leddsetning (oalgecealkka) når den står først ("Go áhčči boahtá, de mii herskkostallat", "Jos mii eat livčče vuolgán, de...").
     * Komma foran "muhto" ("Son livččii viššal, muhto sus ii leat dilli").
     * Komma ved apposisjoner og presiseringer ("Iŋgá, ovddit jagiid vuoiti, bođii...").
     * ALDRI komma mellom setningsledd med felles subjekt eller verbal ("Elle finai vuos buvddas ja de manai ruoktot").
     * ALDRI komma i helt korte leddsetninger ("Dat vulggii go mun bohten").
   - Sitattegn (Aisttonmearkkat): Bruk alltid typografiske nordsamiske/nordiske sitattegn ”...” (ikke engelske “...”). Sitat i sitat bruker apostrof ’...’.
   - Tankestrek (Jurddasáhcu –): Bruk tankestrek uten mellomrom ved avstand, tidsintervall og sidetall ("1995–1997", "Romsa–Ivgubahta 120 km", "siidduin 25–100").
   - Skråstrek (/): Betyr "dahje" (eller), ALDRI "ja" ("mánát/nuorat" = mánát dahje nuorat).

8. STUORA JA UNNA ÁLGORBUSTÁVAT (Store og små forbokstaver):
   - Liten forbokstav (unna álgobustávva):
     * Stillinger og titler: "direktevra Hætta", "stáhtaministtar", "presideanta", "advokáhtta", "gonagas Harald", "sátnejođiheaddji".
     * Nasjonaliteter, folkeslag, språk: "sápmelaččat", "davvisámegiella", "norgalaš", "suopmelaš".
     * Ukedager, måneder, høytider: "bearjadat", "guovvamánnu", "beassážat".
     * Historiske hendelser og epoker: "eváhkkodálvi", "nubbi máilmmisoahti", "ruovdeáigi".
     * Etter kolon når det ikke følger en fullstendig selvstendig setning ("njeallje ivnni: alit, ruoksat, fiskat ja ruoná").
   - Stor forbokstav (stuora álgobustávva):
     * Egennavn på personer, institusjoner, kommuner og organisasjoner ("Sámediggi", "Sámi allaskuvla", "Kárášjoga gielda", "Ráđđehus").
     * Etter kolon ved fullstendig direkte tale eller replikk ("Oahpaheaddji álggahii: ”Dál dii lehpet álgán nuoraidskuvlii!”").

9. VIERISSÁNIT & EARÁ GIELAID NAMAID SOJAHEAPMI (Fremmedord og navn):
   - Utenlandske personnavn skrives slik bæreren skriver dem, og bøyes med samiske endelser:
     * Navn på -a/-i beholder vokalen: "Klara : Klaras : Klarai", "Sari : Saris : Sarii".
     * Énstavelsesnavn bøyes med -a-: "Per : Pera : Perii/Perai : Peras", "Liv : Liva : Livii : Livas".
     * Navn på konsonant: "Astrid : Astrida : Astridii", "Øivind : Øivinda : Øivindii".
   - Fremmedord på -iija ("filosofiija", "biologiija", "energiija") har INGEN stadieveksling ("filosofiijas", "energiijain").
   - Stedsnavn ender ALDRI på -iija ("Tansania", "Italia", ikke Tansaniija).
   - Unngå norsk binde-s i sammensetninger ("eksámenbargu", ikke eksamensbargu).

10. LAKTAPARTIHKKALAT (Enklitiske partikler):
    - Faste leksemer MÅ skrives i ett ord: "dieđusge", "dattetge", "iešguhtege", "oktage", "veaháge", "veahášge", "makkárge", "mannege", "matge", "miige", "mihkkege", "movtge", "goitge", "almmatge", "juogo", "jusgo".
    - Spørrepartikkelen -go henger fast på verbet ("Boahtágo son odne?").
    - Konjunksjonen "go" (når, da, som, enn) skrives ALLTID frittstående ("Ánte lea boarráseabbo go Risten").
    - Bruk ALDRI "jos" i indirekte spørsmål ("In dieđe boahtágo son odne", ikke "jos").

11. SPØRREORD & KONJUNKSJONER (Dahje vs. Vai):
    - Bruk "vai" i spørresetninger ("Boađátgo ihttin vai bearjadaga?").
    - Bruk "dahje" i fortellende setninger.

12. EKTUI vs. HÁRRÁI / DÁFUS / ILLATIV:
    - "Ektui" brukes kun ved reell sammenligning ("Áhčis ektui son lea stuoris"). Bruk "hárrái", "dáfus" eller ren illativ ("Maid don dajat dien áššái?").

13. REKŠUVDNAVEARBBAT (Kasusstyring):
    - Illativ: liikot, luohttit, álgit, guoskat, heivet, suhttat, darvánit.
    - Lokativ: beroštit, ballat, heaitit, dolkat, váruhit, nohkkot.
    - Komitativ: humadit, háleštit.

14. RIEKTAČÁLLIN & DATO:
    - Dato skrives med måned i genitiv + ordenstall + beaivvi ("geassemánu 7. beaivvi 2026" eller "geassemánu 7. b. 2026").
"""

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "nor"  # "nor", "eng", eller "sme"
    use_llm: bool = True
    auto_apply_divvun: bool = True
    api_key: Optional[str] = None
    model: Optional[str] = None

class ProofreadRequest(BaseModel):
    text: str

def extract_gemini_json(raw_text: str) -> dict:
    """Robust JSON-utpakker som håndterer markdown-kodeblokker, tenkeblokker og ueskaperte linjeskift fra Gemini."""
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    # Fjern evt. ```json ... ``` rundt svaret
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Forsøk 1: Direkte json.loads
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Forsøk 2: Finn ytterste { ... } i teksten
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx:end_idx + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Forsøk 3: Regex-uthenting av "final_translation" og "improvements" hvis JSON har rå linjeskift eller småfeil
    ft_match = re.search(
        r'"final_translation"\s*:\s*"((?:[^"\\]|\\.)*)"',
        cleaned,
        flags=re.DOTALL
    )
    if ft_match:
        raw_ft = ft_match.group(1)
        try:
            ft_val = json.loads(f'"{raw_ft}"')
        except Exception:
            ft_val = raw_ft.replace("\\n", "\n").replace('\"', '"')

        imps = []
        imp_block = re.search(r'"improvements"\s*:\s*\[(.*?)\]', cleaned, flags=re.DOTALL)
        if imp_block:
            for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', imp_block.group(1), flags=re.DOTALL):
                try:
                    imps.append(json.loads(f'"{m.group(1)}"'))
                except Exception:
                    imps.append(m.group(1).replace('\"', '"'))
        return {"final_translation": ft_val, "improvements": imps}

    return {}

async def fetch_available_gemini_models(api_key: str) -> List[dict]:
    if not api_key or api_key == "din_gemini_api_nokkel_her":
        return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                valid = []
                for m in models:
                    methods = m.get("supportedGenerationMethods", [])
                    name = m.get("name", "").replace("models/", "")
                    if "generateContent" in methods and name.startswith("gemini-") and "tts" not in name and "image" not in name and "embedding" not in name:
                        valid.append({
                            "id": name,
                            "display_name": m.get("displayName", name)
                        })
                valid.sort(key=lambda x: x["id"], reverse=True)
                return valid
        except Exception:
            pass
    return []

@app.get("/api/config")
async def get_config(api_key: Optional[str] = None):
    active_key = (api_key or GEMINI_API_KEY).strip()
    has_key = bool(active_key and active_key != "din_gemini_api_nokkel_her")
    available_models = await fetch_available_gemini_models(active_key) if has_key else []
    return {
        "env_model": GEMINI_MODEL,
        "has_env_key": bool(GEMINI_API_KEY and GEMINI_API_KEY != "din_gemini_api_nokkel_her"),
        "available_models": available_models
    }

async def call_tartu_mt(text: str, src: str = "nor", tgt: str = "sme") -> str:
    """Trinn 1: Kaller TartuNLP (translate.ut.ee) avsnitt for avsnitt så lange tekster bevarer struktur."""
    paragraphs = text.split("\n")
    translated_paragraphs = []
    if src in ["swe", "sv"]:
        src_candidates = ["swe", "sv"]
    elif src in ["fin", "fi"]:
        src_candidates = ["fin", "fi"]
    elif src in ["eng", "en"]:
        src_candidates = ["eng", "en"]
    else:
        src_candidates = [src, "nob", "no"]
    async with httpx.AsyncClient(timeout=45.0) as client:
        # Prøv først hele teksten i ett kall hvis den ikke er for lang
        if len(text) < 4500:
            for src_code in src_candidates:
                try:
                    resp = await client.post(
                        TARTU_API_URL,
                        json={"text": text, "src": src_code, "tgt": tgt}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if "result" in data and data["result"]:
                            return data["result"]
                except Exception:
                    continue
        # Fallback for veldig lange tekster: del opp
        for p in paragraphs:
            if not p.strip():
                translated_paragraphs.append("")
                continue
            done = False
            for src_code in src_candidates:
                try:
                    resp = await client.post(
                        TARTU_API_URL,
                        json={"text": p, "src": src_code, "tgt": tgt}
                    )
                    if resp.status_code == 200 and resp.json().get("result"):
                        translated_paragraphs.append(resp.json()["result"])
                        done = True
                        break
                except Exception:
                    continue
            if not done:
                translated_paragraphs.append(p)
    return "\n".join(translated_paragraphs) if translated_paragraphs else ""

async def call_divvun_grammar(text: str) -> dict:
    """Trinn 2: Kaller Divvun GiellaLT API for grammatikk- og stavekontroll."""
    if not text.strip():
        return {"text": text, "errs": []}
    async with httpx.AsyncClient(timeout=35.0) as client:
        try:
            resp = await client.post(
                DIVVUN_GRAMMAR_URL,
                json={"text": text},
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            return {"text": text, "errs": [], "api_error": str(e)}
    return {"text": text, "errs": []}


def apply_divvun_suggestions_smart(text: str, errs: list, protect_proper_nouns: bool = True) -> str:
    """Bruker Divvuns forslag automatisk, men beskytter ukjente egennavn (f.eks. 'Warth') mot å bli byttet ut med tilfeldige ord."""
    if not errs:
        return text
    sorted_errs = sorted(errs, key=lambda x: x.get("start_index", 0), reverse=True)
    corrected = text
    for err in sorted_errs:
        suggestions = err.get("suggestions", [])
        start = err.get("start_index")
        end = err.get("end_index")
        err_word = err.get("error_text", "")
        err_code = err.get("error_code", "")
        if not suggestions or start is None or end is None:
            continue
        # Hvis det er en ren stavefeil ("typo") på et ord med stor forbokstav midt i en setning (ofte et norsk etternavn/fornavn),
        # sjekk at vi ikke blindt bytter ut navnet med et helt annet samisk ord.
        if protect_proper_nouns and err_code == "typo" and err_word[:1].isupper() and start > 0 and text[start-1:start] not in [".", "!", "?", "\n"]:
            continue
        corrected = corrected[:start] + suggestions[0] + corrected[end:]
    return corrected

async def call_gemini_final_divvun_pass(
    norwegian_text: str,
    gemini_draft: str,
    divvun_errs: list,
    override_key: Optional[str] = None,
    override_model: Optional[str] = None,
    source_lang: str = "nor"
) -> Optional[str]:
    """Hvis Divvun finner merknader i Geminis tekst, ber vi Gemini rette akkurat disse Divvun-merknadene."""
    active_key = (override_key or GEMINI_API_KEY).strip()
    if not active_key or not divvun_errs:
        return None

    compact_errs = [
        {
            "error_text": e.get("error_text"),
            "title": e.get("title"),
            "description": e.get("description"),
            "suggestions": (e.get("suggestions") or [])[:5]
        }
        for e in divvun_errs
    ]

    source_heading_map = {
        "sme": "NORDSAMISK KILDE",
        "eng": "ENGELSK KILDE",
        "swe": "SVENSK KILDE",
        "fin": "FINSK KILDE",
        "nor": "NORSK KILDE"
    }
    source_heading = source_heading_map.get(source_lang, "NORSK KILDE")
    prompt = f"""Her er den nordsamiske teksten du bearbeider, sammen med merknader fra UiT Divvun grammatikk- og stavekontroll.

{source_heading}:
{norwegian_text}

DIN NORDSAMISKE TEKST:
{gemini_draft}

MERKNADER FRA DIVVUN SOM MÅ FIKSES:
{json.dumps(compact_errs, ensure_ascii=False)}

Oppgave:
Rett opp alle reelle stave-, bøyings-, stadievekslings-, kasus- og tegnsettingsfeil som Divvun har påpekt, så godt det lar seg gjøre, uten å ødelegge personnavn (som f.eks. norske etternavn) eller den gode samiske setningsoppbyggingen.
Returner KUN JSON med nøkkelen "corrected_text".
"""
    model_to_use = "gemini-3.1-flash-preview"
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_use}:generateContent?key={active_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": SAMI_GUIDELINES_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "corrected_text": {"type": "STRING"}
                },
                "required": ["corrected_text"]
            }
        }
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        for cand in [model_to_use, (override_model or GEMINI_MODEL).strip(), "gemini-2.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand}:generateContent?key={active_key}"
                resp = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
                if resp.status_code == 200:
                    parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for p in reversed(parts):
                        if not p.get("thought", False) and p.get("text"):
                            parsed = json.loads(p["text"])
                            if parsed.get("corrected_text"):
                                return parsed["corrected_text"]
            except Exception:
                continue
    return None

def apply_divvun_suggestions(text: str, errs: list) -> str:
    """Bruker Divvuns beste forslag automatisk (bakfra så indekser ikke forskyves)."""
    if not errs:
        return text
    sorted_errs = sorted(errs, key=lambda x: x.get("start_index", 0), reverse=True)
    corrected = text
    for err in sorted_errs:
        suggestions = err.get("suggestions", [])
        start = err.get("start_index")
        end = err.get("end_index")
        if suggestions and start is not None and end is not None:
            corrected = corrected[:start] + suggestions[0] + corrected[end:]
    return corrected

def local_heuristic_checks(norwegian_text: str, sami_text: str) -> List[dict]:
    """Lokal regelsjekker basert på Sámi Giellagáldu Riektačállinrávvagat (2019) og NRK Sámi Giellagiehtagirji."""
    tips = []
    
    if re.search(r"\b(in|it|ii|ean|eahppi|eaba|eat|ehpet|eai)\s+dieđe\s+jos\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Partihkkal -go vs. konjunkšuvdna jos",
            "message": "Unngå 'jos' etter 'in dieđe' i indirekte spørsmål. Bruk spørrepartikkelen '-go' på verbet (f.eks. 'In dieđe boahtágo son odne').",
            "reference": "Giellagiehtagirji s. 18 / Riektačállinrávvagat s. 70"
        })
    if re.search(r"\benngo\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Konjunkšuvdna go",
            "message": "Unngå blandingsordet 'enngo'. Bruk kun 'go' ved sammenligning (f.eks. 'buoret go dát').",
            "reference": "Giellagiehtagirji s. 19 / Riektačállinrávvagat s. 70"
        })
    if "?" in sami_text and re.search(r"\bdahje\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Dahje vs. Vai",
            "message": "I spørresetninger skal man bruke 'vai' i stedet for 'dahje' (f.eks. 'Boađátgo ihttin vai bearjadaga?').",
            "reference": "Giellagiehtagirji s. 22 / Riektačállinrávvagat s. 32"
        })
    if re.search(r"\bektui\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Ektui vs. hárrái / dáfus / illativ",
            "message": "Sjekk om 'ektui' brukes til reell sammenligning. Ofte passer 'hárrái', 'dáfus' eller ren illativ bedre.",
            "reference": "Giellagiehtagirji s. 22"
        })
    if re.search(r"\b(gávnnahii|gávnnahit|gávnnahan)\s+olggos\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Norsk påvirkning (olggos)",
            "message": "På samisk sier man bare 'gávnnahii' (fant ut), uten 'olggos'.",
            "reference": "Giellagiehtagirji s. 9"
        })
    if re.search(r"\bolggosoaidnit\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Norsk påvirkning (olggosoaidnit)",
            "message": "Unngå 'olggosoaidnit' (se ut). Bruk bare 'oaidnit' ('Makkár dat lea oaidnit?').",
            "reference": "Giellagiehtagirji s. 9 & 16"
        })
    if re.search(r"\w+(juvvon|juvvui|juvvo|juvvojit)\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Aktiiva giella (Passiv -> Aktiv)",
            "message": "Teksten inneholder et passivt verb på -(oj)uvvot. Sjekk om den som utfører handlingen er nevnt – i så fall bør setningen snus til aktiv!",
            "reference": "Giellagiehtagirji s. 15 / Ordavledning s. 2"
        })
    # Sjekkpunkter fra Sámi Giellagáldu Riektačállinrávvagat (2019)
    if re.search(r"\b(dieđus|dattet|iešguhte|okta|veahá|veaháš|makkár|manne|masa|mihkke|movt|goit)\s+ge\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Laktapartihkkalat (sammenskriving)",
            "message": "Faste partikkelord skal skrives i ett ord: 'dieđusge', 'dattetge', 'iešguhtege', 'oktage', 'veaháge', 'mihkkege', 'goitge'.",
            "reference": "Riektačállinrávvagat s. 71"
        })
    if re.search(r"\b\d+%", sami_text):
        tips.append({
            "rule": "Proseantamearka (gaska)",
            "message": "Det skal være et mellomrom mellom tallet og prosenttegnet (f.eks. '25 %', ikke '25%'). I løpende tekst skrives 'proseantamearri' (ikke '%-mearri').",
            "reference": "Riektačállinrávvagat s. 41"
        })
    if re.search(r"\b%-(mearri|mearre)\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Proseantamearri vs. %-mearri",
            "message": "Skriv 'proseantamearri' med bokstaver, ikke '%-mearri'.",
            "reference": "Riektačállinrávvagat s. 41"
        })
    if re.search(r"\b[A-ZÁČĐŊŠŦŽ][a-záčđŋšŧž]+iija\b", sami_text):
        tips.append({
            "rule": "Báikenamat eai lohpa -iija",
            "message": "Stedsnavn ender aldri på '-iija' på samisk. Skriv f.eks. 'Tansania', 'Italia', 'Spania' (ikke Tansaniija).",
            "reference": "Riektačállinrávvagat s. 43"
        })
    if re.search(r"[“”]", sami_text):
        tips.append({
            "rule": "Aisttonmearkkat (Sitattegn)",
            "message": "På samisk brukes typografiske sitattegn ”...” (som i norsk), ikke engelske “...”.",
            "reference": "Riektačállinrávvagat s. 24"
        })
    return tips

async def call_gemini_refiner(
    norwegian_text: str,
    tartu_draft: str,
    divvun_corrected: str,
    divvun_errs: list,
    local_tips: list,
    override_key: Optional[str] = None,
    override_model: Optional[str] = None,
    source_lang: str = "nor"
) -> dict:
    """Trinn 3: Foredler oversettelsen eller språkvasker nordsamisk tekst ved hjelp av Google Gemini API."""
    active_key = (override_key or GEMINI_API_KEY).strip()
    requested_model = (override_model or GEMINI_MODEL).strip() or "gemini-3.1-pro-preview"

    if not active_key or active_key == "din_gemini_api_nokkel_her":
        return {
            "final_translation": divvun_corrected or tartu_draft,
            "improvements": [
                "GEMINI_API_KEY er ikke lagt inn ennå (legg den i .env eller i innstillingene i grensesnittet). Viser tekst korrigert av Divvun API."
            ],
            "llm_active": False,
            "used_model": None
        }

    # Begrens antall Divvun-feil vi sender inn i prompten så den ikke blir unødig stor på lange artikler
    compact_errs = [
        {
            "error_text": e.get("error_text"),
            "title": e.get("title"),
            "suggestions": (e.get("suggestions") or [])[:3]
        }
        for e in divvun_errs[:40]
    ]

    if source_lang == "sme":
        user_prompt = f"""
NORDSAMISK KILDETEKST SOM SKAL SPRÅKVASKES OG KORRIGERES:
{norwegian_text}

UTKAST ETTER FØRSTE DIVVUN-KORREKTUR:
{divvun_corrected}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER (Giellagiehtagirji & Riektačállinrávvagat):
{json.dumps(local_tips, ensure_ascii=False)}

Oppgave:
1. Gjennomfør en grundig språkvask og korrektur av den nordsamiske kildeteksten. Rett alle skrivefeil, bøyingsfeil, tegnsettingsfeil og grammatiske svakheter i henhold til normene fra Sámi Giellagáldu (Riektačállinrávvagat 2019), NRK Sámi Giellagiehtagirji og UiT Giellatekno/Oahpa.
2. Forbedre setningsoppbyggingen: snu passiv til aktiv der agenten er nevnt, motvirk substantivsyke med naturlige verbavledninger, og kontroller korrekt bruk av iežas vs. su, partikkelen -go, tallord og sammensetninger.
3. Bevar tekstenes opprinnelige mening, stil og innhold fullstendig – ikke utelat avsnitt og ikke legg til nytt faktuelt innhold.
4. Returner svaret som gyldig JSON med nøklene "final_translation" (den ferdig vaskede teksten) og "improvements" (korte punkter på norsk som forklarer de viktigste språklige forbedringene).
"""
    elif source_lang == "swe":
        user_prompt = f"""
SVENSK KILDE (ALLE avsnitt og sitater skal oversettes til nordsamisk):
{norwegian_text}

RÅOVERSETTELSE FRA TARTUNLP (Svensk -> Nordsamisk):
{tartu_draft}

ETTER DIVVUN KORREKTUR:
{divvun_corrected}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER:
{json.dumps(local_tips, ensure_ascii=False)}

Oppgave:
1. Lag en optimal, naturlig og idiomatisk nordsamisk oversettelse av HELE den svenske kildeteksten (pass nøye på at absolutt alle avsnitt og sitater blir med!).
2. Bruk TartuNLP- og Divvun-utkastet som hjelp, men skriv om der det er nødvendig for å unngå ord-for-ord-oversettelse, passiv-syke eller substantivsyke. Følg normene fra Sámi Giellagáldu (Riektačállinrávvagat 2019) og NRK Sámi Giellagiehtagirji.
3. Returner svaret som gyldig JSON med nøklene "final_translation" og "improvements".
"""
    elif source_lang == "fin":
        user_prompt = f"""
FINSK KILDE (ALLE avsnitt og sitater skal oversettes til nordsamisk):
{norwegian_text}

RÅOVERSETTELSE FRA TARTUNLP (Finsk -> Nordsamisk):
{tartu_draft}

ETTER DIVVUN KORREKTUR:
{divvun_corrected}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER:
{json.dumps(local_tips, ensure_ascii=False)}

Oppgave:
1. Lag en optimal, naturlig og idiomatisk nordsamisk oversettelse av HELE den finske kildeteksten (pass nøye på at absolutt alle avsnitt og sitater blir med!).
2. Bruk TartuNLP- og Divvun-utkastet som hjelp, men skriv om der det er nødvendig for å unngå ord-for-ord-oversettelse, passiv-syke eller substantivsyke. Følg normene fra Sámi Giellagáldu (Riektačállinrávvagat 2019) og NRK Sámi Giellagiehtagirji.
3. Returner svaret som gyldig JSON med nøklene "final_translation" og "improvements".
"""
    elif source_lang == "eng":
        user_prompt = f"""
ENGELSK KILDE (ALLE avsnitt og sitater skal oversettes til nordsamisk):
{norwegian_text}

RÅOVERSETTELSE FRA TARTUNLP (Engelsk -> Nordsamisk):
{tartu_draft}

ETTER DIVVUN KORREKTUR:
{divvun_corrected}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER:
{json.dumps(local_tips, ensure_ascii=False)}

Oppgave:
1. Lag en optimal, naturlig og idiomatisk nordsamisk oversettelse av HELE den engelske kildeteksten (pass nøye på at absolutt alle avsnitt og sitater blir med!).
2. Bruk TartuNLP- og Divvun-utkastet som hjelp, men skriv om der det er nødvendig for å unngå ord-for-ord-oversettelse, passiv-syke eller substantivsyke. Følg normene fra Sámi Giellagáldu (Riektačállinrávvagat 2019) og NRK Sámi Giellagiehtagirji.
3. Returner svaret som gyldig JSON med nøklene "final_translation" og "improvements".
"""
    else:
        user_prompt = f"""
NORSK KILDE (ALLE avsnitt og sitater skal med i oversettelsen):
{norwegian_text}

RÅOVERSETTELSE FRA TARTUNLP:
{tartu_draft}

ETTER DIVVUN KORREKTUR:
{divvun_corrected}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER:
{json.dumps(local_tips, ensure_ascii=False)}

Oppgave:
1. Lag en optimal, naturlig og idiomatisk nordsamisk oversettelse av HELE den norske kildeteksten (pass nøye på at absolutt alle avsnitt og sitater blir med!).
2. Bruk TartuNLP- og Divvun-utkastet som hjelp, men skriv om der det er nødvendig for å unngå ord-for-ord-oversettelse, passiv-syke eller substantivsyke. Følg normene fra Sámi Giellagáldu (Riektačállinrávvagat 2019) og NRK Sámi Giellagiehtagirji.
3. Returner svaret som gyldig JSON med nøklene "final_translation" og "improvements".
"""

    payload = {
        "systemInstruction": {
            "parts": [{"text": SAMI_GUIDELINES_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "final_translation": {
                        "type": "STRING",
                        "description": "Den fullstendige, ferdige nordsamiske teksten med alle avsnitt."
                    },
                    "improvements": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Liste med korte punkter på norsk som forklarer de viktigste språklige forbedringene."
                    }
                },
                "required": ["final_translation", "improvements"]
            }
        }
    }

    fallback_candidates = [
        requested_model,
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-preview",
        "gemini-3.0-pro",
        "gemini-3.0-flash",
        "gemini-2.5-flash"
    ]
    models_to_try = list(dict.fromkeys(fallback_candidates))

    last_error_msg = ""
    # 180 sekunders timeout slik at Gemini 3.1 Pro med tenketid (thinking) på lange artikler aldri avbrytes før svaret kommer!
    async with httpx.AsyncClient(timeout=180.0) as client:
        tried_dynamic_list = False
        idx = 0
        while idx < len(models_to_try):
            candidate_model = models_to_try[idx]
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={active_key}"
            try:
                resp = await client.post(
                    gemini_url,
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        # Viktig for Gemini 3.1 Thinking-modeller:
                        # Parts kan inneholde en {"thought": true, "text": "..."} del FØR selve JSON-svaret!
                        json_text_candidate = ""
                        for p in reversed(parts):
                            if not p.get("thought", False) and p.get("text"):
                                json_text_candidate = p["text"]
                                break
                        if not json_text_candidate and parts:
                            json_text_candidate = parts[-1].get("text", "{}")

                        parsed = extract_gemini_json(json_text_candidate)
                        final_trans = parsed.get("final_translation")
                        improvements = parsed.get("improvements", [])

                        if final_trans and final_trans.strip():
                            if candidate_model != requested_model:
                                improvements.insert(
                                    0,
                                    f"Merk: '{requested_model}' var ikke tilgjengelig på nøkkelen, så systemet brukte '{candidate_model}'."
                                )
                            return {
                                "final_translation": final_trans,
                                "improvements": improvements,
                                "llm_active": True,
                                "used_model": candidate_model
                            }
                        else:
                            last_error_msg = f"Kunne ikke tolke JSON fra Gemini-svaret: {json_text_candidate[:200]}"
                            return {
                                "final_translation": divvun_corrected or tartu_draft,
                                "improvements": [last_error_msg],
                                "llm_active": False,
                                "used_model": candidate_model
                            }
                elif resp.status_code == 404:
                    last_error_msg = resp.text[:250]
                    if not tried_dynamic_list:
                        tried_dynamic_list = True
                        avail = await fetch_available_gemini_models(active_key)
                        for m in avail:
                            if m["id"] not in models_to_try:
                                models_to_try.append(m["id"])
                    idx += 1
                    continue
                else:
                    err_msg = resp.text[:250]
                    return {
                        "final_translation": divvun_corrected or tartu_draft,
                        "improvements": [f"Gemini API feilmelding for '{candidate_model}' ({resp.status_code}): {err_msg}"],
                        "llm_active": False,
                        "used_model": candidate_model
                    }
            except Exception as e:
                return {
                    "final_translation": divvun_corrected or tartu_draft,
                    "improvements": [f"Tidsavbrudd eller nettverksfeil mot Gemini API ({type(e).__name__}: {str(e)}). Prøv gjerne gemini-3.1-flash-preview på ekstra lange tekster."],
                    "llm_active": False,
                    "used_model": candidate_model
                }

    return {
        "final_translation": divvun_corrected or tartu_draft,
        "improvements": [f"Ingen Gemini-modell svarte. Siste feilmelding: {last_error_msg}"],
        "llm_active": False,
        "used_model": requested_model
    }

@app.post("/api/translate")
async def translate_pipeline(req: TranslateRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Teksten er tom.")

    src_lang = req.source_lang.lower().strip() if req.source_lang else "nor"
    is_sami_source = (src_lang == "sme")

    # Trinn 1: TartuNLP råoversettelse (hoppes over hvis kildeteksten allerede er nordsamisk)
    if is_sami_source:
        tartu_raw = req.text
    else:
        tartu_raw = await call_tartu_mt(req.text, src=src_lang, tgt="sme")
        if not tartu_raw:
            tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"

    # Trinn 2: Divvun grammatikk- og korrekturkontroll
    divvun_initial = await call_divvun_grammar(tartu_raw) if not tartu_raw.startswith("[") else {"errs": []}
    initial_errs = divvun_initial.get("errs", [])
    divvun_pre_corrected = apply_divvun_suggestions(tartu_raw, initial_errs) if req.auto_apply_divvun and not tartu_raw.startswith("[") else tartu_raw

    # Lokale språksjekker
    local_tips = local_heuristic_checks(req.text if not is_sami_source else "", divvun_pre_corrected if not divvun_pre_corrected.startswith("[") else "")

    # Trinn 3: Språkvask med Gemini
    llm_result = await call_gemini_refiner(
        req.text,
        tartu_raw,
        divvun_pre_corrected,
        initial_errs,
        local_tips,
        override_key=req.api_key,
        override_model=req.model,
        source_lang=src_lang
    ) if req.use_llm else {
        "final_translation": divvun_pre_corrected,
        "improvements": ["Gemini-språkvask deaktivert av bruker."],
        "llm_active": False,
        "used_model": None
    }

    gemini_text = llm_result["final_translation"]
    llm_succeeded = llm_result.get("llm_active", False)

    # Trinn 4: Kjør Divvun på Geminis tekst. Hvis Divvun har merknader og auto_apply_divvun er på,
    # fikser vi dem automatisk (først via en rask Gemini+Divvun-sløyfe, og deretter direkte med Divvun-forslagene)!
    final_divvun = await call_divvun_grammar(gemini_text)
    final_errs = final_divvun.get("errs", [])
    final_text = gemini_text

    if req.auto_apply_divvun and final_errs:
        initial_err_count = len(final_errs)
        if llm_succeeded:
            # La Gemini rette Divvun-merknadene intelligent først
            refined_by_divvun = await call_gemini_final_divvun_pass(
                req.text, gemini_text, final_errs, override_key=req.api_key, override_model=req.model, source_lang=src_lang
            )
            if refined_by_divvun:
                final_text = refined_by_divvun
                final_divvun = await call_divvun_grammar(final_text)
                final_errs = final_divvun.get("errs", [])

        # Hvis det fortsatt gjenstår konkrete Divvun-merknader med forslag, bruk Divvuns beste forslag direkte (men beskytt egennavn)
        if final_errs:
            final_text = apply_divvun_suggestions_smart(final_text, final_errs, protect_proper_nouns=True)
            final_divvun = await call_divvun_grammar(final_text)
            final_errs = final_divvun.get("errs", [])

        fixed_count = max(0, initial_err_count - len(final_errs))
        if fixed_count > 0:
            llm_result.setdefault("improvements", []).append(
                f"Divvun-sluttkontroll: Rettet automatisk {fixed_count} av {initial_err_count} Divvun-merknader i sluttproduktet."
            )

    final_local_tips = local_heuristic_checks(req.text if not is_sami_source else "", final_text)

    return {
        "source_text": req.text,
        "source_lang": src_lang,
        "step1_tartu_raw": tartu_raw,
        "step2_divvun_initial_errors": initial_errs,
        "step2_divvun_corrected": divvun_pre_corrected,
        "step3_final_text": final_text,
        "step3_improvements": llm_result.get("improvements", []),
        "llm_active": llm_succeeded,
        "used_model": llm_result.get("used_model"),
        "final_divvun_errors": final_divvun.get("errs", []),
        "language_tips": final_local_tips if llm_succeeded else (local_tips + [t for t in final_local_tips if t not in local_tips])
    }


@app.post("/api/translate-stream")
async def translate_pipeline_stream(req: TranslateRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Teksten er tom.")

    src_lang = req.source_lang.lower().strip() if req.source_lang else "nor"
    is_sami_source = (src_lang == "sme")

    async def event_generator():
        def send_event(obj: dict) -> str:
            return json.dumps(obj, ensure_ascii=False) + "\n"

        # Trinn 1: Klargjøring eller TartuNLP
        if is_sami_source:
            yield send_event({
                "type": "progress",
                "step": 1,
                "percent": 20,
                "title": "Trinn 1 av 4: Klargjør nordsamisk tekst",
                "detail": "Kildeteksten er på nordsamisk – hopper over maskinoversettelse..."
            })
            tartu_raw = req.text
        elif src_lang == "swe":
            yield send_event({
                "type": "progress",
                "step": 1,
                "percent": 20,
                "title": "Trinn 1 av 4: TartuNLP Svensk &rarr; Samisk",
                "detail": "Henter svensk-til-nordsamisk førsteutkast fra Universitetet i Tartu (translate.ut.ee)..."
            })
            tartu_raw = await call_tartu_mt(req.text, src="swe", tgt="sme")
            if not tartu_raw:
                tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"
        elif src_lang == "fin":
            yield send_event({
                "type": "progress",
                "step": 1,
                "percent": 20,
                "title": "Trinn 1 av 4: TartuNLP Finsk &rarr; Samisk",
                "detail": "Henter finsk-til-nordsamisk førsteutkast fra Universitetet i Tartu (translate.ut.ee)..."
            })
            tartu_raw = await call_tartu_mt(req.text, src="fin", tgt="sme")
            if not tartu_raw:
                tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"
        elif src_lang == "eng":
            yield send_event({
                "type": "progress",
                "step": 1,
                "percent": 20,
                "title": "Trinn 1 av 4: TartuNLP Engelsk &rarr; Samisk",
                "detail": "Henter engelsk-til-nordsamisk førsteutkast fra Universitetet i Tartu (translate.ut.ee)..."
            })
            tartu_raw = await call_tartu_mt(req.text, src="eng", tgt="sme")
            if not tartu_raw:
                tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"
        else:
            yield send_event({
                "type": "progress",
                "step": 1,
                "percent": 20,
                "title": "Trinn 1 av 4: TartuNLP Norsk &rarr; Samisk",
                "detail": "Henter morfologisk førsteutkast fra Universitetet i Tartu (translate.ut.ee)..."
            })
            tartu_raw = await call_tartu_mt(req.text, src="nor", tgt="sme")
            if not tartu_raw:
                tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"

        # Trinn 2: Divvun 1. runde
        yield send_event({
            "type": "progress",
            "step": 2,
            "percent": 40,
            "title": "Trinn 2 av 4: Divvun Grammatikk & Korrektur",
            "detail": "Analyserer teksten med UiT GiellaLT / Divvun API og kjører språkregelsjekker..."
        })
        divvun_initial = await call_divvun_grammar(tartu_raw) if not tartu_raw.startswith("[") else {"errs": []}
        initial_errs = divvun_initial.get("errs", [])
        divvun_pre_corrected = apply_divvun_suggestions(tartu_raw, initial_errs) if req.auto_apply_divvun and not tartu_raw.startswith("[") else tartu_raw
        local_tips = local_heuristic_checks(req.text if not is_sami_source else "", divvun_pre_corrected if not divvun_pre_corrected.startswith("[") else "")

        # Trinn 3: Gemini Språkvask
        if req.use_llm:
            chosen_model = (req.model or GEMINI_MODEL).strip() or "gemini-3.1-pro-preview"
            title_step3 = (
                f"Trinn 3 av 4: Gemini Språkvask & Korrektur ({chosen_model})"
                if is_sami_source else
                f"Trinn 3 av 4: Gemini Språkvask ({chosen_model})"
            )
            detail_step3 = (
                "Retter skrivefeil og forbedrer stilen etter Riektačállinrávvagat og Giellagiehtagirji..."
                if is_sami_source else
                "Omskriver til naturlig nordsamisk etter Riektačállinrávvagat og Giellagiehtagirji..."
            )
            yield send_event({
                "type": "progress",
                "step": 3,
                "percent": 70,
                "title": title_step3,
                "detail": detail_step3
            })
            llm_result = await call_gemini_refiner(
                req.text,
                tartu_raw,
                divvun_pre_corrected,
                initial_errs,
                local_tips,
                override_key=req.api_key,
                override_model=req.model,
                source_lang=src_lang
            )
        else:
            llm_result = {
                "final_translation": divvun_pre_corrected,
                "improvements": ["Gemini-språkvask deaktivert av bruker."],
                "llm_active": False,
                "used_model": None
            }

        gemini_text = llm_result["final_translation"]
        llm_succeeded = llm_result.get("llm_active", False)

        # Trinn 4: Sluttkontroll med Divvun
        yield send_event({
            "type": "progress",
            "step": 4,
            "percent": 88,
            "title": "Trinn 4 av 4: Divvun Sluttkontroll & Autoretting",
            "detail": "Kontrollerer det ferdige produktet med Divvun og luker ut eventuelle siste merknader..."
        })
        final_divvun = await call_divvun_grammar(gemini_text)
        final_errs = final_divvun.get("errs", [])
        final_text = gemini_text

        if req.auto_apply_divvun and final_errs:
            initial_err_count = len(final_errs)
            if llm_succeeded:
                yield send_event({
                    "type": "progress",
                    "step": 4,
                    "percent": 94,
                    "title": f"Trinn 4 av 4: Fikser {initial_err_count} Divvun-merknader i sluttproduktet...",
                    "detail": "Gemini og Divvun retter siste bøyings- og rettskrivingsmerknader..."
                })
                refined_by_divvun = await call_gemini_final_divvun_pass(
                    req.text, gemini_text, final_errs, override_key=req.api_key, override_model=req.model, source_lang=src_lang
                )
                if refined_by_divvun:
                    final_text = refined_by_divvun
                    final_divvun = await call_divvun_grammar(final_text)
                    final_errs = final_divvun.get("errs", [])

            if final_errs:
                final_text = apply_divvun_suggestions_smart(final_text, final_errs, protect_proper_nouns=True)
                final_divvun = await call_divvun_grammar(final_text)
                final_errs = final_divvun.get("errs", [])

            fixed_count = max(0, initial_err_count - len(final_errs))
            if fixed_count > 0:
                llm_result.setdefault("improvements", []).append(
                    f"Divvun-sluttkontroll: Rettet automatisk {fixed_count} av {initial_err_count} Divvun-merknader i sluttproduktet."
                )

        final_local_tips = local_heuristic_checks(req.text if not is_sami_source else "", final_text)

        result_payload = {
            "source_text": req.text,
            "source_lang": src_lang,
            "step1_tartu_raw": tartu_raw,
            "step2_divvun_initial_errors": initial_errs,
            "step2_divvun_corrected": divvun_pre_corrected,
            "step3_final_text": final_text,
            "step3_improvements": llm_result.get("improvements", []),
            "llm_active": llm_succeeded,
            "used_model": llm_result.get("used_model"),
            "final_divvun_errors": final_divvun.get("errs", []),
            "language_tips": final_local_tips if llm_succeeded else (local_tips + [t for t in final_local_tips if t not in local_tips])
        }

        yield send_event({
            "type": "result",
            "percent": 100,
            "data": result_payload
        })

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.post("/api/proofread")
async def proofread_only(req: ProofreadRequest):
    """Lar brukeren kjøre ren Divvun-korrektur + NRK-språksjekk når de redigerer den samiske teksten manuelt."""
    divvun_res = await call_divvun_grammar(req.text)
    tips = local_heuristic_checks("", req.text)
    return {
        "text": req.text,
        "errs": divvun_res.get("errs", []),
        "language_tips": tips
    }

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    return FileResponse("static/index.html")
