from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
import tempfile, shutil, os
from analyzer import analyze_pdf

app = FastAPI(title="Golden Rock Stone AI", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "Golden Rock Stone AI"}

@app.get("/", response_class=HTMLResponse)
def home():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "drawing.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        return analyze_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)
