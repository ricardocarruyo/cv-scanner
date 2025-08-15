# app/services/ats.py
import re
from collections import Counter
from typing import Dict, List, Optional, Iterable

SECTION_SYNONYMS: Dict[str, List[str]] = {
    "perfil profesional": [
        r"\bperfil profesional\b", r"\bresumen profesional\b", r"\bresumen\b",
        r"\bobjetivo\b", r"\bobjetivos\b",
        r"\bsummary\b", r"\bprofessional summary\b", r"\bprofile\b", r"\bobjective\b"
    ],
    "experiencia laboral": [
        r"\bexperiencia laboral\b", r"\bexperiencia profesional\b",
        r"\bexperiencia\b", r"\bprofessional experience\b", r"\bexperience\b",
        r"\bwork experience\b", r"\bemployment history\b", r"\bcareer history\b"
    ],
    "educación": [
        r"\beducaci[oó]n\b", r"\bformaci[oó]n acad[eé]mica\b",
        r"\beducation\b", r"\bacademic background\b"
    ],
    "habilidades": [
        r"\bhabilidades\b", r"\bcompetencias\b", r"\bhard skills\b", r"\bsoft skills\b",
        r"\bskills\b", r"\btechnical skills\b"
    ],
    "idiomas": [
        r"\bidiomas\b", r"\bidioma\b", r"\blengu(as|as)\b",
        r"\blanguages\b"
    ],
}

GOOD_FONTS = {
    "arial", "helvetica", "calibri", "verdana",
    "roboto", "georgia", "times new roman",
    "inter", "source sans pro"
}
BAD_FONTS = {"comic sans", "papyrus", "monotype corsiva", "brush script", "impact"}

def estimate_pages_from_words(word_count: int) -> int:
    return max(1, round(word_count / 600))

def _detect_sections(text_lower: str):
    present, missing = [], []
    for canonical, patterns in SECTION_SYNONYMS.items():
        hit = any(re.search(p, text_lower, flags=re.IGNORECASE) for p in patterns)
        (present if hit else missing).append(canonical)
    return present, missing, len(present)

# ---- Normalización de nombres de fuentes ----
# Mapea variantes como "Arial-BoldMT", "ArialMT", "ARIAL", "TimesNewRomanPS-BoldItalicMT", etc.
FONT_ALIASES = {
    "timesnewromanps": "times new roman",
    "timesnewroman": "times new roman",
    "arialmt": "arial",
    "arial-boldmt": "arial",
    "arial-bold": "arial",
    "arial-italic": "arial",
    "helveticaneue": "helvetica",
    "symbolmt": "symbol"  # no es "segura", pero la identificamos
}

def normalize_font_name(name: str) -> str:
    if not name:
        return ""
    n = name.strip().lower()

    # sacar espacios y guiones para detectar alias de familia
    raw = re.sub(r"[\s_]+", "", n)

    # quitar sufijos comunes de Adobe/Monotype
    raw = re.sub(r"(ps)?-?(bold|italic|oblique|bolditalic|boldoblique|regular|mt)$", "", raw)

    # quitar "ps-" en el medio y otros sufijos conocidos
    raw = raw.replace("psmt", "").replace("ps", "")

    # aplicar alias conocidos
    if raw in FONT_ALIASES:
        return FONT_ALIASES[raw]

    # si viene con guiones, quédate con el primer trozo (p.ej. arial-boldmt -> arial)
    base = n.split("-")[0]

    # limpieza final
    base = base.replace("mt", "").strip()
    base = re.sub(r"\s+", " ", base)

    # mapear algunos compactos
    if base in ("timesnewroman", "timesnewromanps"):
        base = "times new roman"

    return base

def normalize_fonts(fonts: Optional[Iterable[str]]) -> List[str]:
    if not fonts:
        return []
    return sorted(set(f for f in (normalize_font_name(x) for x in fonts) if f))

