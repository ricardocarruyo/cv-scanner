import io, fitz
from docx import Document

def extract_pdf(b: bytes) -> str:
    doc = fitz.open(stream=b, filetype="pdf")
    return "\n".join([p.get_text() for p in doc])

def extract_docx(b: bytes) -> str:
    doc = Document(io.BytesIO(b))
    return "\n".join([p.text for p in doc.paragraphs])
