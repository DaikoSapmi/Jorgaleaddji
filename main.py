import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator, Dict, List, Literal, Optional, Tuple

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jorgaleaddji")

TARTU_API_URL = "https://api.tartunlp.ai/translation/v2"
DIVVUN_GRAMMAR_URL = "https://api-giellalt.uit.no/grammar/se"
DIVVUN_SPELLER_URL = "https://api-giellalt.uit.no/speller/se"

DEFAULT_GEMINI_MODEL = "gemini-4-hydrogen"
GEMINI_REQUEST_TIMEOUT_MS = 600_000
FAST_DIVVUN_PASS_MODEL = "gemini-4-hydrogen"
PLACEHOLDER_KEY = "din_gemini_api_nokkel_her"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL

DEPRECATED_MODEL_PREFIXES = ("gemini-2.5", "gemini-2.0", "gemini-1.5")
NON_TEXT_MODEL_KEYWORDS = (
    "tts",
    "image",
    "nano-banana",
    "omni",
    "embedding",
    "transcribe",
    "live",
    "decision",
    "imagen",
    "veo",
    "aqa",
)

DEFAULT_MODEL_CHOICES: List[Dict[str, str]] = [
    {
        "id": "gemini-4-hydrogen",
        "display_name": "Gemini 4 Hydrogen (Rask & støtter gratisnivå)",
    },
    {
        "id": "gemini-4-argon",
        "display_name": "Gemini 4 Argon (Anbefalt – presis & effektiv)",
    },
    {
        "id": "gemini-4-carbon",
        "display_name": "Gemini 4 Carbon (Maksimal resonneringsdybde)",
    },
    {
        "id": "gemini-3.5-flash-lite",
        "display_name": "Gemini 3.5 Flash-Lite (Lynrask lettvekter)",
    },
]

SOURCE_LANGUAGES: Dict[str, Dict[str, object]] = {
    "nor": {
        "label_no": "Norsk",
        "source_heading": "NORSK KILDETEKST",
        "tartu_candidates": ["nor", "nob"],
    },
    "swe": {
        "label_no": "Svensk",
        "source_heading": "SVENSK KILDETEKST",
        "tartu_candidates": ["swe", "sv"],
    },
    "fin": {
        "label_no": "Finsk",
        "source_heading": "FINSK KILDETEKST",
        "tartu_candidates": ["fin", "fi"],
    },
    "eng": {
        "label_no": "Engelsk",
        "source_heading": "ENGELSK KILDETEKST",
        "tartu_candidates": ["eng", "en"],
    },
    "sme": {
        "label_no": "Nordsamisk",
        "source_heading": "NORDSAMISK KILDETEKST",
        "tartu_candidates": [],
    },
}

LANG_ALIASES: Dict[str, str] = {
    "no": "nor",
    "nb": "nor",
    "nob": "nor",
    "nn": "nor",
    "nno": "nor",
    "nor": "nor",
    "sv": "swe",
    "swe": "swe",
    "fi": "fin",
    "fin": "fin",
    "en": "eng",
    "eng": "eng",
    "se": "sme",
    "sme": "sme",
}

VALID_IIJA_LOANWORD_SUFFIXES = (
    "logiija",
    "grafiija",
    "sofiija",
    "kratiija",
    "nomiija",
    "gogiija",
    "triija",
    "skopiija",
)

VALID_IIJA_LOANWORDS = {
    "akademiija",
    "allergiija",
    "anatomiija",
    "astronomiija",
    "autonomiija",
    "batteriija",
    "biologiija",
    "demokratiija",
    "dramaturgiija",
    "ekonomiija",
    "energiija",
    "epidemiija",
    "fantasiija",
    "filosofiija",
    "galleriija",
    "garantiija",
    "geografiija",
    "harmoniija",
    "historiija",
    "ideologiija",
    "industriija",
    "ironiija",
    "kategorija",
    "kategoriija",
    "kemiija",
    "kirurgiija",
    "koloniija",
    "liturgiija",
    "lotteriija",
    "melodiija",
    "metallurgiija",
    "metodologiija",
    "pandemiija",
    "pedagogiija",
    "poesiija",
    "politiija",
    "politologiija",
    "psykologiija",
    "sosiologiija",
    "strategiija",
    "symfoniija",
    "teknologiija",
    "teologiija",
    "teoriija",
    "terapiija",
}

GIELLAVERDDE_SKILL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".agent", "skills", "giellaverdde"
)
GIELLAVERDDE_REFS_DIR = os.path.join(GIELLAVERDDE_SKILL_DIR, "references")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "tips.json"), encoding="utf-8") as fh:
    TIP_TRANSLATIONS = json.load(fh)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "server-messages.json"), encoding="utf-8") as fh:
    SERVER_MESSAGES = json.load(fh)

UI_LANGUAGES = ("nor", "swe", "fin", "eng", "sme")


def ui_message(lang: str, key: str, **params: object) -> str:
    return SERVER_MESSAGES[key][UI_LANGUAGES.index(lang)].format(**params)


def add_local_improvement(result: dict, lang: str, key: str, *, first: bool = False, **params: object) -> None:
    variants = {language: ui_message(language, key, **params) for language in UI_LANGUAGES}
    message = variants[lang]
    improvements = result.setdefault("improvements", [])
    if first:
        improvements.insert(0, message)
    else:
        improvements.append(message)
    result.setdefault("improvement_translations", {})[message] = variants


def progress_event(lang: str, step: int, percent: int, title: str, detail: str, **params: object) -> dict:
    translations = {
        language: {
            "title": ui_message(language, title, **params),
            "detail": ui_message(language, detail, **params),
        }
        for language in UI_LANGUAGES
    }
    return {"type": "progress", "step": step, "percent": percent, **translations[lang], "translations": translations}


def _strip_yaml_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\r\n")
    return text


def list_giellaverdde_references() -> List[str]:
    if not os.path.isdir(GIELLAVERDDE_REFS_DIR):
        return []
    return sorted(
        f for f in os.listdir(GIELLAVERDDE_REFS_DIR)
        if f.endswith(".md") and os.path.isfile(os.path.join(GIELLAVERDDE_REFS_DIR, f))
    )


