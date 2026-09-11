from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import tempfile, shutil, os
from analyzer import analyze_pdf
from cladding import PlanRequest, plan, SYSTEMS, WORKFLOW, FABRICATION_FIELDS

app = FastAPI(title="Golden Rock Stone AI", version="0.2.0")

@app.get('/api/cladding/rules')
def rules():
    return {'systems': SYSTEMS, 'workflow': WORKFLOW, 'fabrication_fields': FABRICATION_FIELDS}

@app.post('/api/cladding/plan')
def cladding_plan(request: PlanRequest):
    return plan(request)

@app.get('/app.js')
def javascript():
    return FileResponse(os.path.join(os.path.dirname(__file__), 'app.js'), media_type='text/javascript')

@app.get("/health")
def health():
    return {"status": "ok", "service": "Golden Rock Stone AI"}

@app.get("/", response_class=HTMLResponse)
def home():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not (file.filename or '').lower().endswith('.pdf'):
        raise HTTPException(400, 'Upload a PDF file.')
    suffix = os.path.splitext(file.filename or "drawing.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        try:
            result = analyze_pdf(tmp_path)
            result.file_name = file.filename
            for material in result.materials:
                for evidence in material.evidence:
                    evidence.source = file.filename
            return result
        except (ValueError, RuntimeError) as error:
            raise HTTPException(400, 'Unable to read this PDF.') from error
    finally:
        os.unlink(tmp_path)
