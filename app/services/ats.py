# app/services/ats.py
import re
from collections import Counter
from typing import Dict, List, Optional

# Diccionario de secciones y SINÓNIMOS (ES/EN) – ¡NO CAMBIAR CLAVES!
SECTION_SYNONYMS: Dict[str, List[str]] = {
    "perfil profesional": [
        r"\bperfil profesional\b", r"\bresumen profesional\b", r"\bresumen\b",
        r"\bobjetivo\b", r"\bobjetivos\b",
        r"\bsummary\b", r"\bprofessional summary\b", r"\bprofile\b", r"\bobjective\b"
    ],
    "experiencia laboral": [
        r"\bexperiencia laboral\b", r"\bexperiencia profesional\b",
        r"\bexperiencia\b",
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
        r"\bidiomas\b", r"\blengu(as|as)\b",
        r"\blanguages\b"
    ],
}

# Fuentes “seguras” (ATS-friendly) / “no recomendadas”
GOOD_FONTS = {"arial", "helvetica", "calibri", "verdana", "roboto", "georgia", "times new roman", "inter", "source sans pro"}
BAD_FONTS  = {"comic sans", "papyrus", "monotype corsiva", "brush script", "impact"}

def estimate_pages_from_words(word_count: int) -> int:
    # 500–650 palabras/página aprox
    return max(1, round(word_count / 600))

def _detect_sections(text_lower: str):
    """Devuelve listas: presentes, faltantes y el conteo."""
    present = []
    missing = []
    for canonical, patterns in SECTION_SYNONYMS.items():
        hit = any(re.search(p, text_lower, flags=re.IGNORECASE) for p in patterns)
        (present if hit else missing).append(canonical)
    return present, missing, len(present)

def evaluate_ats_compliance(
    text: str,
    lang_code: str,
    ext: str,
    pdf_meta=None,
    docx_meta=None,
    docx_fonts=None  # <- usamos este nombre para ambos casos (docx o pdf)
):
    """
    Devuelve (score_ats, details) donde details incluye:
      - sections_present / sections_missing / sections_found
      - lang_ok
      - pages
      - images / tables
      - no_images / no_tables
      - fonts_bonus
      - has_images (bool)
      - has_tables_or_columns (bool)
      - safe_typography: True/False/None (None = indeterminado, típico en PDF)
    """
    t = (text or "")
    t_lc = t.lower()
    words = re.findall(r"\b\w+\b", t_lc)
    wcount = len(words)

    # 1) Secciones clave (con sinónimos)
    sections_present, sections_missing, found_sections = _detect_sections(t_lc)

    # 2) Idioma: ES o EN válidos
    lang_ok = (lang_code in ("es", "en"))

    # 3) Páginas
    if pdf_meta and isinstance(pdf_meta.get("pages"), int):
        pages = pdf_meta["pages"]
    else:
        pages = estimate_pages_from_words(wcount)
    pages_ok = pages <= 2

    # 4) Imágenes / tablas/columnas
    images = 0
    tables = 0
    if pdf_meta:
        images += int(pdf_meta.get("images", 0))
    if docx_meta:
        images += int(docx_meta.get("images", 0))
        tables += int(docx_meta.get("tables", 0))
    no_images = (images == 0)
    no_tables = (tables == 0)

    has_images = images > 0
    has_tables_or_columns = tables > 0

    # Tipografía segura
    safe_typography = None
    fonts_list = None
    if isinstance(docx_fonts, (list, tuple)):
        fonts_list = [str(f).strip().lower() for f in docx_fonts if f]

    if fonts_list is not None and len(fonts_list) > 0:
        if any(f in GOOD_FONTS for f in fonts_list):
            safe_typography = True
        elif any(f in BAD_FONTS for f in fonts_list):
            safe_typography = False
        else:
            safe_typography = False
    else:
        safe_typography = None  # indeterminado si no pudimos leer fuentes
        
    # Preferimos docx_fonts explícito; si no, intentamos docx_meta['fonts']
    fonts_list = None
    if docx_fonts:
        fonts_list = [f.strip().lower() for f in docx_fonts if f]
    elif docx_meta and isinstance(docx_meta.get("fonts"), list):
        fonts_list = [str(f).strip().lower() for f in docx_meta["fonts"] if f]

    if fonts_list is not None:
        # Regla simple: si hay alguna de GOOD_FONTS => True; si hay alguna BAD_FONTS => False;
        # si ninguna coincide, consideramos False (no segura) para ser estrictos.
        if any(f in GOOD_FONTS for f in fonts_list):
            safe_typography = True
        elif any(f in BAD_FONTS for f in fonts_list):
            safe_typography = False
        else:
            safe_typography = False
    else:
        # No sabemos (PDF u otro caso sin fuentes detectables)
        safe_typography = None

    # 6) Bonus por mencionar fuentes seguras en texto (heurística débil para PDFs)
    common = [w for w in words if w.isalpha()]
    _ = [w for w, _c in Counter(common).most_common(200)]
    fonts_bonus = 0
    if safe_typography is None:
        if any(f in t_lc for f in GOOD_FONTS):
            fonts_bonus = 3  # bonus leve por mención textual

    # ===== Scoring =====
    score = 0
    # Secciones: hasta 45 pts (9 c/u, 5 secciones)
    score += min(found_sections, 5) * 9
    # Idioma ES/EN: 20 pts
    score += 20 if lang_ok else 0
    # Páginas: <=2 15 pts; 3 páginas 7 pts
    if pages_ok:
        score += 15
    elif pages == 3:
        score += 7
    # Evitar imágenes y tablas/columnas: 10 + 10
    score += 10 if no_images else 0
    score += 10 if no_tables else 0
    # Tipografía segura conocida suma 5; indeterminado no penaliza (se maneja con fonts_bonus si aplica)
    if safe_typography is True:
        score += 5
    # Bonus menor por mención textual (solo si indeterminado)
    score += fonts_bonus

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
    }
    return score, details
