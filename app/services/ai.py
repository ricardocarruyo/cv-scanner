import re, langdetect, markdown, bleach
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
# Prompt personal y humano
# -------------------------------

def _build_prompt(cv_text: str, job_desc: str, idioma: str, nombre: str | None) -> str:
    """
    Crea un prompt para que el modelo actúe como reclutador + coach, con tono profesional y humano.
    Requisito clave: en la PRIMERA LÍNEA debe escribir SOLO el porcentaje (p. ej., '75%')
    para facilitar la extracción del score y evitar 'Puntuación de coincidencia:'.
    """
    idioma_respuesta = "Spanish" if idioma == "es" else "English"
    # Nombre seguro
    display_name = nombre.strip() if nombre else ("candidato/a" if idioma == "es" else "candidate")

    if idioma == "es":
        instruccion = f"""
Actúa como un reclutador senior y coach de carrera. Analiza el CV de {display_name} en relación con la descripción del puesto.
Responde en **{idioma_respuesta}**, con un tono profesional, humano y constructivo.

REQUISITO IMPORTANTE:
- En la **primera línea**, escribe **solo** el porcentaje de coincidencia como número con '%'. Ejemplo: `75%`. No agregues palabras en esa línea.

Estructura del resto del contenido:
### Análisis para {display_name}
**Puntos fuertes (3–5):**
- …
- …

**Áreas de mejora (3–5):**
- …

**Recomendaciones específicas (bullets accionables):**
- …

**Comentario final (breve y alentador):**
Una línea final motivadora.

Evita repeticiones innecesarias y cuida la claridad.
"""
    else:
        instruccion = f"""
Act as a senior recruiter and career coach. Analyze {display_name}'s resume against the job description.
Reply in **{idioma_respuesta}** with a professional, human and constructive tone.

IMPORTANT REQUIREMENT:
- On the **first line**, write **only** the match percentage as a number with '%'. Example: `75%`. Do not add words on that line.

Structure for the rest:
### Analysis for {display_name}
**Strengths (3–5):**
- …
- …

**Areas to improve (3–5):**
- …

**Specific recommendations (actionable bullets):**
- …

**Final comment (brief and encouraging):**
One short motivational line.

Avoid unnecessary repetition and keep it clear.
"""

    prompt = (
        f"{instruccion.strip()}\n\n"
        f"Resume (CV):\n{cv_text}\n\n"
        f"Job Description:\n{job_desc}\n"
    )
    return prompt

# -------------------------------
# LLMs
# -------------------------------

def analizar_openai(cv_text, job_desc, nombre: str | None = None):
    """
    Devuelve (texto_markdown, error). El markdown inicia con 'NN%' en la primera línea,
    seguido del análisis personal (reclutador + coach).
    """
    idioma = detectar_idioma((cv_text or "") + " " + (job_desc or ""))
    prompt = _build_prompt(cv_text, job_desc, idioma, nombre)

    cli = openai_client()
    if not cli:
        return None, "OpenAI no configurado"

    try:
        resp = cli.responses.create(
            model="gpt-4o",
            input=prompt,
            temperature=0.2,
        )
        return resp.output_text, None
    except Exception as e:
        return None, str(e)

def analizar_gemini(cv_text, job_desc, nombre: str | None = None):
    """
    Devuelve texto markdown con el mismo formato que OpenAI.
    """
    idioma = detectar_idioma((cv_text or "") + " " + (job_desc or ""))
    prompt = _build_prompt(cv_text, job_desc, idioma, nombre)

    g = gemini_client()
    if not g:
        return None
    model = g.GenerativeModel("gemini-1.5-flash")
    out = model.generate_content(prompt)
    return out.text

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