def read_giellaverdde_reference(filename: str, max_chars: int = 45000) -> str:
    """Leser en trygt hvitelistet referansefil fra .agent/skills/giellaverdde/references/."""
    clean_name = os.path.basename((filename or "").strip())
    available = list_giellaverdde_references()
    if clean_name not in available:
        return (
            f"Fant ikke '{filename}'. Tilgjengelige referansefiler: "
            + ", ".join(available)
        )
    path = os.path.join(GIELLAVERDDE_REFS_DIR, clean_name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[... avkortet etter maks lengde ...]"
        return content
    except Exception as exc:
        logger.warning("Kunne ikke lese giellaverdde-referanse %s: %s", clean_name, exc)
        return f"Feil ved lesing av {clean_name}: {exc}"


def load_giellaverdde_skill_core() -> str:
    """Laster SKILL.md + 01-nrk-standarda.md fra ./.agent/skills/giellaverdde som systeminstruks."""
    skill_path = os.path.join(GIELLAVERDDE_SKILL_DIR, "SKILL.md")
    if not os.path.isfile(skill_path):
        logger.warning("Fant ikke giellaverdde SKILL.md på %s; bruker minimal reserveinstruks.", skill_path)
        return (
            "Du er Giellaverdde, en ekspert på nordsamisk rettskriving og NRKs språkstandard. "
            "Sørg for korrekt nordsamisk syntaks, aktivt verbspråk, riktig kasusstyring og tegnsetting."
        )

    with open(skill_path, "r", encoding="utf-8") as fh:
        skill_text = _strip_yaml_frontmatter(fh.read()).strip()

    nrk_std_path = os.path.join(GIELLAVERDDE_REFS_DIR, "01-nrk-standarda.md")
    nrk_std_text = ""
    if os.path.isfile(nrk_std_path):
        with open(nrk_std_path, "r", encoding="utf-8") as fh:
            nrk_std_text = fh.read().strip()

    available_refs = ", ".join(list_giellaverdde_references())
    adapter_note = f"""
# TILPASNING TIL PIPELINE-FORMAT (VIKTIG)
1. Du kjører som en integrert del av oversettelses- og korrekturpipelinen **etter første Divvun-sjekk**.
2. I stedet for å bare skrive en separat rapport i Markdown-formatet over, skal du **direkte anvende** alle relevante regler fra `giellaverdde`-skillen og `references/`-filene for å produsere den ferdige, korrigerte og språkvaskede nordsamiske teksten i JSON-feltet `"final_translation"`.
3. Ta med ALLE avsnitt, overskrifter, sitater, tall og fakta fra kildeteksten med nøyaktig samme avsnittsinndeling. Sitater beskyttes mot omskriving (bortsett fra rene stavefeil).
4. **Progressive Disclosure via verktøy:** Når du har tilgang til verktøyet `read_giellaverdde_reference`, slå opp de relevante filene i `references/` (tilgjengelige: {available_refs}) før du leverer det endelige svaret – spesielt ved spørsmål om tegnsetting/tall/forkortelser (`02-riektacallinravvagat.md`), syntaks/`su` vs. `iežas`/tallord (`03-syntaksa-ja-kongrueansa.md`), verb/kasus (`06-vearbbat.md`) eller avledning (`09-suorggideapmi.md`).
5. I JSON-feltet `"improvements"` skal du gi korte, konkrete punkter på **norsk** som gjengir hvilke råd, rettskrivingsregler og `references/`-filer fra `giellaverdde` du fulgte og rettet etter.
""".strip()

    parts = [skill_text]
    if nrk_std_text:
        parts.append("# LASTET REFERANSE (BAJIMUS VÁLDI): 01-nrk-standarda.md\n\n" + nrk_std_text)
    parts.append(adapter_note)
    return "\n\n---\n\n".join(parts)


READ_GIELLAVERDDE_TOOL = {
    "type": "function",
    "name": "read_giellaverdde_reference",
    "description": (
        "Leser en faglig oppslagsfil fra giellaverdde/references/ (for eksempel '02-riektacallinravvagat.md', "
        "'03-syntaksa-ja-kongrueansa.md', '04-substantiivvat.md', '05-adjektiivvat.md', '06-vearbbat.md', "
        "'07-dassemolsasupmi.md', '08-oamastangehcosat.md', '09-suorggideapmi.md', '10-essiiva.md') "
        "for å sjekke eksakte nordsamiske normer før retting."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Eksakt filnavn i references/, f.eks. '03-syntaksa-ja-kongrueansa.md'.",
            }
        },
        "required": ["filename"],
    },
}

SOURCE_SPECIFIC_GUIDANCE: Dict[str, str] = {
    "nor": (
        "Du er en ekspertoversetter og språkvasker fra norsk (bokmål/nynorsk) til nordsamisk (davvisámegiella). "
        "Vær spesielt oppmerksom på å løse opp norsk substantivsyke, preposisjonsuttrykk ('i forhold til', 'i forbindelse med'), "
        "norske passivsetninger med 'av', binde-s i sammensetninger og 'om' i indirekte spørsmål."
    ),
    "swe": (
        "Du er en ekspertoversetter og språkvasker fra svensk til nordsamisk (davvisámegiella). "
        "Vær spesielt oppmerksom på å løse opp svensk substantivsyke, s-passiv ('behandlades av') der agens er kjent, "
        "svenske sammensetningsfoger og indirekte spørsmål med 'om'."
    ),
    "fin": (
        "Du er en ekspertoversetter og språkvasker fra finsk til nordsamisk (davvisámegiella). "
        "Selv om finsk og samisk er beslektede språk, må du unngå mekaniske finske partisippkalker, feil kasusstyring (finsk elativ/inessiv/partitiv vs. samisk lokativ/illativ/akkusativ) "
        "og falske venner (f.eks. 'hallitus' = 'ráđđehus' for regjering vs. 'stivra' for styre; 'toimittaa' etter kontekst). Skriv naturlig, idiomatisk nordsamisk."
    ),
    "eng": (
        "Du er en ekspertoversetter og språkvasker fra engelsk til nordsamisk (davvisámegiella). "
        "Unngå kalkering av engelske '-ing'-konstruksjoner og passiv med 'by'. Konverter desimalpunktum til samisk/nordisk desimalkomma (f.eks. '3.5%' → '3,5 %'), "
        "bruk liten forbokstav på titler, ukedager, måneder og nasjonaliteter, og bytt engelske anførselstegn “...” til samiske ”...”."
    ),
    "sme": (
        "Du er en ekspertspråkvasker og korrekturleser i nordsamisk (davvisámegiella). "
        "Kildeteksten er allerede skrevet på nordsamisk. Bevar skribentens egen stemme, stil og ordvalg der samisken allerede er god, "
        "men rett alle skrive-, bøyings-, stadievekslings-, rekšuvdna- og tegnsettingsfeil, og løs opp tydelige skandinaviske/finske kalker skånsomt."
    ),
}


def parse_glossary(raw_glossary: Optional[str]) -> List[Tuple[str, str]]:
    """Tolker brukerens ordliste ('kilde = samisk', 'kilde -> samisk' eller 'kilde : samisk')."""
    if not raw_glossary or not raw_glossary.strip():
        return []
    entries: List[Tuple[str, str]] = []
    for line in raw_glossary.splitlines()[:100]:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        for sep in ("->", "→", "=", ":"):
            if sep in cleaned:
                left, right = cleaned.split(sep, 1)
                src_term, tgt_term = left.strip(), right.strip()
                if src_term and tgt_term:
                    entries.append((src_term, tgt_term))
                break
    return entries


def build_system_instruction(
    source_lang: str = "nor",
    glossary: Optional[str] = None,
) -> str:
    role_intro = SOURCE_SPECIFIC_GUIDANCE.get(source_lang, SOURCE_SPECIFIC_GUIDANCE["nor"])
    skill_core = load_giellaverdde_skill_core()
    parts = [role_intro, "", skill_core]
    glossary_entries = parse_glossary(glossary)
    if glossary_entries:
        formatted_terms = "\n".join(f"- {src} → {tgt}" for src, tgt in glossary_entries)
        parts.extend([
            "",
            "# OBLIGATORISK TERMINOLOGI / ORDLISTE",
            "Bruk konsekvent følgende normerte samiske termer (bøyd i riktig kasus etter setningen) når disse begrepene forekommer:",
            formatted_terms,
        ])
    return "\n".join(parts)


class RefinementSchema(BaseModel):
    final_translation: str = Field(
        description="Den fullstendige, ferdige nordsamiske teksten med alle avsnitt bevart."
    )
    improvements: List[str] = Field(
        description="Liste med korte punkter på norsk som forklarer de viktigste språklige forbedringene."
    )


class DivvunFixSchema(BaseModel):
    corrected_text: str = Field(
        description="Den korrigerte nordsamiske teksten der reelle Divvun-merknader er rettet."
    )


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000)
    source_lang: str = Field(default="nor")
    use_llm: bool = True
    auto_apply_divvun: bool = True
    api_key: Optional[str] = Field(default=None, max_length=256)
    model: Optional[str] = Field(default=None, max_length=128)
    thinking_level: Literal["low", "medium", "high"] = "medium"
    glossary: Optional[str] = Field(default=None, max_length=10_000)

    @field_validator("source_lang")
    @classmethod
    def validate_source_lang(cls, v: str) -> str:
        norm = (v or "nor").strip().lower()
        if norm not in LANG_ALIASES:
            raise ValueError(f"Ugyldig kildespråk '{v}'. Støttede språk: nor, swe, fin, eng, sme.")
        return LANG_ALIASES[norm]


class ProofreadRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000)
    source_lang: str = Field(default="nor")

    @field_validator("source_lang")
    @classmethod
    def validate_source_lang(cls, v: str) -> str:
        return TranslateRequest.validate_source_lang(v)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    timeout = httpx.Timeout(45.0, connect=10.0)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as http_client:
        app_instance.state.http_client = http_client
        yield


