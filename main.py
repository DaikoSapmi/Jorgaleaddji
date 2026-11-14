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
opplært etter NRK Sámi Giellagiehtagirji og UiT Giellatekno/Oahpa-grammatikken.

Når du reviderer og oversetter teksten, MÅ du følge disse reglene:
1. FULLSTENDIGHET: Du MÅ oversette ALLE avsnitt, sitater og overskrifter i den norske kildeteksten. Ikke hopp over et eneste avsnitt!
2. VEARBAGIELLA (Verbspråk): Unngå norsk substantivsyke! Gjør tunge norske substantivuttrykk om til samiske verb og verbavledninger (-goahtit, -stit, -lit, -hit, -ut, -nit, -odit, -muvvat). Eks: "Statsforvalteren har gitt fellingstillatelse på bjørn" -> "Stáhtahálddašeaddji lea addán lobi báhčit guovžža" eller "lea suovvan báhčit guovžža".
3. AKTIIVA GIELLA (Aktivt språk): Hvis en passiv setning med -(oj)uvvot nevner hvem som utfører handlingen (subjekt/agent), MÅ setningen skrives om til aktiv. ("Ášši meannuduvvui suohkanstivrras" -> "Suohkanstivra meannudii ášši"). Passiv med -hallat brukes kun når noe er uheldig for den som rammes, med agenten i illativ ("Áhkku vuojáhalai boastabiilii").
4. SU vs. IEŽAS: Bruk refleksivt pronomen (iežan, iežat, iežas, iežame, iežade, iežaska, iežamet, iežadet, iežaset) når eieren er setningens subjekt ("Son borrá iežas njálgáid"). Bruk su/sudno/sin KUN når det viser til noen andre enn subjektet ("Son borrá su njálgáid"). Habitiv følger samme regel ("Mus lea alddán dállu", "Sudnos lea alddiska biila").
5. LOHKU + SUBSTANTIIVA: Etter tallord over 1 (2, 3... samt moadde, máŋga, galle) skal substantivet stå i ENTALL GENITIV (f.eks. "guokte olbmo", "vihtta viesu"), mens verbet står i flertall ("Guokte olbmo bohte"). Tall fra 1 til 10 skrives med bokstaver i løpende tekst. I andre kasus enn nominativ/akkusativ/genitiv: Merk at i entall lokativ og illativ står tallordet/pronomenet i genitiv mens substantivet står i lokativ/illativ ("dan guovtti mánnái", "golmma mánás").
6. -GO vs. JOS: Bruk ALDRI "jos" i indirekte spørresetninger som uttrykker usikkerhet ("Jeg vet ikke om han kommer"). Bruk partikkelen -go ("In dieđe boahtágo son odne"). "Jos" brukes kun i betingelsessetninger (jos ... de).
7. DAHJE vs. VAI: Bruk "vai" i spørresetninger ("Boađátgo ihttin vai bearjadaga?") og "dahje" i fortellende setninger.
8. EKTUI vs. HÁRRÁI/DÁFUS/ILLATIV: Unngå overbruk av "ektui" (som kun skal brukes ved ren sammenligning, f.eks. "Áhčis ektui son lea stuoris"). Bruk "hárrái", "dáfus" eller ren illativ ("Maid don dajat dien áššái?").
9. GIELLASEAGUHEAPMI & NORSK PÅVIRKNING:
   - Fjern norsk binde-s i sammensetninger (eksámenbohtosat, ikke eksamensbohtosat).
   - Bruk aldri "enngo" ved komparativ, kun "go" ("buoret go dát").
   - Fjern norske partikkeladverb som "olggos" i "gávnnahii olggos" -> "gávnnahii", eller "olggosoaidnit" -> "oaidnit".
   - Sett genitivattributt foran substantivet: "Gáivuona vuođđoskuvlla rektor", ikke "rektor Gáivuona vuođđoskuvllas".
