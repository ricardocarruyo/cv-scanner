from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
import os
import markdown
from openai import OpenAI
import openai
import google.generativeai as genai
import langdetect  # Nueva librería para detectar idioma

# Claves API desde variables de entorno
openai.api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV Compatibility Scanner</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-5">
    <h1 class="mb-4 text-center">CV Compatibility Scanner</h1>
    <div class="card p-4 shadow-sm">
        <form method=post enctype=multipart/form-data>
            <div class="mb-3">
                <label class="form-label">Upload your CV (PDF):</label>
                <input type="file" class="form-control" name="cv" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Paste the job description:</label>
                <textarea name="jobdesc" class="form-control" rows="6" required></textarea>
            </div>
            <button type="submit" class="btn btn-primary w-100">Analyze</button>
        </form>
    </div>
    {% if feedback %}
    <div class="card mt-4 p-4 shadow-sm">
        <h3 class="mb-3">AI Feedback</h3>
        <div>{{ feedback|safe }}</div>
    </div>
    {% endif %}
</div>
</body>
</html>
"""

def extract_text_from_pdf(file_stream):
    doc = fitz.open(stream=file_stream.read(), filetype="pdf")
    text = "\n".join([page.get_text() for page in doc])
    return text

def detectar_idioma(texto):
    try:
        idioma = langdetect.detect(texto)
        return "es" if idioma.startswith("es") else "en"
    except:
        return "en"

def analizar_con_openai(cv_text, job_desc):
    idioma = detectar_idioma(cv_text + " " + job_desc)
    idioma_respuesta = "Spanish" if idioma == "es" else "English"

    try:
        client = OpenAI()
        prompt = f"""
You are a recruiter. Compare the following resume with the job description.
Please write the entire feedback in **{idioma_respuesta}**.

Resume:
{cv_text}

Job Description:
{job_desc}

Respond with:
1. A match score (0–100).
2. Key skills or qualifications missing.
3. Suggestions for improving the resume to better fit the role.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    except openai.RateLimitError as e:
        if "insufficient_quota" in str(e):
            return None
        else:
            raise e

def analizar_con_gemini(cv_text, job_desc):
    idioma = detectar_idioma(cv_text + " " + job_desc)
    idioma_respuesta = "Spanish" if idioma == "es" else "English"

    prompt = f"""
You are a recruiter. Compare the following resume with the job description.
Please write the entire feedback in **{idioma_respuesta}**.

Resume:
{cv_text}

Job Description:
{job_desc}

Respond with:
1. A match score (0–100).
2. Key skills or qualifications missing.
3. Suggestions for improving the resume to better fit the role.
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

@app.route('/', methods=['GET', 'POST'])
def scan():
    feedback = None
    if request.method == 'POST':
        cv_file = request.files['cv']
        jobdesc = request.form['jobdesc']

        if cv_file and jobdesc:
            cv_text = extract_text_from_pdf(cv_file)

            # Intentar OpenAI primero
            feedback_text = analizar_con_openai(cv_text, jobdesc)

            # Si no hay feedback, usar Gemini
            if feedback_text is None and gemini_api_key:
                feedback_text = analizar_con_gemini(cv_text, jobdesc)

            # Convertir Markdown a HTML
            if feedback_text:
                feedback = markdown.markdown(feedback_text)

    return render_template_string(HTML_TEMPLATE, feedback=feedback)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
