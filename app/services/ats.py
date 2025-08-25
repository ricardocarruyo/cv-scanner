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
    docx_fonts=None,
):
    t = (text or "")
    t_lc = t.lower()
    words = re.findall(r"\b\w+\b", t_lc)
    wcount = len(words)

    # 1) Secciones detectadas (listas)
    sections_present, sections_missing, found_sections = _detect_sections(t_lc)

    # Booleans por sección (5 checks)
    sec_perfil      = ("perfil profesional"   in sections_present)
    sec_experiencia = ("experiencia laboral"  in sections_present)
    sec_educacion   = ("educación"            in sections_present)
    sec_habilidades = ("habilidades"          in sections_present)
    sec_idiomas     = ("idiomas"              in sections_present)

    # 2) Páginas (1 check)
    if pdf_meta and isinstance(pdf_meta.get("pages"), int):
        pages = pdf_meta["pages"]
    else:
        pages = estimate_pages_from_words(wcount)
    paginas_ok = (pages <= 2)

    # 3) Imágenes/Tablas (2 checks)
    images = 0
    tables = 0
    if pdf_meta:
        images += int(pdf_meta.get("images", 0))
        # si alguna vez extraes tablas/columnas del PDF, súmalas aquí
    if docx_meta:
        images += int(docx_meta.get("images", 0))
        tables += int(docx_meta.get("tables", 0))

    no_imagenes = (images == 0)           # preferido: sin imágenes
    no_tablas   = (tables == 0)           # preferido: sin tablas/columnas

    # 4) Tipografías (1 check)
    # preferimos docx_fonts (ya normalizado por quien llama)
    if isinstance(docx_fonts, (list, tuple)):
        detected_fonts = list(docx_fonts)
    elif docx_meta and isinstance(docx_meta.get("fonts"), list):
        detected_fonts = list(docx_meta["fonts"])
    elif pdf_meta and isinstance(pdf_meta.get("fonts"), list):
        detected_fonts = list(pdf_meta["fonts"])
    else:
        detected_fonts = None

    normalized = normalize_fonts(detected_fonts)
    if normalized:
        if any(f in GOOD_FONTS for f in normalized):
            tipografia_segura = True
        elif any(f in BAD_FONTS for f in normalized):
            tipografia_segura = False
        else:
            tipografia_segura = False
    else:
        # Si no pudimos detectar fuentes, asumimos NO segura para que el % refleje
        # exactamente el checklist (sin “bonos”).
        tipografia_segura = False

    # =========================
    # 9 CHECKS DEL CHECKLIST
    # =========================
    checks = {
        # secciones (5)
        "perfil": sec_perfil,
        "experiencia": sec_experiencia,
        "educacion": sec_educacion,
        "habilidades": sec_habilidades,
        "idiomas": sec_idiomas,
        # estructura (3)
        "no_imagenes": no_imagenes,
        "no_tablas": no_tablas,
        "tipografia_segura": tipografia_segura,
        # páginas (1)
        "paginas_ok": paginas_ok,
    }

    ok_count = sum(1 for v in checks.values() if v is True)
    total = len(checks)   # 9
    score = round((ok_count / total) * 100)

    details = {
        # Para tu UI actual:
        "sections_present": sections_present,
        "sections_missing": sections_missing,
        "sections_found": found_sections,

        "pages": pages,
        "images": images,
        "tables": tables,

        # Flags tal como los usas en la plantilla
        "no_images": no_imagenes,
        "no_tables": no_tablas,
        "has_images": images > 0,
        "has_tables_or_columns": tables > 0,
        "safe_typography": tipografia_segura,

        # Nuevo bloque compacto para pintar el checklist directamente si quieres
        "checks": checks,
    }
    return score, details

# (Opcional) si en algún lado importabas el nombre anterior, deja un alias:
evaluate_ats_ = evaluate_ats_compliance
