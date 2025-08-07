from flask import Flask, request, render_template_string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import fitz  # PyMuPDF
import openai
import os

from openai import OpenAI

client = OpenAI()

# Cargar API Key desde variable de entorno
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<title>CV Compatibility Scanner with AI</title>
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

def analizar_con_ia(cv_text, job_desc):
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
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

@app.route('/', methods=['GET', 'POST'])
def scan():
    feedback = None
    if request.method == 'POST':
        cv_file = request.files['cv']
        jobdesc = request.form['jobdesc']

        if cv_file and jobdesc:
            cv_text = extract_text_from_pdf(cv_file)
            feedback = analizar_con_ia(cv_text, jobdesc)

    return render_template_string(HTML_TEMPLATE, feedback=feedback)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