app = FastAPI(
    title="Jorgaleaddji & Divvun Studio (Gemini 4 Edition)",
    lifespan=lifespan,
)


def sanitize_error_message(raw_msg: str, secret_key: str = "") -> str:
    """Fjerner eventuelle API-nøkler og URL-hemmeligheter fra feilmeldinger før visning/logging."""
    if not raw_msg:
        return "Ukjent feil"
    cleaned = str(raw_msg)
    if secret_key and len(secret_key) >= 6:
        cleaned = cleaned.replace(secret_key, "[SKJULT_NØKKEL]")
    cleaned = re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "[SKJULT_NØKKEL]", cleaned)
    cleaned = re.sub(r"([?&](?:api_)?key=)[^&\s'\"]+", r"\1[SKJULT]", cleaned, flags=re.IGNORECASE)
    return cleaned[:280]


def normalize_gemini_model(model: Optional[str], source_lang: str = "nor") -> Tuple[str, Optional[str]]:
    """Erstatter avviklede Gemini 1.5/2.0/2.5-modeller med gemini-4-hydrogen."""
    candidate = (model or GEMINI_MODEL or DEFAULT_GEMINI_MODEL).strip()
    if not candidate:
        candidate = DEFAULT_GEMINI_MODEL
    lower = candidate.lower()
    if any(lower.startswith(prefix) for prefix in DEPRECATED_MODEL_PREFIXES):
        note = ui_message(source_lang, "deprecated", model=candidate)
        return "gemini-4-hydrogen", note
    return candidate, None


def extract_gemini_json(raw_text: str) -> dict:
    """Robust JSON-utpakker som ekstra sikring dersom et svar inneholder kodeblokker eller småfeil."""
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx : end_idx + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    ft_match = re.search(
        r'"final_translation"\s*:\s*"((?:[^"\\]|\\.)*)"',
        cleaned,
        flags=re.DOTALL,
    )
    if ft_match:
        raw_ft = ft_match.group(1)
        try:
            ft_val = json.loads(f'"{raw_ft}"')
        except Exception:
            ft_val = raw_ft.replace("\\n", "\n").replace('\\"', '"')

        imps: List[str] = []
        imp_block = re.search(r'"improvements"\s*:\s*\[(.*?)\]', cleaned, flags=re.DOTALL)
        if imp_block:
            for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', imp_block.group(1), flags=re.DOTALL):
                try:
                    imps.append(json.loads(f'"{m.group(1)}"'))
                except Exception:
                    imps.append(m.group(1).replace('\\"', '"'))
        return {"final_translation": ft_val, "improvements": imps}

    return {}


def extract_interaction_text(interaction: object) -> str:
    """Henter tekstsvar fra et Interactions API-objekt (via output_text eller model_output-steps)."""
    out_text = getattr(interaction, "output_text", None)
    if isinstance(out_text, str) and out_text.strip():
        return out_text

    steps = getattr(interaction, "steps", None) or []
    collected: List[str] = []
    for step in steps:
        if getattr(step, "type", None) == "model_output":
            for block in getattr(step, "content", None) or []:
                txt = getattr(block, "text", None)
                if isinstance(txt, str) and txt:
                    collected.append(txt)
    return "".join(collected)


def is_supported_text_model(model_id: str) -> bool:
    lower = model_id.lower()
    if not (lower.startswith("gemini-") or lower.startswith("gemma-4-")):
        return False
    if any(lower.startswith(prefix) for prefix in DEPRECATED_MODEL_PREFIXES):
        return False
    if any(kw in lower for kw in NON_TEXT_MODEL_KEYWORDS):
        return False
    return True


async def fetch_available_gemini_models(api_key: str) -> List[Dict[str, str]]:
    active_key = (api_key or "").strip()
    if not active_key or active_key == PLACEHOLDER_KEY:
        return []

    try:
        client = genai.Client(
            api_key=active_key,
            http_options={"timeout": GEMINI_REQUEST_TIMEOUT_MS},
        )
        discovered: Dict[str, str] = {}
        pager = await client.aio.models.list()
        async for m in pager:
            raw_name = getattr(m, "name", "") or ""
            model_id = raw_name.replace("models/", "").strip()
            if not model_id or not is_supported_text_model(model_id):
                continue
            display_name = getattr(m, "display_name", None) or model_id
            discovered[model_id] = display_name

        if not discovered:
            return list(DEFAULT_MODEL_CHOICES)

        priority_order = [c["id"] for c in DEFAULT_MODEL_CHOICES]
        default_labels = {c["id"]: c["display_name"] for c in DEFAULT_MODEL_CHOICES}
        ordered: List[Dict[str, str]] = []

        for pid in priority_order:
            if pid in discovered:
                ordered.append({"id": pid, "display_name": default_labels[pid]})
                discovered.pop(pid, None)

        for mid in sorted(discovered.keys(), reverse=True):
            ordered.append({"id": mid, "display_name": discovered[mid]})

        return ordered
    except Exception as exc:
        logger.warning("Kunne ikke hente modelliste fra Gemini API: %s", sanitize_error_message(str(exc), active_key))
        return list(DEFAULT_MODEL_CHOICES)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config(
    x_gemini_api_key: Optional[str] = Header(default=None, alias="X-Gemini-Api-Key"),
):
    active_key = (x_gemini_api_key or GEMINI_API_KEY).strip()
    has_key = bool(active_key and active_key != PLACEHOLDER_KEY)
    normalized_env_model, _ = normalize_gemini_model(GEMINI_MODEL)
    available_models = await fetch_available_gemini_models(active_key) if has_key else []
    return {
        "env_model": normalized_env_model,
        "has_env_key": bool(GEMINI_API_KEY and GEMINI_API_KEY != PLACEHOLDER_KEY),
        "available_models": available_models,
        "default_models": DEFAULT_MODEL_CHOICES,
    }


@asynccontextmanager
async def borrow_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    shared: Optional[httpx.AsyncClient] = getattr(app.state, "http_client", None)
    if shared is not None and not shared.is_closed:
        yield shared
    else:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as temp_client:
            yield temp_client


