from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
import tempfile, shutil, os, json, zipfile, io
import re
from analyzer import analyze_pdf, merge_project_register, PdfReadError
from cladding import PlanRequest, plan, SYSTEMS, WORKFLOW, FABRICATION_FIELDS

app = FastAPI(title="Golden Rock Stone AI", version="1.5.0")

# In-memory cache of the most recent live analysis, so a later GET (e.g. a page
# refresh, or the client simply re-reading the register) sees what was just uploaded
# without re-sending the files. No database is used (see README); this does not
# survive a restart, matching the project's existing "no persistent project storage"
# note -- it only avoids re-analysing on every read within one running session.
_last_register = None
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_EXPANDED_BYTES = 500 * 1024 * 1024
MAX_MEMBER_BYTES = 50 * 1024 * 1024
MAX_ZIP_MEMBERS = 200


@app.get('/api/cladding/rules')
def rules():
    return {'systems': SYSTEMS, 'workflow': WORKFLOW, 'fabrication_fields': FABRICATION_FIELDS}


@app.get('/api/project/external-stone')
def external_stone_register():
    """Return the live register from the most recent upload/analysis, if any;
    otherwise fall back to the static Palm D139 reference register bundled with the
    app (kept only so the workspace is not blank before anything has been uploaded)."""
    if _last_register is not None:
        return _last_register
    path = os.path.join(os.path.dirname(__file__), 'external_stone_project_register.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['status'] = 'STATIC SAMPLE REGISTER (no drawings analysed yet in this session) - ' + data.get('status', '')
    return data


@app.post('/api/cladding/plan')
def cladding_plan(request: PlanRequest):
    return plan(request)


def _write_temp_pdf(data: bytes, original_name: str) -> str:
    """Write PDF bytes to a temp file that KEEPS the original filename, inside a fresh
    temp directory. analyze_pdf()/find_sheet_number() read the sheet number from the
    path's own basename first (this project's filenames reliably encode it, e.g.
    "AR-509.pdf") because that is far more reliable than anything printed on the sheet
    itself -- but that only works if the file on disk is still actually named that. An
    earlier version of this endpoint saved uploads under tempfile's own randomised name
    (e.g. "tmpAbC123.pdf"), which silently defeated the filename shortcut for every
    upload that went through the API (as opposed to a direct analyze_pdf(real_path)
    call in a test/script) and fell back to a weaker in-document heuristic instead.
    Use _cleanup_temp_pdf(tmp_path) to remove the directory this creates."""
    tmp_dir = tempfile.mkdtemp(prefix='grsa_')
    safe_name = os.path.basename(original_name.replace('\\', '/')) or 'upload.pdf'
    safe_name = re.sub(r'[^\w. -]', '_', safe_name)[:180]
    if not safe_name.lower().endswith('.pdf'):
        safe_name += '.pdf'
    tmp_path = os.path.join(tmp_dir, safe_name)
    with open(tmp_path, 'wb') as fh:
        fh.write(data)
    return tmp_path


def _cleanup_temp_pdf(tmp_path: str) -> None:
    shutil.rmtree(os.path.dirname(tmp_path), ignore_errors=True)


def _analyze_one_pdf(data: bytes, name: str, analysis_results: list, analysis_errors: list, original_name: str | None = None) -> dict:
    """Run analyze_pdf on one PDF's raw bytes and return its manifest entry. Shared by
    top-level uploads and PDFs found inside an uploaded ZIP so both paths behave
    identically."""
    entry = {'file_name': name, 'extension': '.pdf', 'size_bytes': len(data)}
    tmp_path = _write_temp_pdf(data, original_name or name)
    try:
        result = analyze_pdf(tmp_path)
        result.file_name = name
        for material in result.materials:
            for evidence in material.evidence:
                evidence.source = name
        analysis_results.append(result)
        entry['status'] = 'ANALYZED'
        entry['sheet_number'] = result.sheet_number
        entry['stone_codes_found'] = [z.material_code for z in result.zones]
    except PdfReadError as error:
        entry['status'] = 'ANALYSIS_FAILED'
        entry['error'] = str(error)
        analysis_errors.append({'file_name': name, 'error': str(error)})
    finally:
        _cleanup_temp_pdf(tmp_path)
    return entry


def _catalog_only_entry(name: str, ext: str, size_bytes: int, content_type: str | None = None) -> dict:
    entry = {'file_name': name, 'extension': ext, 'size_bytes': size_bytes,
              'status': 'RECEIVED (catalogued only - no DWG/CAD geometry reader in this release)',
              'dimension_status': 'RFI_REQUIRED' if ext in ('.dwg', '.dxf') else 'UNVERIFIED'}
    if content_type is not None:
        entry['content_type'] = content_type
    return entry


def _expand_zip(data: bytes, zip_name: str, analysis_results: list, analysis_errors: list) -> list:
    """A project is often shared as one ZIP of the whole drawing package rather than
    individual file picks; previously this endpoint only catalogued the ZIP itself and
    never looked inside it, so every PDF in it was silently skipped. This opens the
    archive (top level only -- a ZIP nested inside this ZIP is still just catalogued,
    not recursively expanded) and analyses every .pdf member the same way a directly
    uploaded PDF would be, so nothing depends on how the client happened to select
    files in their browser."""
    entries = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        entries.append({'file_name': zip_name, 'extension': '.zip', 'size_bytes': len(data),
                         'status': 'ANALYSIS_FAILED', 'error': 'Could not open this ZIP (corrupt or not a ZIP file).'})
        analysis_errors.append({'file_name': zip_name, 'error': 'Could not open this ZIP (corrupt or not a ZIP file).'})
        return entries
    with zf:
        members = [m for m in zf.infolist()
                   if not m.is_dir() and not m.filename.startswith('__MACOSX/')
                   and not os.path.basename(m.filename).startswith('.')]
        if len(members) > MAX_ZIP_MEMBERS or sum(m.file_size for m in members) > MAX_EXPANDED_BYTES or any(m.file_size > MAX_MEMBER_BYTES for m in members):
            error = 'ZIP exceeds limits: 200 members, 50MB per member, 500MB expanded total.'
            analysis_errors.append({'file_name': zip_name, 'error': error})
            return [{'file_name': zip_name, 'extension': '.zip', 'status': 'ANALYSIS_FAILED', 'error': error}]
        if not members:
            entries.append({'file_name': zip_name, 'extension': '.zip', 'size_bytes': len(data),
                             'status': 'RECEIVED (empty or unreadable ZIP - no files found inside)'})
            return entries
        for m in members:
            inner_name = f'{zip_name} → {m.filename}'
            ext = os.path.splitext(m.filename)[1].lower()
            if ext not in ('.pdf', '.zip'):
                entries.append(_catalog_only_entry(inner_name, ext, m.file_size))
                continue
            try:
                with zf.open(m) as member:
                    member_bytes = member.read(MAX_MEMBER_BYTES + 1)
                if len(member_bytes) > MAX_MEMBER_BYTES:
                    raise ValueError('ZIP member exceeds 50MB.')
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, ValueError) as error:
                message = 'Unable to read ZIP member: ' + str(error)
                analysis_errors.append({'file_name': inner_name, 'error': message})
                entries.append({'file_name': inner_name, 'extension': ext, 'status': 'ANALYSIS_FAILED', 'error': message})
                continue
            if ext == '.pdf':
                entries.append(_analyze_one_pdf(member_bytes, inner_name, analysis_results, analysis_errors, original_name=m.filename))
            elif ext == '.zip':
                entries.append({'file_name': inner_name, 'extension': '.zip', 'size_bytes': len(member_bytes),
                                 'status': 'RECEIVED (catalogued only - nested ZIPs are not expanded automatically; upload it separately if it contains drawings)'})
            else:
                entries.append(_catalog_only_entry(inner_name, ext, len(member_bytes)))
    return entries


