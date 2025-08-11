import re

ALLOWED_EXTS = {"pdf", "docx"}

SUSPICIOUS_PATTERNS = [
    r"<script\b", r"</script>", r"<iframe\b", r"onerror\s*=", r"onload\s*=",
    r"document\.cookie", r"eval\s*\(", r"fetch\s*\(", r"xmlhttprequest",
    r"import\s+os", r"subprocess\.Popen", r"socket\.", r"<?php", r"bash -c",
    r"powershell", r"base64,", r"rm -rf /"
]

def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename: return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTS

def looks_suspicious(text: str) -> bool:
    for pat in SUSPICIOUS_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return True
    return False
