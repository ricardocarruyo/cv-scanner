# app/services/ats.py
import re
from collections import Counter

# Diccionario de secciones y SINÓNIMOS (ES/EN)
SECTION_SYNONYMS = {
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

GOOD_FONTS = ("arial", "helvetica", "calibri", "verdana", "roboto")

def estimate_pages_from_words(word_count: int) -> int:
    # 500-650 palabras/página aprox
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
    lang_code: str,      # 'es'/'en'/...
    ext: str,            # 'pdf' o 'docx'
    pdf_meta=None,       # {'pages': int, 'images': int}
    docx_meta=None       # {'tables': int, 'images': int}
):
    t = (text or "")
    t_lc = t.lower()
    words = re.findall(r"\b\w+\b", t_lc)
    wcount = len(words)

    # 1) Secciones clave (con sinónimos)
    sections_present, sections_missing, found_sections = _detect_sections(t_lc)

    # 2) Idioma: ahora ES o EN son válidos
    lang_ok = (lang_code in ("es", "en"))

    # 3) Páginas
    if pdf_meta and isinstance(pdf_meta.get("pages"), int):
        pages = pdf_meta["pages"]
    else:
        pages = estimate_pages_from_words(wcount)
    pages_ok = pages <= 2

    # 4) Imágenes / tablas
    images = 0
    tables = 0
    if pdf_meta:
        images += int(pdf_meta.get("images", 0))
    if docx_meta:
        images += int(docx_meta.get("images", 0))
        tables += int(docx_meta.get("tables", 0))
    no_images = (images == 0)
    no_tables = (tables == 0)

    # 5) Bonus por mencionar fuentes “seguras” (heurística débil)
    common = [w for w in words if w.isalpha()]
    _ = [w for w, _c in Counter(common).most_common(200)]
    fonts_bonus = 5 if any(f in t_lc for f in GOOD_FONTS) else 0

    # Scoring
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
    # Imágenes/Tablas (evitarlas): 10 + 10
    score += 10 if no_images else 0
    score += 10 if no_tables else 0
    # Bonus menor
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
        "fonts_bonus": fonts_bonus,
    }
    return score, details