@app.post('/api/project/upload-batch')
async def upload_batch(files: list[UploadFile] = File(...)):
    """Accept a complete drawing package in one operation. PDFs are actually analysed
    (legend/material codes, candidate dimensions, auto-proposed stone zones), including
    PDFs found inside an uploaded ZIP of the project package; DWG/DXF/image files (and
    any ZIP contents that are not PDFs) are catalogued only, since this release has no
    DWG/CAD geometry reader. The merged, live project register replaces the static
    bundled sample for the remainder of this session."""
    global _last_register
    manifest = []
    analysis_results = []
    analysis_errors = []
    if len(files) > 100:
        raise HTTPException(413, 'Upload at most 100 files per batch.')
    total_bytes = 0
    for f in files:
        data = await f.read(MAX_UPLOAD_BYTES - total_bytes + 1)
        total_bytes += len(data)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Batch exceeds 200MB upload limit.')
        name = f.filename or 'unnamed'
        ext = os.path.splitext(name)[1].lower()
        if ext == '.pdf':
            manifest.append(_analyze_one_pdf(data, name, analysis_results, analysis_errors))
        elif ext == '.zip':
            manifest.extend(_expand_zip(data, name, analysis_results, analysis_errors))
        else:
            manifest.append(_catalog_only_entry(name, ext, len(data), f.content_type))

    register = None
    _last_register = None
    if analysis_results:
        register = merge_project_register(analysis_results, project_name='Stone Works')
        _last_register = register.model_dump()

    return {
        'status': 'RECEIVED',
        'file_count': len(manifest),
        'files': manifest,
        'analysis_errors': analysis_errors,
        'project_register': register,
        'note': 'PDFs, including ZIP members, were analysed for text evidence. Other formats are catalogued only; original uploaded files are not retained. Written dimensions still require CAD/site verification.',
    }


@app.post('/api/cladding/export-dxf')
def export_dxf(request: PlanRequest):
    from drawing_engine import to_dxf
    result = plan(request)
    return PlainTextResponse(to_dxf(result['drawing_package']), media_type='application/dxf', headers={'Content-Disposition':'attachment; filename=golden-rock-review-details.dxf'})

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
    data = await file.read(MAX_MEMBER_BYTES + 1)
    if len(data) > MAX_MEMBER_BYTES:
        raise HTTPException(413, 'PDF exceeds 50MB limit.')
    tmp_path = _write_temp_pdf(data, file.filename or 'drawing.pdf')
    try:
        try:
            result = analyze_pdf(tmp_path)
            result.file_name = file.filename
            for material in result.materials:
                for evidence in material.evidence:
                    evidence.source = file.filename
            return result
        except PdfReadError as error:
            raise HTTPException(400, str(error)) from error
    finally:
        _cleanup_temp_pdf(tmp_path)