10. REKŠUVDNAVEARBBAT: Sjekk at verbene styrer riktig kasus:
   - Illativ: liikot, luohttit, álgit, guoskat, heivet, suhttat, darvánit.
   - Lokativ: beroštit, ballat, heaitit, dolkat, váruhit, nohkkot.
   - Komitativ: humadit/háleštit, hilbošit.
11. ADJEKTIIVA ATTRIBUHTTAN & MÅL:
    - Adjektiv foran substantiv skal stå i attributtform (f.eks. "fiskes viessu", "rukses biila"). Unntak: "buorre" bøyes i kasus/tall ("buori biilla", "buori biilii"). Predikativ bøyes i tall med subjektet ("Viessu lea fiskat", "Viesut leat fiskadat").
    - Ved nøyaktige mål brukes -u-form (guhku, alu, viiddu, losu, stuoru) eller -saš ("logi mehtera alu", ikke "allat").
12. RIEKTAČÁLLIN (Rettskriving):
    - Kolon ved kasusbøyning av forkortelser og tall ("NRK:i", "2026:s").
    - Dato: Måned i genitiv + ordenstall + beaivi/beaivvi ("geassemánu 7. beaivvi 2026").
"""

class TranslateRequest(BaseModel):
    text: str
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
    async with httpx.AsyncClient(timeout=45.0) as client:
        # Prøv først hele teksten i ett kall hvis den ikke er for lang
        if len(text) < 4500:
            for src_code in [src, "nob", "no"]:
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
            for src_code in [src, "nob", "no"]:
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
    override_model: Optional[str] = None
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

    prompt = f"""Her er den nordsamiske oversettelsen du nettopp laget, sammen med merknader fra UiT Divvun grammatikk- og stavekontroll.

