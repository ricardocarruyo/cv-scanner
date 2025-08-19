# app/i18n.py
STRINGS = {
    "es": {
        # Navbar / generales
        "app.title": "CV Match Scanner",
        "nav.sign_in": "Iniciar sesión",
        "nav.history": "Historial",
        "nav.admin": "Admin",
        "nav.logout": "Salir",
        "nav.template": "Plantilla CV ATS",
        "nav.video": "¿Qué es un ATS?",
        "btn.print": "Imprimir / Guardar PDF",

        # Formulario
        "form.occupation": "Ocupación (opcional):",
        "form.occupation.ph": "Ej.: Analista de Negocio, QA, DevOps",
        "form.upload.label": "Sube tu CV (PDF o DOCX, máx. {max_mb} MB):",
        "form.upload.drop_main": "Arrastra y suelta tu archivo aquí",
        "form.upload.drop_sub": "o haz clic para elegir desde tu computadora",
        "form.upload.help": "Solo PDF/DOCX. Realizamos controles básicos de seguridad.",
        "form.jd.label": "Pega la descripción del puesto:",
        "form.jd.clear": "Limpiar",
        "form.analyze": "Analizar",

        # Lineamientos panel
        "panel.guidelines.title": "Lineamientos para subir tu CV",
        "panel.guidelines.items": "Formato: <strong>PDF o DOCX</strong>;;Idioma: <strong>Español o Inglés</strong>;;Texto legible (no imagen escaneada);;Tamaño máximo: <strong>{max_mb} MB</strong>;;Solo el CV (no adjuntes otros documentos)",
        "panel.guidelines.download": "Descargar Plantilla CV ATS",
        "panel.ats.title": "Recomendaciones ATS",
        "panel.ats.items": "<strong>1–2 páginas</strong> (junior 1 pág., senior hasta 2).;;Tipografías seguras: Arial, Calibri, Helvetica, Verdana.;;<strong>Evita</strong> imágenes, logos, tablas y columnas.;;Usa encabezados simples (H1/H2) y bullets estándar.;;No uses gráficos incrustados ni íconos como texto.",
        "panel.syn.title": "Títulos / Secciones equivalentes aceptadas por ATS",
        "panel.syn.note": "Puedes usar cualquiera de estos nombres; el sistema los reconocerá como equivalentes.",

        # STAR
        "star.title": "Recomendación: usa el formato STAR en tu experiencia",
        "star.help": "El método <strong>STAR</strong> ayuda a redactar logros claros y medibles:",
        "star.s": "<strong>S</strong>ituación: contexto o problema.",
        "star.t": "<strong>T</strong>area: objetivo o responsabilidad.",
        "star.a": "<strong>A</strong>cción: qué hiciste específicamente.",
        "star.r": "<strong>R</strong>esultado: impacto medible (%, tiempos, ahorros, etc.).",

        # Módulo análisis
        "analysis.title": "Análisis de la IA",
        "analysis.donut.jd": "Coincidencia con Job Description",
        "analysis.donut.ats": "Coincidencia con Plantilla CV ATS",
        "analysis.checklist.title": "Checklist ATS detectado",
        "analysis.checklist.images": "Imágenes en el CV",
        "analysis.checklist.tables": "Tablas o columnas",
        "analysis.checklist.fontsafe": "Tipografía segura",
        "yes": "Sí",
        "no": "No",
        "indeterminate": "Indeterminado",
        "lineamientos.title": "Lineamientos y equivalencias ATS",

        # Errores/flash
        "err.login": "Inicia sesión para analizar tu CV.",
        "err.no_file": "No se recibió ningún archivo. Selecciona un PDF o DOCX.",
        "err.no_jd": "Falta la descripción del puesto.",
        "err.bad_ext": "Formato no permitido. Solo PDF o DOCX.",
        "err.empty": "El archivo está vacío o no se pudo leer.",
        "err.too_big": "El archivo supera {max_mb} MB.",
        "err.malicious": "Detectamos contenido potencialmente peligroso en el archivo.",
        "err.analysis": "No pudimos generar el análisis en este momento. Intenta nuevamente.",
        "err.generic": "Ocurrió un error al procesar el análisis. Inténtalo nuevamente.",

        # Nuevas claves análisis (modelos, descarga, guía)
        "ai.title": "Análisis de la IA",
        "ai.model_1": "OpenAI",
        "ai.model_2": "Gemini",
        "ai.download_print": "Versión imprimible",
        "ai.match_jd": "Coincidencia con Job Description",
        "ai.match_ats": "Coincidencia con Plantilla CV ATS",
        "ai.checklist_title": "Checklist ATS detectado",
        "ai.images_in_cv": "Imágenes en el CV",
        "ai.tables_or_columns": "Tablas o columnas",
        "ai.safe_typography": "Tipografía segura",

        # Secciones traducidas
        "sec.profile": "Perfil profesional",
        "sec.experience": "Experiencia laboral",
        "sec.education": "Educación",
        "sec.skills": "Habilidades",
        "sec.languages": "Idiomas",

        # Guía y equivalencias
        "guide.title": "Lineamientos y equivalencias ATS",
        "guide.bullet_format": "Formato: PDF o DOCX (máx. {max_mb} MB)",
        "guide.bullet_avoid": "Evita imágenes, logos, tablas y columnas",
        "guide.bullet_fonts": "Tipografías seguras: Arial, Calibri, Helvetica, Verdana",
        "guide.download_template": "Descargar Plantilla CV ATS",
        "guide.get_template_site": "Descarga la plantilla desde el sitio oficial",
        "guide.sections_equiv_title": "Secciones equivalentes aceptadas",
        "guide.sec_profile_equiv": "Resumen, About me, Extracto",
        "guide.sec_experience_equiv": "Background, Career history",
        "guide.sec_education_equiv": "Academic background, Studies",
        "guide.sec_skills_equiv": "Competencias, Technical skills",
        "guide.sec_languages_equiv": "Idiomas, Languages",

        # STAR
        "guide.star_title": "Formato STAR para logros",
        "guide.star_intro": "El método STAR ayuda a mostrar logros claros y medibles:",
        "guide.star_s": "<strong>S</strong>ituación: contexto o problema",
        "guide.star_t": "<strong>T</strong>area: objetivo o responsabilidad",
        "guide.star_a": "<strong>A</strong>cción: qué hiciste específicamente",
        "guide.star_r": "<strong>R</strong>esultado: impacto medible",
        
        # Comunes
        "common.yes": "Sí",
        "common.no": "No",
        "common.undetermined": "Indeterminado",
    },
    "en": {
        "app.title": "CV Match Scanner",
        "nav.sign_in": "Sign in",
        "nav.history": "History",
        "nav.admin": "Admin",
        "nav.logout": "Log out",
        "nav.template": "ATS CV Template",
        "nav.video": "What is an ATS?",
        "btn.print": "Print / Save as PDF",

        "form.occupation": "Occupation (optional):",
        "form.occupation.ph": "e.g., Business Analyst, QA, DevOps",
        "form.upload.label": "Upload your resume (PDF or DOCX, max {max_mb} MB):",
        "form.upload.drop_main": "Drag & drop your file here",
        "form.upload.drop_sub": "or click to choose from your computer",
        "form.upload.help": "PDF/DOCX only. Basic security checks are performed.",
        "form.jd.label": "Paste the job description:",
        "form.jd.clear": "Clear",
        "form.analyze": "Analyze",

        "panel.guidelines.title": "Guidelines to upload your resume",
        "panel.guidelines.items": "Format: <strong>PDF or DOCX</strong>;;Language: <strong>Spanish or English</strong>;;Readable text (not a scanned image);;Maximum size: <strong>{max_mb} MB</strong>;;Resume only (don’t attach other documents)",
        "panel.guidelines.download": "Download ATS CV Template",
        "panel.ats.title": "ATS Recommendations",
        "panel.ats.items": "<strong>1–2 pages</strong> (junior 1 page, senior up to 2).;;Safe fonts: Arial, Calibri, Helvetica, Verdana.;;<strong>Avoid</strong> images, logos, tables and columns.;;Use simple headers (H1/H2) and standard bullets.;;Do not embed charts or icons as text.",
        "panel.syn.title": "Section titles accepted by most ATS",
        "panel.syn.note": "You can use any of these names; the system will recognize them as equivalent.",

        "star.title": "Tip: use the STAR format in your experience",
        "star.help": "The <strong>STAR</strong> method helps you write clear, measurable achievements:",
        "star.s": "<strong>S</strong>ituation: context or problem.",
        "star.t": "<strong>T</strong>ask: goal or responsibility.",
        "star.a": "<strong>A</strong>ction: what you did specifically.",
        "star.r": "<strong>R</strong>esult: measurable impact (%, time, savings, etc.).",

        "analysis.title": "AI Analysis",
        "analysis.donut.jd": "Match with Job Description",
        "analysis.donut.ats": "Match with ATS CV Template",
        "analysis.checklist.title": "Detected ATS checklist",
        "analysis.checklist.images": "Images in the resume",
        "analysis.checklist.tables": "Tables or columns",
        "analysis.checklist.fontsafe": "Safe typography",
        "yes": "Yes",
        "no": "No",
        "indeterminate": "Indeterminate",
        "lineamientos.title": "Guidelines and ATS equivalences",

        "err.login": "Sign in to analyze your resume.",
        "err.no_file": "No file received. Please select a PDF or DOCX.",
        "err.no_jd": "Job description is missing.",
        "err.bad_ext": "Format not allowed. PDF or DOCX only.",
        "err.empty": "The file is empty or could not be read.",
        "err.too_big": "The file exceeds {max_mb} MB.",
        "err.malicious": "We detected potentially dangerous content in the file.",
        "err.analysis": "We couldn’t generate the analysis right now. Please try again.",
        "err.generic": "An error occurred while processing the analysis. Try again.",

        # New analysis keys
        "ai.title": "AI Analysis",
        "ai.model_1": "OpenAI",
        "ai.model_2": "Gemini",
        "ai.download_print": "Printable version",
        "ai.match_jd": "Match with Job Description",
        "ai.match_ats": "Match with ATS CV Template",
        "ai.checklist_title": "Detected ATS checklist",
        "ai.images_in_cv": "Images in the resume",
        "ai.tables_or_columns": "Tables or columns",
        "ai.safe_typography": "Safe typography",

        # Sections
        "sec.profile": "Professional profile",
        "sec.experience": "Work experience",
        "sec.education": "Education",
        "sec.skills": "Skills",
        "sec.languages": "Languages",

        # Guidelines
        "guide.title": "Guidelines and ATS equivalences",
        "guide.bullet_format": "Format: PDF or DOCX (max {max_mb} MB)",
        "guide.bullet_avoid": "Avoid images, logos, tables and columns",
        "guide.bullet_fonts": "Safe fonts: Arial, Calibri, Helvetica, Verdana",
        "guide.download_template": "Download ATS CV Template",
        "guide.get_template_site": "Get the template from the official site",
        "guide.sections_equiv_title": "Section titles accepted",
        "guide.sec_profile_equiv": "Summary, About me, Extract",
        "guide.sec_experience_equiv": "Background, Career history",
        "guide.sec_education_equiv": "Academic background, Studies",
        "guide.sec_skills_equiv": "Competencies, Technical skills",
        "guide.sec_languages_equiv": "Languages, Idioms",

        # STAR
        "guide.star_title": "STAR format for achievements",
        "guide.star_intro": "The STAR method helps to show clear, measurable achievements:",
        "guide.star_s": "<strong>S</strong>ituation: context or problem",
        "guide.star_t": "<strong>T</strong>ask: goal or responsibility",
        "guide.star_a": "<strong>A</strong>ction: what you did specifically",
        "guide.star_r": "<strong>R</strong>esult: measurable impact",
        
        # Common
        "common.yes": "Yes",
        "common.no": "No",
        "common.undetermined": "Undetermined",

    }
}

def tr(lang: str, key: str, **kwargs) -> str:
    lang = (lang or "es").lower()
    txt = STRINGS.get(lang, {}).get(key, STRINGS["es"].get(key, key))
    return txt.format(**kwargs)
