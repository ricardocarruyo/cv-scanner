# wsgi.py
from app import create_app

# Gunicorn buscará la variable "app"
app = create_app()

if __name__ == "__main__":
    # Útil para pruebas locales: python wsgi.py
    app.run(host="0.0.0.0", port=10000, debug=True)