def evaluate_ats_compliance(
    text: str,
    lang_code: str,
    ext: str,
    pdf_meta=None,
    docx_meta=None,
    docx_fonts=None  # aquí pasan tanto fuentes de DOCX como de PDF (via main)
):
    t = (text or "")
    t_lc = t.lower()
    words = re.findall(r"\b\w+\b", t_lc)
    wcount = len(words)

    # 1) Secciones
    sections_present, sections_missing, found_sections = _detect_sections(t_lc)

    # 2) Idioma
    lang_ok = (lang_code in ("es", "en"))

    # 3) Páginas
    if pdf_meta and isinstance(pdf_meta.get("pages"), int):
        pages = pdf_meta["pages"]
    else:
        pages = estimate_pages_from_words(wcount)
    pages_ok = pages <= 2

    # 4) Imágenes / Tablas
    images = 0
    tables = 0
    if pdf_meta:
        images += int(pdf_meta.get("images", 0))
        # si el extractor de PDF detectara tablas/columnas se podrían sumar aquí
    if docx_meta:
        images += int(docx_meta.get("images", 0))
        tables += int(docx_meta.get("tables", 0))

    no_images = (images == 0)
    no_tables = (tables == 0)

    has_images = images > 0
    has_tables_or_columns = tables > 0

    # 5) Tipografías (PDF o DOCX)
    detected_fonts = None

    # preferimos el parámetro explícito docx_fonts (usa ambos casos: docx o pdf)
    if isinstance(docx_fonts, (list, tuple)):
        detected_fonts = list(docx_fonts)
    # o si vino en meta de docx
    elif docx_meta and isinstance(docx_meta.get("fonts"), list):
        detected_fonts = list(docx_meta["fonts"])
    # o si vino en meta de pdf (por si decides no enviarlo en docx_fonts)
    elif pdf_meta and isinstance(pdf_meta.get("fonts"), list):
        detected_fonts = list(pdf_meta["fonts"])

    normalized = normalize_fonts(detected_fonts)
    safe_typography: Optional[bool]
    if normalized:
        if any(f in GOOD_FONTS for f in normalized):
            safe_typography = True
        elif any(f in BAD_FONTS for f in normalized):
            safe_typography = False
        else:
            # si no coincide con ninguna lista, se considera “no segura”
            safe_typography = False
    else:
        safe_typography = None  # indeterminado (común en PDFs si no hay PyMuPDF)

    # 6) Bonus leve si es indeterminado pero se menciona una fuente segura en el texto
    common = [w for w in words if w.isalpha()]
    _ = [w for w, _c in Counter(common).most_common(200)]
    fonts_bonus = 0
    if safe_typography is None:
        if any(f in t_lc for f in GOOD_FONTS):
            fonts_bonus = 3

    # ===== Scoring =====
    score = 0
    score += min(found_sections, 5) * 9        # secciones (hasta 45)
    score += 20 if lang_ok else 0              # idioma
    if pages_ok:                               # páginas
        score += 15
    elif pages == 3:
        score += 7
    score += 10 if no_images else 0            # sin imágenes
    score += 10 if no_tables else 0            # sin tablas/columnas
    if safe_typography is True:                # tipografía segura confirmada
        score += 5
    score += fonts_bonus                       # bonus textual si indeterminado

    score = max(0, min(100, score))

    details = {
        "sections_present": sections_present,
        "sections_missing": sections_missing,
        "sections_found": found_sections,
        "lang_ok": lang_ok,
        "pages": pages,
        "images": images,
        "tables": tables,
        "no_images": no_images,
        "no_tables": no_tables,
        "has_images": has_images,
        "has_tables_or_columns": has_tables_or_columns,
        "safe_typography": safe_typography,
        "fonts_bonus": fonts_bonus,
        # opcional: para depurar puedes exponer qué fuentes se detectaron
        # "detected_fonts": normalized,
    }
    return score, details