async def _tartu_translate_chunk(
    client: httpx.AsyncClient,
    chunk: str,
    src_candidates: List[str],
    tgt: str,
) -> Tuple[Optional[str], bool]:
    """Returnerer (oversatt_tekst_eller_None, språkpar_avvist_permanent)."""
    saw_bad_pair = False
    for src_code in src_candidates:
        try:
            resp = await client.post(
                TARTU_API_URL,
                json={"text": chunk, "src": src_code, "tgt": tgt},
                timeout=45.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result")
                if isinstance(result, str) and result.strip():
                    return result, False
            elif resp.status_code in (400, 404, 422):
                saw_bad_pair = True
        except Exception as exc:
            logger.warning("TartuNLP feil for src=%s: %s", src_code, exc)
            continue
    return None, saw_bad_pair


async def call_tartu_mt(text: str, src: str = "nor", tgt: str = "sme") -> Optional[str]:
    """
    Trinn 1: Kaller TartuNLP (translate.ut.ee).
    Returnerer None dersom TartuNLP ikke støtter språkparet eller ikke svarer,
    slik at uoversatt kildetekst ALDRI sendes videre til samisk stavekontroll.
    """
    lang_cfg = SOURCE_LANGUAGES.get(src, SOURCE_LANGUAGES["nor"])
    src_candidates = list(lang_cfg.get("tartu_candidates") or ["nor", "nob"])
    if not src_candidates or not text.strip():
        return None

    async with borrow_http_client() as client:
        if len(text) < 4000:
            whole_res, rejected = await _tartu_translate_chunk(client, text, src_candidates, tgt)
            if whole_res is not None:
                return whole_res
            if rejected:
                logger.info("TartuNLP støtter ikke språkparet %s -> %s; hopper til Gemini.", src, tgt)
                return None

        paragraphs = text.split("\n")
        non_empty_indices = [i for i, p in enumerate(paragraphs) if p.strip()]
        if not non_empty_indices:
            return None

        # Test første avsnitt først for å unngå N unødvendige kall hvis tjenesten/språkparet er nede
        first_idx = non_empty_indices[0]
        first_res, first_rejected = await _tartu_translate_chunk(
            client, paragraphs[first_idx], src_candidates, tgt
        )
        if first_res is None and (first_rejected or len(non_empty_indices) == 1):
            return None

        semaphore = asyncio.Semaphore(4)
        results_by_index: Dict[int, Optional[str]] = {first_idx: first_res}

        async def translate_idx(idx: int) -> None:
            async with semaphore:
                res, _ = await _tartu_translate_chunk(client, paragraphs[idx], src_candidates, tgt)
                results_by_index[idx] = res

        if len(non_empty_indices) > 1:
            await asyncio.gather(*(translate_idx(i) for i in non_empty_indices[1:]))

        succeeded = sum(1 for v in results_by_index.values() if v is not None)
        if succeeded == 0:
            return None

        assembled: List[str] = []
        for idx, orig_p in enumerate(paragraphs):
            if not orig_p.strip():
                assembled.append("")
            elif results_by_index.get(idx) is not None:
                assembled.append(results_by_index[idx] or "")
            else:
                # Hvis et enkeltavsnitt feilet i en ellers vellykket lang tekst, behold kilden tydelig merket for Gemini
                assembled.append(orig_p)
        return "\n".join(assembled)


async def call_divvun_grammar(text: str) -> dict:
    """Trinn 2 / 4: Kaller Divvun GiellaLT API for nordsamisk grammatikk- og stavekontroll."""
    if not text or not text.strip():
        return {"text": text, "errs": []}
    async with borrow_http_client() as client:
        try:
            resp = await client.post(
                DIVVUN_GRAMMAR_URL,
                json={"text": text},
                headers={"Content-Type": "application/json"},
                timeout=35.0,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Divvun API svarte med HTTP %s", resp.status_code)
        except Exception as exc:
            logger.warning("Divvun API nettverksfeil: %s", exc)
            return {"text": text, "errs": [], "api_error": str(exc)}
    return {"text": text, "errs": []}


def localize_speller_errors(errors: List[dict], lang: str) -> None:
    for error in errors:
        translations = {
            language: {
                "title": ui_message(language, "speller_title"),
                "description": ui_message(language, "speller_description"),
            }
            for language in UI_LANGUAGES
        }
        error.update(translations[lang])
        error["translations"] = translations


async def call_divvun_speller(text: str) -> List[dict]:
    """Kaller Divvun GiellaLT Speller API (/speller/se) for siste ord-for-ord rettskrivingstest."""
    if not text or not text.strip():
        return []
    async with borrow_http_client() as client:
        try:
            resp = await client.post(
                DIVVUN_SPELLER_URL,
                json={"text": text},
                headers={"Content-Type": "application/json"},
                timeout=25.0,
            )
            if resp.status_code != 200:
                logger.warning("Divvun Speller API svarte med HTTP %s", resp.status_code)
                return []
            data = resp.json()
        except Exception as exc:
            logger.warning("Divvun Speller API nettverksfeil: %s", exc)
            return []

    results = data.get("results") or []
    speller_errs: List[dict] = []
    cursor = 0
    for item in results:
        if not isinstance(item, dict):
            continue
        word = item.get("word") or ""
        if not word:
            continue
        idx = text.find(word, cursor)
        if idx == -1:
            idx = text.find(word)
        if idx != -1:
            cursor = idx + len(word)
        if item.get("is_correct", True) or idx == -1:
            continue
        raw_suggs = item.get("suggestions") or []
        suggestions = [
            s["value"]
            for s in raw_suggs
            if isinstance(s, dict) and s.get("value")
        ][:6]
        speller_errs.append(
            {
                "error_text": word,
                "start_index": idx,
                "end_index": idx + len(word),
                "error_code": "speller",
                "title": "Čállinmeattáhus (Divvun Speller)",
                "description": "Sátni ii gávdno divvun-sátnerájus.",
                "suggestions": suggestions,
                "source": "speller",
            }
        )
    return speller_errs


def merge_divvun_errors(grammar_errs: List[dict], speller_errs: List[dict]) -> List[dict]:
    """Slår sammen grammatikkfeil og stavefeil fra /speller/se uten overlappende duplikater."""
    merged: List[dict] = []
    for err in grammar_errs or []:
        if not isinstance(err, dict):
            continue
        entry = dict(err)
        entry.setdefault("source", "grammar")
        merged.append(entry)

    for sp_err in speller_errs or []:
        sp_start = sp_err.get("start_index")
        sp_end = sp_err.get("end_index")
        if not isinstance(sp_start, int) or not isinstance(sp_end, int):
            continue
        overlaps = False
        for existing in merged:
            ex_start = existing.get("start_index")
            ex_end = existing.get("end_index")
            if isinstance(ex_start, int) and isinstance(ex_end, int):
                if sp_start < ex_end and sp_end > ex_start:
                    # Slå sammen eventuelle ekstra forslag fra speller inn i eksisterende merknad
                    existing_suggs = list(existing.get("suggestions") or [])
                    for s in sp_err.get("suggestions") or []:
                        if s not in existing_suggs:
                            existing_suggs.append(s)
                    existing["suggestions"] = existing_suggs[:6]
                    overlaps = True
                    break
        if not overlaps:
            merged.append(sp_err)

    merged.sort(key=lambda e: e.get("start_index", 0))
    return merged


def _extract_capitalized_source_stems(source_text: str) -> set:
    if not source_text:
        return set()
    tokens = re.findall(r"\b[A-ZÁČĐŊŠŦŽÆØÅÄÖ][\w\-]{1,}\b", source_text)
    return set(tokens)


def _matches_source_proper_noun(word: str, source_cap_words: set) -> bool:
    if not source_cap_words or not word:
        return False
    if word in source_cap_words:
        return True
    # Sjekk også samiske kasusendelser lagt på utenlandske egennavn (f.eks. Warth -> Wartha / Warthii / Warthas)
    for cap in source_cap_words:
        if len(cap) >= 3 and word.startswith(cap) and len(word) - len(cap) <= 4:
            return True
    return False


def _is_sentence_initial(text: str, start: int) -> bool:
    """Sjekker om posisjon `start` er starten på en ny setning (hopper over mellomrom og åpningsanførselstegn)."""
    if start <= 0:
        return True
    prefix = text[:start].rstrip(" \t\r”\"“«»'‘’‚([—–-")
    if not prefix:
        return True
    return prefix[-1] in ".!?\n:"


def apply_divvun_suggestions(
    text: str,
    errs: list,
    protect_proper_nouns: bool = True,
    source_text: str = "",
) -> str:
    """
    Bruker Divvuns beste forslag bakfra uten å ødelegge:
    - overlappende feilintervaller,
    - egennavn midt i en setning, eller
    - egennavn fra kildeteksten (selv først i en setning),
    samtidig som reelle skrivefeil i starten av nye setninger blir rettet.
    """
    if not text or not errs:
        return text

    source_cap_words = _extract_capitalized_source_stems(source_text) if protect_proper_nouns else set()

    valid_errs = [
        e
        for e in errs
        if isinstance(e.get("start_index"), int)
        and isinstance(e.get("end_index"), int)
        and e.get("suggestions")
    ]
    sorted_errs = sorted(
        valid_errs,
        key=lambda x: (x["start_index"], x["end_index"]),
        reverse=True,
    )

    corrected = text
    min_touched_start = len(text) + 1

    for err in sorted_errs:
        suggestions = err.get("suggestions") or []
        start = err["start_index"]
        end = err["end_index"]
        err_word = err.get("error_text") or ""
        err_code = err.get("error_code") or ""

        if not suggestions or start < 0 or end > len(text) or start >= end:
            continue
        # Hopp over overlappende intervaller slik at vi aldri klipper i allerede endret tekst
        if end > min_touched_start:
            continue

        actual_slice = text[start:end]
        if err_word and actual_slice != err_word:
            continue

        if protect_proper_nouns and err_code == "typo" and actual_slice[:1].isupper():
            sentence_start = _is_sentence_initial(text, start)
            in_source_names = _matches_source_proper_noun(actual_slice, source_cap_words)
            if (not sentence_start) or in_source_names:
                continue

        corrected = corrected[:start] + suggestions[0] + corrected[end:]
        min_touched_start = start

    return corrected


# Bakoverkompatibelt alias
apply_divvun_suggestions_smart = apply_divvun_suggestions


def _is_valid_iija_loanword(word: str) -> bool:
    # Fjern evt. vanlige kasussuffikser hvis regex traff grunnformen
    low = word.lower()
    if low in VALID_IIJA_LOANWORDS:
        return True
    return any(low.endswith(sfx) for sfx in VALID_IIJA_LOANWORD_SUFFIXES)


def local_heuristic_checks(source_text: str, sami_text: str, source_lang: str = "nor") -> List[dict]:
    """Lokal regelsjekker basert på Riektačállinrávvagat (2019), NRK Sámi Giellagiehtagirji og kilde-samsvar."""
    if not sami_text or not sami_text.strip():
        return []

    tips: List[dict] = []

    if re.search(r"\b(in|it|ii|ean|eahppi|eaba|eat|ehpet|eai)\s+dieđe\s+jos\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Partihkkal -go vs. konjunkšuvdna jos",
            "message": "Unngå 'jos' etter 'in dieđe' i indirekte spørsmål. Bruk spørrepartikkelen '-go' på verbet (f.eks. 'In dieđe boahtágo son odne').",
            "reference": "Giellagiehtagirji s. 18 / Riektačállinrávvagat s. 70",
        })

    if re.search(r"\benngo\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Konjunkšuvdna go",
            "message": "Unngå blandingsordet 'enngo'. Bruk kun 'go' ved sammenligning (f.eks. 'buoret go dát').",
            "reference": "Giellagiehtagirji s. 19 / Riektačállinrávvagat s. 70",
        })

    # Sjekk 'dahje' kun inne i faktiske spørresetninger (som slutter med '?')
    sentences = re.split(r"(?<=[.!?])\s+|\n+", sami_text)
    if any(s.rstrip(" ”\"')").endswith("?") and re.search(r"\bdahje\b", s, re.IGNORECASE) for s in sentences):
        tips.append({
            "rule": "Dahje vs. Vai",
            "message": "I spørresetninger skal man bruke 'vai' i stedet for 'dahje' (f.eks. 'Boađátgo ihttin vai bearjadaga?').",
            "reference": "Giellagiehtagirji s. 22 / Riektačállinrávvagat s. 32",
        })

    if re.search(r"\bektui\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Ektui vs. hárrái / dáfus / illativ",
            "message": "Sjekk om 'ektui' brukes til reell sammenligning. Ofte passer 'hárrái', 'dáfus' eller ren illativ bedre.",
            "reference": "Giellagiehtagirji s. 22",
        })

    if re.search(r"\b(gávnnahii|gávnnahit|gávnnahan)\s+olggos\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Norsk påvirkning (olggos)",
            "message": "På samisk sier man bare 'gávnnahii' (fant ut), uten 'olggos'.",
            "reference": "Giellagiehtagirji s. 9",
        })

    if re.search(r"\bolggosoaidnit\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Norsk påvirkning (olggosoaidnit)",
            "message": "Unngå 'olggosoaidnit' (se ut). Bruk bare 'oaidnit' ('Makkár dat lea oaidnit?').",
            "reference": "Giellagiehtagirji s. 9 & 16",
        })

    if re.search(r"\w+(juvvon|juvvui|juvvo|juvvojit)\b", sami_text, re.IGNORECASE):
        tips.append({
            "rule": "Aktiiva giella (Passiv → Aktiv)",
            "message": "Teksten inneholder et passivt verb på -(oj)uvvot. Sjekk om den som utfører handlingen er nevnt – i så fall bør setningen snus til aktiv.",
            "reference": "Giellagiehtagirji s. 15 / Ordavledning s. 2",
        })

    if re.search(
        r"\b(dieđus|dattet|iešguhte|okta|veahá|veaháš|makkár|mihkke|movt|goit|almmat)\s+ge\b",
        sami_text,
        re.IGNORECASE,
    ):
        tips.append({
            "rule": "Laktapartihkkalat (sammenskriving)",
            "message": "Faste partikkelord skal skrives i ett ord: 'dieđusge', 'dattetge', 'iešguhtege', 'oktage', 'veaháge', 'mihkkege', 'goitge', 'almmatge'.",
            "reference": "Riektačállinrávvagat s. 71",
        })

    if re.search(r"\b\d+(?:[.,]\d+)?%", sami_text):
        tips.append({
            "rule": "Proseantamearka (gaska)",
            "message": "Det skal være mellomrom mellom tallet og prosenttegnet (f.eks. '25 %', ikke '25%').",
            "reference": "Riektačállinrávvagat s. 41",
        })

    if re.search(r"-(mearri|mearre)\b", sami_text, re.IGNORECASE) and "%-" in sami_text:
        tips.append({
            "rule": "Proseantamearri vs. %-mearri",
            "message": "Skriv 'proseantamearri' med bokstaver, ikke '%-mearri'.",
            "reference": "Riektačállinrávvagat s. 41",
        })

    iija_candidates = re.findall(r"\b[A-ZÁČĐŊŠŦŽ][a-záčđŋšŧž]+iija\b", sami_text)
    invalid_iija = [w for w in iija_candidates if not _is_valid_iija_loanword(w)]
    if invalid_iija:
        examples = ", ".join(dict.fromkeys(invalid_iija))
        tips.append({
            "rule": "Báikenamat eai noga -iija",
            "message": f"Stedsnavn ender aldri på '-iija' på samisk (fant: {examples}). Skriv f.eks. 'Tansania', 'Italia', 'Spania'.",
            "reference": "Riektačállinrávvagat s. 43",
            "params": {"examples": examples},
        })

    # Varsle KUN ved engelske åpningsanførselstegn “ (U+201C), tyske „ (U+201E) eller norske vinkeltegn «» – ALDRI ved gyldig samisk ” (U+201D)!
    if re.search(r"[“„«»]", sami_text):
        tips.append({
            "rule": "Aisttonmearkkat (Sitattegn)",
            "message": "På nordsamisk brukes typografiske sitattegn ”...” (U+201D før og etter sitatet), ikke engelske “...” eller norske «...».",
            "reference": "Riektačállinrávvagat s. 24",
        })

    # Kilde-samsvar: avsnitt og årstall
    if source_text and source_text.strip():
        src_paras = [p.strip() for p in source_text.splitlines() if p.strip()]
        tgt_paras = [p.strip() for p in sami_text.splitlines() if p.strip()]
        if len(src_paras) >= 2 and len(tgt_paras) < len(src_paras):
            tips.append({
                "rule": "Avsnittsstruktur (Fullstendighet)",
                "message": f"Kildeteksten har {len(src_paras)} avsnitt, mens den samiske teksten har {len(tgt_paras)} avsnitt. Kontroller at ingen avsnitt er utelatt eller slått sammen.",
                "reference": "Kvalitetskontroll",
                "params": {"source_count": len(src_paras), "target_count": len(tgt_paras)},
            })

        src_years = set(re.findall(r"\b(?:1[89]\d{2}|20\d{2})\b", source_text))
        missing_years = sorted(y for y in src_years if y not in sami_text)
        if missing_years:
            tips.append({
                "rule": "Årstall fra kildeteksten",
                "message": f"Årstall i kildeteksten som ikke ble funnet som sifre i målteksten: {', '.join(missing_years)}.",
                "reference": "Kvalitetskontroll",
                "params": {"years": ", ".join(missing_years)},
            })

    for tip in tips:
        original_rule = tip["rule"]
        variants = {"nor": {key: tip[key] for key in ("rule", "message", "reference")}}
        for lang in UI_LANGUAGES[1:]:
            title, message = TIP_TRANSLATIONS[original_rule][lang]
            reference = tip["reference"]
            if reference == "Kvalitetskontroll":
                reference = {
                    "swe": "Kvalitetskontroll",
                    "fin": "Laadunvalvonta",
                    "eng": "Quality control",
                    "sme": "Kvalitehtadárkkisteapmi",
                }[lang]
            else:
                if lang == "eng":
                    reference = reference.replace("s. ", "p. ")
                reference = reference.replace(
                    "Ordavledning",
                    {"swe": "Ordavledning", "fin": "Sananjohtaminen", "eng": "Word derivation", "sme": "Sátnesuorggideapmi"}[lang],
                )
            variants[lang] = {
                "rule": title,
                "message": message.format(**tip.get("params", {})),
                "reference": reference,
            }
        tip.update(variants[source_lang])
        tip["translations"] = variants
        tip.pop("params", None)
    return tips


