import re, langdetect, markdown, bleach
from uuid import uuid4
from ..extensions import openai_client, gemini_client

# -------------------------------
# Utilidades de idioma y puntaje
# -------------------------------

def detectar_idioma(texto):
    try:
        idioma = langdetect.detect(texto)
        return "es" if idioma.startswith("es") else "en"
    except Exception:
        return "en"

def extraer_score(texto):
    """
    Extrae un score 0–100 de la respuesta textual.
    Soporta formatos como:
      - '75%'
      - '75 / 100'
      - 'score: 75'
    """
    if not texto:
        return None
    pats = [
        r"(?:match\s*score|puntuaci[oó]n.*?(?:0.?100)?)\D{0,20}(\b100\b|\b\d{1,2}\b)",
        r"(?:score|coincidencia)\D{0,20}(\b100\b|\b\d{1,2}\b)",
        r"\b(\d{1,3})\s*/\s*100\b",
        r"\b(\d{1,3})\s*%",
        r"\b(\d{1,2})\b",
    ]
    for p in pats:
        m = re.search(p, texto, flags=re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0 <= val <= 100:
                    return val
            except:
                pass
    return None

# -------------------------------
# Disclaimer (ES / EN)
# -------------------------------

def disclaimer_text(idioma: str) -> str:
    if idioma == "es":
        return (
            "Nota: Este análisis es una guía orientativa para ayudarte a mejorar tu CV. "
            "No representa una verdad absoluta y los resultados pueden variar en cada evaluación. "
            "Como referencia, una coincidencia superior al 70% suele considerarse buena, "
            "pero otros factores también influyen en los procesos de selección."
        )
    # EN
    return (
        "Note: This analysis is a guiding aid to help you improve your resume. "
        "It is not an absolute truth and results may vary across evaluations. "
        "As a reference, a match over 70% is typically considered good, "
        "but other factors also influence hiring decisions."
    )

# -------------------------------
# Prompt builder (neutro / sin nombre)
# -------------------------------

def _build_prompt(cv_text: str, job_desc: str, idioma: str, nombre: str | None) -> str:
    """
    Prompt mejorado:
    - Actúa como reclutador experto, coach de carrera y evaluador ATS.
    - Compara CV vs Job Description y CV vs filtros ATS.
    - Devuelve análisis en formato FODA.
    - Sin nombres propios ni encabezados personalizados.
    - Primera línea: solo el porcentaje (ej: '75%').
    """

    idioma_respuesta = "Spanish" if idioma == "es" else "English"
    candidato = "candidato" if idioma == "es" else "candidate"

    if idioma == "es":
        instruccion = f"""
Eres un reclutador experto, coach de carrera y evaluador ATS. 
Analiza el CV del {candidato} comparándolo tanto con la descripción del puesto como con los filtros de sistemas ATS.
Responde en **{idioma_respuesta}** con un tono profesional, humano y constructivo. 
Ignora cualquier conversación previa, memoria o contexto externo. 
Basate estricta y exclusivamente en el CV y la Descripción del Puesto a continuación.

REQUISITO IMPORTANTE:
- En la **primera línea**, escribe **solo** el porcentaje de coincidencia como número con '%'. Ejemplo: `75%`. No agregues palabras en esa línea.

El resto del análisis debe estar estructurado como un **FODA**:

**Fortalezas:**
incluye de 3 a 5 fortalezas que destaquen las habilidades, experiencias o logros más relevantes del candidato, y señala fortalezas del cv frente a los filtros ATS.
- …

**Oportunidades:**
incluye de 3 a 5 Oportunidades sobre las habilidades, experiencias o logros del candidato, y señala oportunidades del cv frente a los filtros ATS.
- …

**Debilidades:**
incluye de 3 a 5 Debilidades sobre las habilidades, experiencias o logros del candidato, y señala debilidades del cv frente a los filtros ATS.
- …

**Amenazas:**
incluye de 3 a 5 Amenazas sobre las habilidades, experiencias o logros del candidato, y señala Amenazas del cv frente a los filtros ATS.
- …

**Comentario final:**
Una línea motivadora breve y clara.

Evita repeticiones innecesarias y mantén un estilo conciso y profesional.
"""
    else:
        instruccion = f"""
You are an expert recruiter, career coach, and ATS evaluator. 
Analyze the {candidato}'s resume by comparing it both against the job description and against ATS filters.
Reply in **{idioma_respuesta}** with a professional, human, and constructive tone.
Ignore any previous conversation, memory or external context.
Base your answer strictly and exclusively on the Resume and Job Description below.

IMPORTANT REQUIREMENT:
- On the **first line**, write **only** the match percentage as a number with '%'. Example: `75%`. Do not add words on that line.

The rest of the analysis must follow a **SWOT** structure:

**Strengths:**
Include 3 to 5 strengths that highlight the candidate’s most relevant skills, experiences, or achievements, and point out strong aspects of the resume against ATS filters.
- …

**Opportunities:**
Include 3 to 5 opportunities regarding the candidate’s skills, experiences, or achievements, and highlight opportunities in the resume compared to ATS filters.
- …

**Weaknesses:**
Include 3 to 5 weaknesses regarding the candidate’s skills, experiences, or achievements, and highlight weaknesses in the resume compared to ATS filters.
- …

**Threats:**
Include 3 to 5 threats regarding the candidate’s skills, experiences, or achievements, and point out threats in the resume against ATS filters.
- …

**Final comment:**
One short motivational line.

Avoid unnecessary repetition and keep it clear, concise, and professional.
"""

    prompt = (
        f"{instruccion.strip()}\n\n"
        f"Resume (CV):\n{cv_text}\n\n"
        f"Job Description:\n{job_desc}\n"
    )
    return prompt


# -------------------------------
# LLMs (stateless por request)
# -------------------------------

def analizar_openai(cv_text, job_desc, nombre: str | None = None):
    """
    Devuelve (texto_markdown, error). El markdown inicia con 'NN%' en la primera línea.
    Stateless: sin threads compartidos ni historial previo.
    """
    idioma = detectar_idioma((cv_text or "") + " " + (job_desc or ""))
    prompt = _build_prompt(cv_text, job_desc, idioma, nombre=None)  # forzamos neutro

    cli = openai_client()
    if not cli:
        return None, "OpenAI no configurado"

    try:
        # Cada request es independiente; no pasamos thread_id ni history
        resp = cli.responses.create(
            model="gpt-4o",
            input=prompt,
            temperature=0.2,
            # Cabecera opcional para evitar caches de gateway (si tu SDK la soporta)
            extra_headers={"x-nonce": str(uuid4())}
        )
        return getattr(resp, "output_text", None), None
    except Exception as e:
        return None, str(e)

def analizar_gemini(cv_text, job_desc, nombre: str | None = None):
    """
    Devuelve texto markdown con el mismo formato que OpenAI.
    Stateless: no reusamos chat/historial entre llamadas.
    """
    idioma = detectar_idioma((cv_text or "") + " " + (job_desc or ""))
    prompt = _build_prompt(cv_text, job_desc, idioma, nombre=None)  # forzamos neutro

    try:
        g = gemini_client()
        if not g:
            return None
        model = g.GenerativeModel("gemini-1.5-flash")
        out = model.generate_content(prompt)
        return getattr(out, "text", None)
    except Exception:
        return None

# -------------------------------
# Sanitizado a HTML seguro
# -------------------------------

def sanitize_markdown(md_text):
    allowed_tags = [
        "p","ul","ol","li","strong","em","b","i","br","hr","blockquote","code","pre",
        "h1","h2","h3","h4","h5","h6","a","table","thead","tbody","tr","th","td"
    ]
    allowed_attrs = {"a": ["href","title","rel","target"]}
    raw_html = markdown.markdown(md_text or "", extensions=["nl2br"])
    return bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs, strip=True)
