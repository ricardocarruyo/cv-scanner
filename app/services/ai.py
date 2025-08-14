import re, langdetect, markdown, bleach
from ..extensions import openai_client, gemini_client

def detectar_idioma(texto):
    try:
        idioma = langdetect.detect(texto)
        return "es" if idioma.startswith("es") else "en"
    except Exception:
        return "en"

def extraer_score(texto):
    if not texto: return None
    pats = [
        r"(?:match\s*score|puntuaci[oó]n.*?(?:0.?100)?)\D{0,20}(\b100\b|\b\d{1,2}\b)",
        r"(?:score|coincidencia)\D{0,20}(\b100\b|\b\d{1,2}\b)",
        r"\b(\d{1,3})\s*/\s*100\b",
        r"\b(\d{1,3})\s*%",
        r"\b(\d{1,2})\b"
    ]
    for p in pats:
        m = re.search(p, texto, flags=re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0 <= val <= 100: return val
            except: pass

    return None

PROMPT_TEMPLATE = """
You are a recruiter and career coach. Your task is to analyze the following resume and job description in a professional, human, and personal tone. Address the candidate by their name, highlight strengths and areas for improvement, and provide constructive feedback as both a recruiter and a coach. Be empathetic and encouraging, but also honest and direct. Do not include a line that says 'Puntuación de coincidencia:'.

Respond with:
1. A match score (0–100) (just the number, not a label).
2. Key strengths and positive aspects of the resume.
3. Skills or qualifications missing or needing improvement.
4. Suggestions for improving the resume to better fit the role.
5. A professional disclaimer: "This analysis is intended as guidance to help improve your CV. Results may vary with each analysis and are not absolute truths. A match score above 70% is generally considered good, but always adapt your CV to each opportunity."
"""
PROMPT_TEMPLATE = """You are a recruiter... Respond with:
1. A match score (0–100).
2. Key skills or qualifications missing.
3. Suggestions for improving the resume to better fit the role.
"""

def analizar_openai(cv_text, job_desc):
    idioma = detectar_idioma(cv_text + " " + job_desc)
    idioma_respuesta = "Spanish" if idioma == "es" else "English"
    # Intentar extraer el nombre de la persona del CV (heurística simple)
    nombre_match = re.search(r"(?i)nombre[:\s]*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)", cv_text)
    nombre = nombre_match.group(1).strip() if nombre_match else "el candidato"
    prompt = f"{PROMPT_TEMPLATE}\nPlease write the entire feedback in **{idioma_respuesta}**. Address the candidate as '{nombre}'.\n\nResume:\n{cv_text}\n\nJob Description:\n{job_desc}\n"
    cli = openai_client()
    if not cli: return None, "OpenAI no configurado"
    try:
        resp = cli.responses.create(model="gpt-4o", input=prompt, temperature=0.2)
        return resp.output_text, None
    except Exception as e:
        return None, str(e)

def analizar_gemini(cv_text, job_desc):
    idioma = detectar_idioma(cv_text + " " + job_desc)
    idioma_respuesta = "Spanish" if idioma == "es" else "English"
    nombre_match = re.search(r"(?i)nombre[:\s]*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)", cv_text)
    nombre = nombre_match.group(1).strip() if nombre_match else "el candidato"
    prompt = f"{PROMPT_TEMPLATE}\nPlease write the entire feedback in **{idioma_respuesta}**. Address the candidate as '{nombre}'.\n\nResume:\n{cv_text}\n\nJob Description:\n{job_desc}\n"
    g = gemini_client()
    if not g: return None
    model = g.GenerativeModel("gemini-1.5-flash")
    out = model.generate_content(prompt)
    return out.text

def sanitize_markdown(md_text):
    allowed_tags = [
        "p","ul","ol","li","strong","em","b","i","br","hr","blockquote","code","pre",
        "h1","h2","h3","h4","h5","h6","a","table","thead","tbody","tr","th","td"
    ]
    allowed_attrs = {"a": ["href","title","rel","target"]}
    raw_html = markdown.markdown(md_text or "", extensions=["nl2br"])
    return bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs, strip=True)
