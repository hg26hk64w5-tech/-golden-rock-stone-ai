from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
import tempfile, shutil, os
from analyzer import analyze_pdf
from cladding import PlanRequest, plan, SYSTEMS, WORKFLOW, FABRICATION_FIELDS

app = FastAPI(title="Golden Rock Stone AI", version="0.2.0")

@app.get('/api/cladding/rules')
def rules():
    return {'systems': SYSTEMS, 'workflow': WORKFLOW, 'fabrication_fields': FABRICATION_FIELDS}

@app.get('/api/project/external-stone')
def external_stone_register():
    path = os.path.join(os.path.dirname(__file__), 'external_stone_project_register.json')
    with open(path, 'r', encoding='utf-8') as f:
        import json
        return json.load(f)

@app.post('/api/cladding/plan')
def cladding_plan(request: PlanRequest):
    return plan(request)

@app.post('/api/project/upload-batch')
async def upload_batch(files: list[UploadFile] = File(...)):
    """Accept a complete drawing package in one operation; files are catalogued, not interpreted as verified dimensions."""
    manifest = []
    for f in files:
        data = await f.read()
        name = f.filename or 'unnamed'
        ext = os.path.splitext(name)[1].lower()
        manifest.append({'file_name': name, 'extension': ext, 'content_type': f.content_type, 'size_bytes': len(data), 'status': 'RECEIVED', 'dimension_status': 'RFI_REQUIRED' if ext in ('.dwg','.dxf') else 'UNVERIFIED'})
    return {'status':'RECEIVED','file_count':len(manifest),'files':manifest,'note':'DWG/DXF files are preserved as reference inputs; written dimensions still require CAD/site verification.'}

@app.post('/api/cladding/export-dxf')
def export_dxf(request: PlanRequest):
    result = plan(request)
    entities = []
    def line(x1,y1,x2,y2,layer):
        entities.extend(['0','LINE','8',layer,'10',str(x1),'20',str(y1),'11',str(x2),'21',str(y2)])
    def text(x,y,value,layer='NOTES',height=25):
        entities.extend(['0','TEXT','8',layer,'10',str(x),'20',str(y),'40',str(height),'1',value])
    for panel in result.get('cutting_list',{}).get('items',[]):
        x,y,w,h=panel['x_mm'],panel['y_mm'],panel['width_mm'],panel['height_mm']
        for a,b,c,d in [(x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)]: line(a,b,c,d,'STONE_PANEL')
        text(x+10,y+h/2,panel['id'],'STONE_LABEL',20)
        if request.system == 'U':
            for q in (0.25,0.75):
                cx=x+w*q; line(cx,y,cx,y+h,'U_CHANNEL'); text(cx+8,y+h-30,'U-CHANNEL 41x41x41','NOTES',16)
    if request.system == 'U': text(0,-70,'U-CHANNEL WALL CLADDING - PRELIMINARY / NOT FOR FABRICATION','TITLE',30)
    dxf='0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n'+'\n'.join(entities)+'\n0\nENDSEC\n0\nEOF\n'
    return PlainTextResponse(dxf, media_type='application/dxf', headers={'Content-Disposition':'attachment; filename=golden-rock-external-wall.dxf'})

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