def _classify_gemini_exception(exc: Exception) -> Tuple[Optional[int], bool]:
    """Returnerer (status_code_hvis_kjent, bør_prøve_neste_modell)."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int):
        if code in (403, 404, 429, 503):
            return code, True
        if code in (400, 401):
            return code, False
    msg = str(exc)
    for sc in (400, 401, 403, 404, 429, 503):
        if f" {sc} " in msg or f"({sc})" in msg or msg.startswith(str(sc)):
            return sc, sc in (403, 404, 429, 503)
    return None, False


async def call_gemini_final_divvun_pass(
    source_text: str,
    gemini_draft: str,
    divvun_errs: list,
    override_key: Optional[str] = None,
    override_model: Optional[str] = None,
    source_lang: str = "nor",
    glossary: Optional[str] = None,
) -> Optional[str]:
    """Trinn 4: Lar en rask Gemini 4-modell rette konkrete Divvun-merknader intelligent uten å ødelegge syntaks eller egennavn."""
    active_key = (override_key or GEMINI_API_KEY).strip()
    if not active_key or active_key == PLACEHOLDER_KEY or not divvun_errs:
        return None

    compact_errs = [
        {
            "error_text": e.get("error_text"),
            "title": e.get("title"),
            "description": e.get("description"),
            "suggestions": (e.get("suggestions") or [])[:5],
        }
        for e in divvun_errs[:35]
    ]

    lang_cfg = SOURCE_LANGUAGES.get(source_lang, SOURCE_LANGUAGES["nor"])
    source_heading = str(lang_cfg["source_heading"])

    prompt = f"""Her er den nordsamiske teksten du bearbeider, sammen med merknader fra UiT Divvun grammatikk- og stavekontroll.

