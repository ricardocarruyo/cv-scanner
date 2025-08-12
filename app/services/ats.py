# app/services/ats.py
import re
from collections import Counter

RE_SECTIONS = [
    r"\bsummary\b|\bobjective\b",
    r"\bexperience\b|\bwork experience\b|\bprofessional experience\b",
    r"\beducation\b",
    r"\bskills?\b",
    r"\bcertifications?\b|\blicenses?\b"
]
GOOD_FONTS = ("arial", "helvetica", "calibri", "verdana", "roboto")

def estimate_pages_from_words(word_count: int) -> int:
    # 500-650 palabras por página (aprox)
    return max(1, round(word_count / 600))

def evaluate_ats_compliance(
    text: str,
    lang_code: str,      # 'en'/'es'/...
    ext: str,            # 'pdf' o 'docx'
    pdf_meta=None,       # dict opcional: {'pages': int, 'images': int}
    docx_meta=None       # dict opcional: {'tables': int, 'images': int}
):
    t = text or ""
    t_lc = t.lower()
    words = re.findall(r"\b\w+\b", t_lc)
    wcount = len(words)

    # 1) Secciones clave
    found_sections = 0
    for pat in RE_SECTIONS:
        if re.search(pat, t_lc):
            found_sections += 1

    # 2) Idioma
    lang_ok = (lang_code == "en")

    # 3) Largo/páginas
    pages = None
    if pdf_meta and isinstance(pdf_meta.get("pages"), int):
        pages = pdf_meta["pages"]
    else:
        pages = estimate_pages_from_words(wcount)

    pages_ok = pages <= 2

    # 4) Imágenes/tablas
    images = 0
    tables = 0
    if pdf_meta:
        images += int(pdf_meta.get("images", 0))
    if docx_meta:
        images += int(docx_meta.get("images", 0))
        tables += int(docx_meta.get("tables", 0))

    no_images = (images == 0)
    no_tables = (tables == 0)

    # 5) “Fuentes” (muy aproximado, usando palabras frecuentes; no podemos leer fuentes reales sin inspección del binario)
    common = [w for w in words if w.isalpha()]
    top = [w for w, _ in Counter(common).most_common(200)]
    # no lo usamos para puntuar duro, solo como +5 si detectamos palabras de familias "seguras" en texto (heurística débil)
    fonts_bonus = 5 if any(f in t_lc for f in GOOD_FONTS) else 0

    # Scoring (base 100)
    score = 0
    # Secciones: 5 secciones => hasta 45 pts (9 c/u)
    score += min(found_sections, 5) * 9
    # Idioma inglés: 20 pts
    score += 20 if lang_ok else 0
    # Páginas: <=2 15 pts; 3 páginas 7 pts; más 0
    if pages_ok:
        score += 15
    elif pages == 3:
        score += 7
    # Imágenes/tablas: sin imágenes +10, sin tablas +10
    score += 10 if no_images else 0
    score += 10 if no_tables else 0
    # Bonus menor por “fuentes seguras”
    score += fonts_bonus

    score = max(0, min(100, score))

    details = {
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