NORSK KILDE:
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
    """Lokal regelsjekker basert på NRK Sámi Giellagiehtagirji."""
    tips = []
    
    if re.search(r"\b(in|it|ii|ean|eahppi|eaba|eat|ehpet|eai)\s+dieđe\s+jos\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Partihkkal -go vs. konjunkšuvdna jos",
            "message": "Unngå 'jos' etter 'in dieđe' i indirekte spørsmål. Bruk spørrepartikkelen '-go' på verbet (f.eks. 'In dieđe boahtágo son odne').",
            "reference": "Giellagiehtagirji s. 18"
        })
    if re.search(r"\benngo\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Konjunkšuvdna go",
            "message": "Unngå blandingsordet 'enngo'. Bruk kun 'go' ved sammenligning (f.eks. 'buoret go dát').",
            "reference": "Giellagiehtagirji s. 19"
        })
    if "?" in sami_text and re.search(r"\bdahje\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Dahje vs. Vai",
            "message": "I spørresetninger skal man bruke 'vai' i stedet for 'dahje' (f.eks. 'Boađátgo ihttin vai bearjadaga?').",
            "reference": "Giellagiehtagirji s. 22"
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
    return tips

async def call_gemini_refiner(
    norwegian_text: str,
    tartu_draft: str,
    divvun_corrected: str,
    divvun_errs: list,
    local_tips: list,
    override_key: Optional[str] = None,
    override_model: Optional[str] = None
) -> dict:
    """Trinn 3: Foredler oversettelsen ved hjelp av Google Gemini API med responseSchema og 180s timeout for lange tekster."""
    active_key = (override_key or GEMINI_API_KEY).strip()
    requested_model = (override_model or GEMINI_MODEL).strip() or "gemini-3.1-pro-preview"

    if not active_key or active_key == "din_gemini_api_nokkel_her":
        return {
            "final_translation": divvun_corrected or tartu_draft,
            "improvements": [
                "GEMINI_API_KEY er ikke lagt inn ennå (legg den i .env eller i toppmenyen i grensesnittet). Viser TartuNLP-oversettelse korrigert av Divvun API."
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
2. Bruk TartuNLP- og Divvun-utkastet som hjelp, men skriv om der det er nødvendig for å unngå ord-for-ord-oversettelse, passiv-syke eller substantivsyke.
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

    # Trinn 1: TartuNLP råoversettelse
    tartu_raw = await call_tartu_mt(req.text)
    if not tartu_raw:
        tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"

    # Trinn 2: Divvun grammatikk- og korrekturkontroll på råoversettelsen
    divvun_initial = await call_divvun_grammar(tartu_raw) if not tartu_raw.startswith("[") else {"errs": []}
    initial_errs = divvun_initial.get("errs", [])
    divvun_pre_corrected = apply_divvun_suggestions(tartu_raw, initial_errs) if req.auto_apply_divvun and not tartu_raw.startswith("[") else tartu_raw

    # Lokale språksjekker på råutkastet
    local_tips = local_heuristic_checks(req.text, divvun_pre_corrected if not divvun_pre_corrected.startswith("[") else "")

    # Trinn 3: Språkvask med Gemini
    llm_result = await call_gemini_refiner(
        req.text,
        tartu_raw,
        divvun_pre_corrected,
        initial_errs,
        local_tips,
        override_key=req.api_key,
        override_model=req.model
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
                req.text, gemini_text, final_errs, override_key=req.api_key, override_model=req.model
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

    final_local_tips = local_heuristic_checks(req.text, final_text)

    return {
        "source_text": req.text,
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

    async def event_generator():
        def send_event(obj: dict) -> str:
            return json.dumps(obj, ensure_ascii=False) + "\n"

        # Trinn 1: TartuNLP
        yield send_event({
            "type": "progress",
            "step": 1,
            "percent": 15,
            "title": "Trinn 1 av 4: TartuNLP Råoversettelse",
            "detail": "Henter morfologisk førsteutkast fra Universitetet i Tartu (translate.ut.ee)..."
        })
        tartu_raw = await call_tartu_mt(req.text)
        if not tartu_raw:
            tartu_raw = "[TartuNLP svarte ikke – bruker Gemini og Divvun direkte]"

        # Trinn 2: Divvun 1. runde
        yield send_event({
            "type": "progress",
            "step": 2,
            "percent": 35,
            "title": "Trinn 2 av 4: Divvun Grammatikk & Korrektur (1. runde)",
            "detail": "Analyserer råutkastet med UiT GiellaLT / Divvun API og kjører lokale språksjekker..."
        })
        divvun_initial = await call_divvun_grammar(tartu_raw) if not tartu_raw.startswith("[") else {"errs": []}
        initial_errs = divvun_initial.get("errs", [])
        divvun_pre_corrected = apply_divvun_suggestions(tartu_raw, initial_errs) if req.auto_apply_divvun and not tartu_raw.startswith("[") else tartu_raw
        local_tips = local_heuristic_checks(req.text, divvun_pre_corrected if not divvun_pre_corrected.startswith("[") else "")

        # Trinn 3: Gemini Språkvask
        if req.use_llm:
            chosen_model = (req.model or GEMINI_MODEL).strip() or "gemini-3.1-pro-preview"
            yield send_event({
                "type": "progress",
                "step": 3,
                "percent": 65,
                "title": f"Trinn 3 av 4: Gemini Språkvask ({chosen_model})",
                "detail": "Omskriver til naturlig nordsamisk etter NRK Sámi Giellagiehtagirji og Oahpa-grammatikk..."
            })
            llm_result = await call_gemini_refiner(
                req.text,
                tartu_raw,
                divvun_pre_corrected,
                initial_errs,
                local_tips,
                override_key=req.api_key,
                override_model=req.model
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
            "title": "Trinn 4 av 4: Divvun Sluttkontroll & Auto-retting",
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
                    req.text, gemini_text, final_errs, override_key=req.api_key, override_model=req.model
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

        final_local_tips = local_heuristic_checks(req.text, final_text)

        result_payload = {
            "source_text": req.text,
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
