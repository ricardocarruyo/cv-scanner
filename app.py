from flask import Flask, request, render_template_string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import fitz  # PyMuPDF

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<title>CV Scanner</title>
<h2>CV Compatibility Scanner</h2>
<form method=post enctype=multipart/form-data>
  Upload your CV (PDF): <input type=file name=cv><br><br>
  Paste the job description:<br>
  <textarea name=jobdesc rows=10 cols=80></textarea><br><br>
  <input type=submit value=Analyze>
</form>
{% if score %}
  <h3>Match Score: {{ score }}%</h3>
{% endif %}
"""

def extract_text_from_pdf(file_stream):
    doc = fitz.open(stream=file_stream.read(), filetype="pdf")
    text = "\n".join([page.get_text() for page in doc])
    return text

@app.route('/', methods=['GET', 'POST'])
def scan():
    score = None
    if request.method == 'POST':
        cv_file = request.files['cv']
        jobdesc = request.form['jobdesc']

        if cv_file and jobdesc:
            cv_text = extract_text_from_pdf(cv_file)
            texts = [cv_text, jobdesc]

            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(texts)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            score = round(similarity * 100, 2)

    return render_template_string(HTML_TEMPLATE, score=score)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