{source_heading}:
{source_text}

DIN NORDSAMISKE TEKST:
{gemini_draft}

MERKNADER FRA DIVVUN SOM SKAL VURDERES OG FIKSES:
{json.dumps(compact_errs, ensure_ascii=False)}

Oppgave:
Rett opp alle reelle stave-, bøyings-, stadievekslings-, kasus- og tegnsettingsfeil som Divvun har påpekt, uten å ødelegge personnavn, fagtermer eller den gode samiske setningsoppbyggingen og avsnittsstrukturen.
Returner svaret som JSON med nøkkelen "corrected_text"."""

    normalized_override, _ = normalize_gemini_model(override_model)
    candidates = list(
        dict.fromkeys([FAST_DIVVUN_PASS_MODEL, normalized_override, "gemini-3.5-flash-lite"])
    )
    system_instruction = build_system_instruction(source_lang=source_lang, glossary=glossary)

    try:
        client = genai.Client(
            api_key=active_key,
            http_options={"timeout": GEMINI_REQUEST_TIMEOUT_MS},
        )
        for cand in candidates:
            try:
                interaction = await client.aio.interactions.create(
                    model=cand,
                    system_instruction=system_instruction,
                    input=prompt,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": DivvunFixSchema.model_json_schema(),
                    },
                    generation_config={
                        "thinking_level": "low",
                        "max_output_tokens": 32768,
                    },
                )
                raw_json = extract_interaction_text(interaction)
                if not raw_json:
                    continue
                try:
                    parsed_obj = DivvunFixSchema.model_validate_json(raw_json)
                    if parsed_obj.corrected_text.strip():
                        return parsed_obj.corrected_text
                except Exception:
                    fallback_dict = extract_gemini_json(raw_json)
                    corrected = fallback_dict.get("corrected_text")
                    if isinstance(corrected, str) and corrected.strip():
                        return corrected
            except Exception as exc:
                logger.warning(
                    "Divvun-sluttpass med %s feilet: %s",
                    cand,
                    sanitize_error_message(str(exc), active_key),
                )
                continue
    except Exception as exc:
        logger.warning("Kunne ikke opprette Gemini-klient i sluttpass: %s", sanitize_error_message(str(exc), active_key))
    return None


def _build_refiner_user_prompt(
    source_text: str,
    tartu_draft: Optional[str],
    divvun_corrected: Optional[str],
    compact_errs: list,
    local_tips: list,
    source_lang: str,
) -> str:
    if source_lang == "sme":
        return f"""NORDSAMISK KILDETEKST SOM SKAL SPRÅKVASKES OG KORRIGERES:
{source_text}

UTKAST ETTER FØRSTE DIVVUN-KORREKTUR:
{divvun_corrected or source_text}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER (Giellagiehtagirji & Riektačállinrávvagat):
{json.dumps(local_tips, ensure_ascii=False)}

Oppgave:
1. Gjennomfør en grundig, men skånsom språkvask og korrektur av den nordsamiske kildeteksten som Giellaverdde (etter `giellaverdde`-skillen).
2. Slå ved behov opp relevante fagfiler i `references/` med `read_giellaverdde_reference` (f.eks. ved passiv/aktiv, `su` vs. `iežas`, tallbøying, sammensatte ord, tegnsetting eller kasusstyring) og rett teksten i henhold til rådene.
3. Bevar tekstens opprinnelige mening, tone, sitater og eksakte avsnittsinndeling – ikke utelat avsnitt og ikke legg til nytt innhold.
4. Returner gyldig JSON med nøklene `"final_translation"` og `"improvements"` (korte punkter på norsk som gjengir hvilke råd og `references/`-regler fra `giellaverdde` du fulgte)."""

    lang_cfg = SOURCE_LANGUAGES.get(source_lang, SOURCE_LANGUAGES["nor"])
    lang_label = str(lang_cfg["label_no"]).lower()
    source_heading = str(lang_cfg["source_heading"])

    if tartu_draft:
        draft_section = f"""RÅOVERSETTELSE FRA TARTUNLP ({lang_cfg['label_no']} → Nordsamisk):
{tartu_draft}

ETTER FØRSTE DIVVUN-KORREKTUR:
{divvun_corrected or tartu_draft}

DIVVUN FEILRAPPORT (utvalg):
{json.dumps(compact_errs, ensure_ascii=False)}

AUTOMATISKE SPRÅKVARSLER:
{json.dumps(local_tips, ensure_ascii=False)}"""
        draft_hint = (
            "Bruk TartuNLP- og Divvun-utkastet som morfologisk hjelp der det treffer godt, "
            "men skriv fritt om til naturlig, idiomatisk nordsamisk for å unngå ord-for-ord-oversettelse, passivsyke og substantivsyke."
        )
    else:
        draft_section = (
            "MERK: Maskinoversettelse fra TartuNLP var ikke tilgjengelig for denne teksten. "
            "Oversett direkte fra kildeteksten til idiomatisk nordsamisk."
        )
        draft_hint = (
            "Oversett direkte til naturlig, idiomatisk nordsamisk uten kalkering av kildespråkets syntaks."
        )

    return f"""{source_heading} (ALLE avsnitt, overskrifter og sitater skal oversettes til nordsamisk):
{source_text}

{draft_section}

