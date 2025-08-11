import io, re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

def _wrap_text(c, text, max_width):
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if c.stringWidth(test, "Helvetica", 11) <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = w
    if current: lines.append(current)
    return lines

def render_analysis_pdf(execution) -> io.BytesIO:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left, right = 2*cm, A4[0]-2*cm
    y = height - 2*cm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, "Informe de Análisis (CV Match Scanner)")
    y -= 18

    c.setFont("Helvetica", 11)
    meta = [
        f"Fecha: {execution.created_at.strftime('%Y-%m-%d %H:%M')}",
        f"Correo: {execution.email}",
        f"Archivo: {execution.uploaded_filename or '-'}",
        f"Modelo: {(execution.model_vendor or '-')}/{(execution.model_name or '-')}",
        f"Puntaje: {execution.score if execution.score is not None else '-'}",
        f"Idioma CV: {execution.resume_lang or '-'} | Idioma JD: {execution.jd_lang or '-'}",
    ]
    for m in meta:
        c.drawString(left, y, m); y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "Análisis:")
    y -= 16

    c.setFont("Helvetica", 11)
    text = execution.feedback_text or "(Sin contenido)"
    text = re.sub(r"<[^>]+>", "", text).replace("\r", "")
    max_width = right - left

    for para in text.split("\n"):
        if not para.strip():
            y -= 10; continue
        for line in _wrap_text(c, para, max_width):
            if y < 2*cm:
                c.showPage(); y = height - 2*cm; c.setFont("Helvetica", 11)
            c.drawString(left, y, line); y -= 14

    c.showPage(); c.save(); buffer.seek(0)
    return buffer
