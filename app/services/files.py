import fitz  # PyMuPDF
from docx import Document
import io
from typing import Tuple, Dict, Any, List
from pdfminer.high_level import extract_text

def extract_pdf(data: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Devuelve:
      texto (str),
      pdf_meta: {
        'pages': int,
        'images': int,
        'fonts': List[str]   # <-- NUEVO
      }
    """
    text = ""
    pages = 0
    images = 0
    fonts: List[str] = []

    # 1) Intento preferido: PyMuPDF (fitz) — permite leer fuentes con fiabilidad
    try:        
        with fitz.open(stream=data, filetype="pdf") as doc:
            pages = doc.page_count
            for page in doc:
                # texto
                text += page.get_text("text")

                # imágenes
                try:
                    images += len(page.get_images(full=True))
                except Exception:
                    pass

                # fuentes desde spans
                try:
                    d = page.get_text("dict")
                    for block in d.get("blocks", []):
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                fname = span.get("font")
                                if fname:
                                    fonts.append(str(fname))
                except Exception:
                    # si falla la extracción estructurada, seguimos con lo que tengamos
                    pass

        pdf_meta = {"pages": pages, "images": images, "fonts": sorted(set(fonts))}
        return text, pdf_meta

    except Exception:
        # 2) Fallback sin PyMuPDF (solo texto, sin fuentes)
        pass

    # Fallback simple: intenta extraer texto con pdfminer o PyPDF2 si ya los usas
    try:
        # ejemplo con pdfminer.six de manera muy simple       
        text = extract_text(io.BytesIO(data))
    except Exception:
        text = ""

    # Sin acceso a fuentes en este camino
    return text, {"pages": 0, "images": 0, "fonts": []}

def extract_docx(data: bytes):
    # python-docx necesita un archivo; lo cargamos a tmp en memoria
    import io
    bio = io.BytesIO(data)
    d = Document(bio)

    # texto
    parts = []
    for p in d.paragraphs:
        parts.append(p.text or "")

    # tablas / imágenes
    tables = len(d.tables)
    images = 0
    # conteo básico de imágenes: shapes en headers/inline
    for r in d.inline_shapes:
        images += 1

    meta = {"tables": tables, "images": images}
    return "\n".join(parts), meta
