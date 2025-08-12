# ...lo que ya tenés arriba...
import fitz  # PyMuPDF
from docx import Document

def extract_pdf(data: bytes):
    doc = fitz.open(stream=data, filetype="pdf")
    pages = doc.page_count
    text = []
    image_count = 0
    for i in range(pages):
        p = doc.load_page(i)
        text.append(p.get_text() or "")
        image_count += len(p.get_images(full=True))
    return "\n".join(text), {"pages": pages, "images": image_count}

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