Oppgave:
1. Lag en presis, naturlig og idiomatisk nordsamisk oversettelse av HELE den {lang_label}e kildeteksten med nøyaktig samme avsnittsinndeling.
2. {draft_hint} Slå opp relevante fagfiler i `giellaverdde`-skillens `references/` med `read_giellaverdde_reference` ved behov, og rett i henhold til rådene derfra (med `01-nrk-standarda.md` som øverste myndighet).
3. Returner gyldig JSON med nøklene `"final_translation"` og `"improvements"` (korte punkter på norsk som gjengir hvilke råd og `references/`-regler fra `giellaverdde` som ble fulgt)."""


async def call_gemini_refiner(
    source_text: str,
    tartu_draft: Optional[str],
    divvun_corrected: Optional[str],
    divvun_errs: list,
    local_tips: list,
    override_key: Optional[str] = None,
    override_model: Optional[str] = None,
    source_lang: str = "nor",
    thinking_level: Literal["low", "medium", "high"] = "medium",
    glossary: Optional[str] = None,
) -> dict:
    """Trinn 3: Oversetter / språkvasker til nordsamisk via Google GenAI Interactions API (Gemini 4)."""
    active_key = (override_key or GEMINI_API_KEY).strip()
    requested_model, deprecation_note = normalize_gemini_model(override_model, source_lang)
    fallback_text = divvun_corrected or tartu_draft or (source_text if source_lang == "sme" else "")

    if not active_key or active_key == PLACEHOLDER_KEY:
        result = {
            "final_translation": fallback_text,
            "improvements": [],
            "llm_active": False,
            "used_model": None,
        }
        add_local_improvement(result, source_lang, "missing_key_fallback" if fallback_text else "missing_key_no_fallback")
        return result

    compact_errs = [
        {
            "error_text": e.get("error_text"),
            "title": e.get("title"),
            "suggestions": (e.get("suggestions") or [])[:3],
        }
        for e in divvun_errs[:40]
    ]

    user_prompt = _build_refiner_user_prompt(
        source_text=source_text,
        tartu_draft=tartu_draft,
        divvun_corrected=divvun_corrected,
        compact_errs=compact_errs,
        local_tips=[{k: v for k, v in tip.items() if k != "translations"} for tip in local_tips],
        source_lang=source_lang,
    )
    system_instruction = build_system_instruction(source_lang=source_lang, glossary=glossary)

    fallback_candidates = [
        requested_model,
        "gemini-4-argon",
        "gemini-4-hydrogen",
        "gemini-4-carbon",
        "gemini-3.5-flash-lite",
    ]
    models_to_try = list(dict.fromkeys(fallback_candidates))

    last_error_msg = ""
    try:
        client = genai.Client(
            api_key=active_key,
            http_options={"timeout": GEMINI_REQUEST_TIMEOUT_MS},
        )
    except Exception as exc:
        safe_err = sanitize_error_message(str(exc), active_key)
        result = {
            "final_translation": fallback_text,
            "improvements": [],
            "llm_active": False,
            "used_model": None,
        }
        add_local_improvement(result, source_lang, "sdk_error", error=safe_err)
        return result

    tried_dynamic_list = False
    idx = 0
    while idx < len(models_to_try):
        candidate_model = models_to_try[idx]
        retried_overload = False

        while True:
            try:
                history: List[dict] = [
                    {
                        "type": "user_input",
                        "content": [{"type": "text", "text": user_prompt}],
                    }
                ]
                has_refs = bool(list_giellaverdde_references())
                tools_arg = [READ_GIELLAVERDDE_TOOL] if has_refs else None
                consulted_refs: List[str] = []
                interaction = None

                for _round in range(5):
                    create_kwargs = {
                        "model": candidate_model,
                        "system_instruction": system_instruction,
                        "store": False,
                        "input": history,
                        "response_format": {
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": RefinementSchema.model_json_schema(),
                        },
                        "generation_config": {
                            "thinking_level": thinking_level,
                            "max_output_tokens": 32768,
                        },
                    }
                    if tools_arg:
                        create_kwargs["tools"] = tools_arg

                    interaction = await client.aio.interactions.create(**create_kwargs)
                    steps = getattr(interaction, "steps", None) or []
                    fc_steps = [s for s in steps if getattr(s, "type", None) == "function_call"]
                    if not fc_steps:
                        break

                    for s in steps:
                        history.append(s.model_dump())

                    for fc in fc_steps:
                        fc_name = getattr(fc, "name", "")
                        fc_args = getattr(fc, "arguments", None) or {}
                        if fc_name == "read_giellaverdde_reference":
                            fname = str(fc_args.get("filename", ""))
                            ref_content = read_giellaverdde_reference(fname)
                            clean_fname = os.path.basename(fname.strip())
                            if clean_fname and clean_fname not in consulted_refs:
                                consulted_refs.append(clean_fname)
                        else:
                            ref_content = f"Ukjent verktøy: {fc_name}"
                        history.append(
                            {
                                "type": "function_result",
                                "name": fc_name,
                                "call_id": getattr(fc, "id", ""),
                                "result": [{"type": "text", "text": ref_content}],
                            }
                        )

                raw_json = extract_interaction_text(interaction) if interaction is not None else ""
                final_trans = ""
                improvements: List[str] = []

                if raw_json:
                    try:
                        validated = RefinementSchema.model_validate_json(raw_json)
                        final_trans = validated.final_translation
                        improvements = list(validated.improvements)
                    except Exception:
                        parsed = extract_gemini_json(raw_json)
                        final_trans = parsed.get("final_translation") or ""
                        improvements = list(parsed.get("improvements") or [])

                if final_trans and final_trans.strip():
                    result = {
                        "final_translation": final_trans,
                        "improvements": improvements,
                        "llm_active": True,
                        "used_model": candidate_model,
                    }
                    if consulted_refs:
                        add_local_improvement(result, source_lang, "references_used", references=", ".join(consulted_refs))
                    if getattr(interaction, "status", None) == "incomplete":
                        add_local_improvement(result, source_lang, "incomplete", first=True)
                    if candidate_model != requested_model:
                        add_local_improvement(
                            result, source_lang, "fallback_model", first=True,
                            requested=requested_model, used=candidate_model,
                        )
                    if deprecation_note:
                        add_local_improvement(
                            result, source_lang, "deprecated", first=True,
                            model=(override_model or GEMINI_MODEL or DEFAULT_GEMINI_MODEL).strip(),
                        )
                    return result

                last_error_msg = ui_message(source_lang, "invalid_response", model=candidate_model)
                break
            except Exception as exc:
                status_code, should_fallback = _classify_gemini_exception(exc)
                safe_err = sanitize_error_message(str(exc), active_key)
                last_error_msg = f"{candidate_model}: {safe_err}"
                logger.warning("Gemini API feil (%s): %s", status_code, last_error_msg)

                if status_code == 503 and not retried_overload:
                    retried_overload = True
                    await asyncio.sleep(1.5)
                    continue

                if should_fallback:
                    if status_code == 404 and not tried_dynamic_list:
                        tried_dynamic_list = True
                        avail = await fetch_available_gemini_models(active_key)
                        for m in avail:
                            if m["id"] not in models_to_try:
                                models_to_try.append(m["id"])
                    break

                result = {
                    "final_translation": fallback_text,
                    "improvements": [],
                    "llm_active": False,
                    "used_model": candidate_model,
                }
                add_local_improvement(result, source_lang, "api_error", model=candidate_model, error=safe_err)
                return result

        idx += 1

    result = {
        "final_translation": fallback_text,
        "improvements": [],
        "llm_active": False,
        "used_model": requested_model,
    }
    add_local_improvement(result, source_lang, "no_model", error=last_error_msg)
    return result


async def run_translation_pipeline_events(
    req: TranslateRequest,
    header_api_key: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Felles pipeline-generator som brukes av både /api/translate og /api/translate-stream."""
    src_lang = req.source_lang
    is_sami_source = src_lang == "sme"
    effective_key = (req.api_key or header_api_key or GEMINI_API_KEY).strip() or None

    # Trinn 1: Klargjøring eller TartuNLP
    yield progress_event(
        src_lang, 1, 20, "step1_sami" if is_sami_source else "step1_translation",
        "step1_sami_detail" if is_sami_source else "step1_detail",
        language={"nor": "Norsk", "swe": "Svenska", "fin": "Suomi", "eng": "English"}.get(src_lang, ""),
    )

    if is_sami_source:
        tartu_raw: Optional[str] = req.text
        tartu_display = req.text
    else:
        tartu_raw = await call_tartu_mt(req.text, src=src_lang, tgt="sme")
        tartu_display = (
            tartu_raw
            if tartu_raw is not None
            else ui_message(src_lang, "no_tartu")
        )

    # Trinn 2: Divvun 1. runde (kjøres KUN når vi faktisk har samisk tekst å sjekke!)
    yield progress_event(
        src_lang, 2, 40, "step2",
        "step2_detail" if tartu_raw is not None else "step2_skipped",
    )

    if tartu_raw is not None:
        divvun_initial = await call_divvun_grammar(tartu_raw)
        initial_errs = divvun_initial.get("errs", [])
        divvun_pre_corrected: Optional[str] = (
            apply_divvun_suggestions(
                tartu_raw,
                initial_errs,
                protect_proper_nouns=True,
                source_text="" if is_sami_source else req.text,
            )
            if req.auto_apply_divvun
            else tartu_raw
        )
        local_tips = local_heuristic_checks(
            "" if is_sami_source else req.text,
            divvun_pre_corrected or "",
            src_lang,
        )
    else:
        initial_errs = []
        divvun_pre_corrected = None
        local_tips = []

    # Trinn 3: Gemini 4 Språkvask / Oversettelse
    if req.use_llm:
        chosen_model, _ = normalize_gemini_model(req.model)
        yield progress_event(
            src_lang, 3, 70, "step3_sami" if is_sami_source else "step3_translation",
            "step3_sami_detail" if is_sami_source else "step3_detail", model=chosen_model,
        )
        llm_result = await call_gemini_refiner(
            source_text=req.text,
            tartu_draft=tartu_raw,
            divvun_corrected=divvun_pre_corrected,
            divvun_errs=initial_errs,
            local_tips=local_tips,
            override_key=effective_key,
            override_model=req.model,
            source_lang=src_lang,
            thinking_level=req.thinking_level,
            glossary=req.glossary,
        )
    else:
        if divvun_pre_corrected is None and not is_sami_source:
            llm_result = {
                "final_translation": "",
                "improvements": [],
                "llm_active": False,
                "used_model": None,
            }
            add_local_improvement(llm_result, src_lang, "no_translation")
        else:
            llm_result = {
                "final_translation": divvun_pre_corrected or req.text,
                "improvements": [],
                "llm_active": False,
                "used_model": None,
            }
            add_local_improvement(llm_result, src_lang, "gemini_off")

    gemini_text = llm_result.get("final_translation") or ""
    llm_succeeded = bool(llm_result.get("llm_active", False))

    # Trinn 4: Sluttkontroll med Divvun
    yield progress_event(src_lang, 4, 88, "step4", "step4_detail")

    final_text = gemini_text
    final_divvun = await call_divvun_grammar(final_text) if final_text.strip() else {"errs": []}
    final_errs = final_divvun.get("errs", [])

    if req.auto_apply_divvun and final_errs and final_text.strip():
        initial_err_count = len(final_errs)
        if llm_succeeded:
            yield progress_event(
                src_lang, 4, 94, "step4_fix", "step4_fix_detail", count=initial_err_count,
            )
            refined_by_divvun = await call_gemini_final_divvun_pass(
                source_text=req.text,
                gemini_draft=final_text,
                divvun_errs=final_errs,
                override_key=effective_key,
                override_model=req.model,
                source_lang=src_lang,
                glossary=req.glossary,
            )
            if refined_by_divvun and refined_by_divvun.strip() and refined_by_divvun != final_text:
                final_text = refined_by_divvun
                final_divvun = await call_divvun_grammar(final_text)
                final_errs = final_divvun.get("errs", [])

        if final_errs:
            smart_corrected = apply_divvun_suggestions(
                final_text,
                final_errs,
                protect_proper_nouns=True,
                source_text="" if is_sami_source else req.text,
            )
            # Kall kun Divvun på nytt dersom teksten faktisk ble endret!
            if smart_corrected != final_text:
                final_text = smart_corrected
                final_divvun = await call_divvun_grammar(final_text)
                final_errs = final_divvun.get("errs", [])

        fixed_count = max(0, initial_err_count - len(final_errs))
        if fixed_count > 0:
            add_local_improvement(llm_result, src_lang, "fixed_count", fixed=fixed_count, total=initial_err_count)

    # Siste ord-for-ord rettskrivingstest via Divvun Speller (/speller/se)
    speller_errs = await call_divvun_speller(final_text) if final_text.strip() else []
    localize_speller_errors(speller_errs, src_lang)
    merged_final_errs = merge_divvun_errors(final_errs, speller_errs)

    final_local_tips = (
        local_heuristic_checks("" if is_sami_source else req.text, final_text, src_lang)
        if final_text.strip()
        else []
    )

    combined_tips = (
        final_local_tips
        if llm_succeeded
        else (local_tips + [t for t in final_local_tips if t not in local_tips])
    )

    result_payload = {
        "source_text": req.text,
        "source_lang": src_lang,
        "step1_tartu_raw": tartu_display,
        "step1_raw_translations": (
            {language: ui_message(language, "no_tartu") for language in UI_LANGUAGES}
            if tartu_raw is None else {}
        ),
        "step1_had_tartu": tartu_raw is not None,
        "step2_divvun_initial_errors": initial_errs,
        "step2_divvun_corrected": divvun_pre_corrected or "",
        "step3_final_text": final_text,
        "step3_improvements": llm_result.get("improvements", []),
        "improvement_translations": llm_result.get("improvement_translations", {}),
        "llm_active": llm_succeeded,
        "used_model": llm_result.get("used_model"),
        "final_divvun_errors": merged_final_errs,
        "language_tips": combined_tips,
    }

    yield {
        "type": "result",
        "percent": 100,
        "data": result_payload,
    }


