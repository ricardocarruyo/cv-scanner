from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
import os

# OpenAI
from openai import OpenAI
import openai

# Gemini
import google.generativeai as genai

# Configuración de claves desde variables de entorno
openai.api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<title>CV Compatibility Scanner with AI Fallback</title>
<h2>CV Compatibility Scanner</h2>
<form method=post enctype=multipart/form-data>
  Upload your CV (PDF): <input type=file name=cv><br><br>
  Paste the job description:<br>
  <textarea name=jobdesc rows=10 cols=80></textarea><br><br>
  <input type=submit value=Analyze>
</form>
{% if feedback %}
  <h3>AI Feedback:</h3>
  <pre style="background:#f8f8f8; padding:10px;">{{ feedback }}</pre>
{% endif %}
"""

def extract_text_from_pdf(file_stream):
    doc = fitz.open(stream=file_stream.read(), filetype="pdf")
    text = "\n".join([page.get_text() for page in doc])
    return text

def analizar_con_openai(cv_text, job_desc):
    try:
        client = OpenAI()
        prompt = f"""
You are a recruiter. Compare the following resume with the job description.

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
            return None  # Fuerza cambio a Gemini
        else:
            raise e

def analizar_con_gemini(cv_text, job_desc):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
You are a recruiter. Compare the following resume with the job description.

Resume:
{cv_text}

Job Description:
{job_desc}

Respond with:
1. A match score (0–100).
2. Key skills or qualifications missing.
3. Suggestions for improving the resume to better fit the role.
"""
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
            feedback = analizar_con_openai(cv_text, jobdesc)

            # Si no hay feedback por falta de cuota, usar Gemini
            if feedback is None and gemini_api_key:
                feedback = analizar_con_gemini(cv_text, jobdesc)

    return render_template_string(HTML_TEMPLATE, feedback=feedback)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