@app.post("/api/translate")
async def translate_pipeline(
    req: TranslateRequest,
    x_gemini_api_key: Annotated[
        Optional[str], Header(alias="X-Gemini-Api-Key")
    ] = None,
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail=ui_message(req.source_lang, "empty_text"))

    final_data = None
    async for event in run_translation_pipeline_events(req, header_api_key=x_gemini_api_key):
        if event.get("type") == "result":
            final_data = event["data"]

    if final_data is None:
        raise HTTPException(status_code=500, detail=ui_message(req.source_lang, "no_result"))
    return final_data


@app.post("/api/translate-stream")
async def translate_pipeline_stream(
    req: TranslateRequest,
    x_gemini_api_key: Annotated[
        Optional[str], Header(alias="X-Gemini-Api-Key")
    ] = None,
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail=ui_message(req.source_lang, "empty_text"))

    effective_key = (req.api_key or x_gemini_api_key or GEMINI_API_KEY).strip()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in run_translation_pipeline_events(req, header_api_key=x_gemini_api_key):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except asyncio.CancelledError:
            logger.info("Klienten avbrøt oversettelsesstrømmen.")
            raise
        except Exception as exc:
            safe_msg = sanitize_error_message(str(exc), effective_key)
            logger.error("Uventet feil i translate-stream: %s", safe_msg)
            yield json.dumps({"type": "error", "message": safe_msg}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/api/proofread")
async def proofread_only(req: ProofreadRequest):
    """Lar brukeren kjøre ren Divvun-korrektur + Speller (/speller/se) + språksjekk når de redigerer den samiske teksten manuelt."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail=ui_message(req.source_lang, "empty_text"))
    divvun_res, speller_errs = await asyncio.gather(
        call_divvun_grammar(req.text),
        call_divvun_speller(req.text),
    )
    localize_speller_errors(speller_errs, req.source_lang)
    merged_errs = merge_divvun_errors(divvun_res.get("errs", []), speller_errs)
    tips = local_heuristic_checks("", req.text, req.source_lang)
    return {
        "text": req.text,
        "errs": merged_errs,
        "language_tips": tips,
    }


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
