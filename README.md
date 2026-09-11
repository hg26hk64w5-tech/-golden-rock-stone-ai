# Golden Rock Stone AI v0.3

Updated 11 September 2026. This pass replaces the fixed 3-material PDF reader with a
generalised legend-table analyzer and wires it into the "Upload all project files" step,
so the app proposes external stone/marble zones automatically from the actual uploaded
drawings instead of the client typing a single "Zone 1" by hand. See "What changed in
v0.3" below for the full, honest list -- including what this still cannot do.

## Start locally

Python 3.11 or 3.12, **and poppler-utils** (provides the `pdftotext` binary the analyzer
now shells out to -- see "PDF analysis dependency" below):

```sh
# Debian/Ubuntu: sudo apt-get install -y poppler-utils
# macOS: brew install poppler
# Windows: install poppler and put its bin/ on PATH (e.g. via choco install poppler)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest -v
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. API documentation: `/docs`; health: `/health`.

## PDF analysis dependency: poppler-utils

`analyzer.py` no longer uses PyMuPDF (`fitz`). On these AutoCAD-exported architectural
sheets, PyMuPDF's (and pdfplumber's) word/character clustering repeatedly took
10-60+ seconds per page in testing -- too slow for an interactive multi-file upload, and
some pages did not return within a reasonable timeout at all. `pdftotext -bbox` (from
poppler-utils, the same engine behind `pdftotext`/`pdfinfo`) returns identical word-level
bounding boxes from its C++ engine in a few hundred milliseconds. The **Dockerfile now
installs `poppler-utils` via `apt-get`** before the Python dependencies; if you deploy
without Docker (e.g. a buildpack), make sure `pdftotext` is on `PATH` in that environment
too, or PDF analysis will fail with a clear "poppler-utils (pdftotext) is not installed"
error (other endpoints are unaffected).

## Workflow

Scope → Internal/External → Area/Element → Installation System → Material → Panelization → Fixing Details → Shop Drawing → Cutting List → Quantity Takeoff → RFI.

External Wall Cladding is implemented for a rectangular zone. Internal and other elements are selectable but return `RFI_REQUIRED` without applying external panelization to them. Steps are freely navigable; calculation enforces dependencies. Inputs changed after a calculation invalidate its exports. Download the review JSON and preliminary cutting CSV from the interface.

## Applied client rules

* Client selects L-Bracket SS316 50mm, Z-Bracket SS316 70mm, Omega SS316 70mm, or U-Channel 41×41×41mm.
* U cavity = 110mm. **Each U-Channel piece uses 4 large brackets 100×100mm (2 top + 2 bottom) and 4 small reverse brackets 50×100mm between them.** This quantity basis was explicitly confirmed by the client. Three channel pieces therefore give 12 large and 12 small brackets. Missing channel count remains RFI; count is never inferred from panels.
* Pin Ø5mm; embedment 20mm. Other machining/anchor dimensions are never guessed.
* Optional Rock Wool 50mm.
* Cementitious waterproofing, 2 coats × 2mm = 4mm. Product selection: MasterSeal 550, Sika, or approved equivalent. These are client-entered project requirements; no product performance or structural certification is asserted.
* Stone 20mm; panel height at most 700mm.
* No joints by default. Project-requested joints require an explicit positive width. A conflicting width raises an RFI.
* Corner options: 45° mitre; 5mm then 45° Bird’s Mouth. Nominal face sizes do not substitute for approved return/corner cutting geometry.
* Project Detail Profile `project_option2_25mm` supports the supplied reference drawing style: 25mm stone, 5mm horizontal joints, 2mm vertical joints, parapet grooves 20×5mm or 20×10mm, 5mm corner machine cut, and a 10×10mm groove with approved mockup glue. It generates numbered detail records for elevation, window side, wall corner, typical crown and roof balustrade crown. This profile is opt-in and does not replace the general 20mm rule.
* No fixed minimum panel width. Optional material minimum/maximum limits are entered only after material selection. Slab sizes, edge trim and kerf must be entered.

## Panelization and setting-out

Panelization compares the entered slab sizes, retains their orientation, minimizes grid panel count and then favors wider panels. Equalized columns/rows avoid narrow leftover strips. Slab edge trim and saw kerf are conservatively allowed before fitting. All output coordinates retain full numeric precision; the visible table rounds to 3 decimals. This is a balanced grid optimization, not stock-aware slab nesting; slab quantities, mixed sizes, grain matching, openings and waste optimization are not yet implemented.

Survey points must share a datum and outward-positive axis. The largest outward wall coordinate is the closest point to the proposed stone face. Deviation is `max - min`.

`final stone face = closest wall point + 4mm waterproofing + insulation allowance + cavity + 20mm stone`

Insulation allowance is 50mm only when Rock Wool is selected and cavity is measured from the insulation face. If cavity is measured from waterproofing, insulation occupies the cavity and is not added twice. Missing cavity reference creates RFI. U uses 110mm cavity; L/Z/Omega require an explicit cavity because nominal bracket size is not a cavity dimension.

One approved bracket projection is stored for each request's system/zone. It is not varied point-by-point. Approved adjustment capacity must cover wall deviation. A conflicting supplied final-face coordinate creates RFI. Engineering approval remains necessary for anchorage, shimming/adjustment and projection compatibility; the app does not solve structural loads.

## Fabrication and RFI

`POST /api/cladding/plan` accepts the typed `PlanRequest` defined in `cladding.py`; `GET /api/cladding/rules` returns workflow, system options and required fabrication fields. Missing dimensions, conflicting data, unapproved fixing details, unsupported scopes and unknown fabrication fields remain `RFI_REQUIRED`. Invalid numeric/types/unknown request fields return HTTP 422. Use `conflicts` for unresolved drawing evidence or additional missing project dimensions.

Outputs are **PRELIMINARY — NOT FOR FABRICATION**. The app does not issue manufacturing release. Even with all currently modeled fields supplied, output is `REVIEW_REQUIRED` and `fabrication_released` remains false. The shop drawing is a nominal panel elevation, not a complete fixing fabrication drawing or CAD export. Exact channel lengths, hole patterns, corner returns, machining and structural capacity require the approved project detail. The cutting list contains nominal rectangular panel face dimensions only.

Quantity takeoff includes gross wall area, net panel face area, waterproofing area and coat-area, optional insulation area and confirmed U bracket totals. Missing L/Z/Omega bracket counts are unresolved rather than borrowed from U. No pin count is guessed.

Existing `/analyze` extracts PDF text, materials and candidate dimensions. Candidates are not automatically promoted to verified geometry. Scanned/image PDFs still require an OCR workflow outside this release.

## What changed in v0.3

**Problem being fixed:** `analyzer.py` only recognised 3 hardcoded material codes
(`EWMB-01`, `EWST-02`, `EWPT-01`) and returned one flat, unclassified list of numbers per
PDF with no link back to a wall, zone or elevation -- so every project still needed a
human to type "Zone 1" and re-key material data by hand before anything could be
calculated, no matter how much information the drawings actually contained.

**What the analyzer does now:**
* Reads the actual `LEGEND` table on a sheet (the `Code | Symbol | Description |
  Comments` block architects place on these drawings) by locating its header and
  columns from real text positions, instead of a hardcoded code list. Tested against
  the real "AR-509 Roof Floor External Wall Finish Layout" sheet, it recovers **all
  10** legend entries with complete descriptions (aluminium, HPL, paint and stone
  alike), not just the 3 that used to be hardcoded.
* Filters that to natural-stone/marble codes only for the workflow (per your request),
  and emits **one proposed zone per stone code per sheet** -- e.g. this project's
  drawings alone yield `EWMB-01`/`EWST-01`/`EWST-02` (roof parapet wall) and
  `EFST-01`/`EFST-02` (ground/first/roof floor), i.e. more than one zone automatically,
  instead of a single hand-typed "Zone 1".
* Falls back to a narrower inline scanner (a project-specific `E**-##` pattern, plus a
  plain "Travertine/Limestone/Marble/Flagstone" text search) on sheets that have no
  legend table at all -- e.g. the pool and water-feature detail sheets -- so a mention
  is still surfaced instead of silently skipped.
* Reads the sheet number from the uploaded filename first (this project's filenames
  reliably encode it, e.g. "...AR509_Roof_Floor..."), falling back to the drawing's own
  title-block reference, then a frequency count. A revision-cloud note like "TD-02" is
  no longer mistaken for the sheet's own number.
* A new `POST /api/project/upload-batch` behaviour (frontend: the existing "Upload all
  project files" button) actually analyzes every uploaded PDF and returns a merged,
  live `project_register` -- replacing the previously static, hand-authored
  `external_stone_project_register.json` for the rest of the running session.
  `GET /api/project/external-stone` now serves that live register once one exists.

**What is deliberately still `RFI_REQUIRED`, and why:** a proposed zone never carries an
auto-filled width/height. Assigning a specific wall length to a specific material code
needs real CAD geometry or a site survey -- a flattened PDF's text stream has no
reliable link between a decimal number and the wall it dimensions (the same number can
be a length, a level, or something unrelated printed nearby). `candidate_dimensions_m`
lists every plausible number found on that sheet as a hint for the person confirming the
zone, and is explicitly documented as unassigned. This preserves the project's existing
core rule -- "never fabricate a missing dimension" -- rather than quietly guessing.

**Known limitations carried into this version:**
* The legend-table reader is tuned to this drawing set's layout (description lines can
  appear above *and* below the code row, assigned by nearest vertical distance) and to
  sheets that print a `LEGEND` block with `Code`/`Description`/`Comments` headers. A
  differently formatted legend, or one on a scanned/rasterised page, will not be read
  and the sheet falls back to the inline scanner or is left unanalyzed for materials.
* On sheets with no dedicated stone legend (e.g. the ceiling RCP layouts, `AR-523`/
  `AR-524`), a stone code can be detected but its description can still pick up a
  fragment of the title block; it is filtered heuristically, not guaranteed clean.
* `candidate_dimensions_m`/levels are per-sheet, not per-zone -- they are not yet
  geometrically associated with one specific wall run.
* No DWG/DXF geometry reader exists; those files are still catalogued only, as before.

## GitHub / Railway package

The delivery ZIP is flat: `main.py`, `requirements.txt`, `Dockerfile`, `railway.toml`, frontend files and README are directly at archive root. Extract them into the GitHub repository root. Keep the included Railway Dockerfile configuration; it runs Uvicorn on `0.0.0.0` with Railway's `PORT`, falling back to 8000. Health check is `/health`.

No GitHub push or Railway deployment was performed. Python/API tests and local browser checks were performed; a Docker image was not built locally. Run the included tests before deployment. No database or persistent project storage is included; save the review JSON to retain the request and its calculated results.

## Validation

`test_cladding.py` (unchanged business rules: all four systems, per-channel bracket
quantities, missing dimensions, material dependencies, small-strip avoidance, 700mm cap,
joints, detail profiles, waterproofing, insulation reference, survey deviation,
final-face conflicts, input validation) plus a live-register API test. `test_analyzer.py`
is new: it regression-tests the legend-table reader against the real, bundled
`fixtures/AR-509.pdf` sample sheet (all 10 legend codes, correct travertine thickness,
correct zone filtering, sheet-number detection) and the fallback code pattern.

Run `python -m unittest -v` after installing poppler-utils (see above) and
`requirements-dev.txt`. In the sandbox this update was built in, `pip install` and
`apt-get install` were both network-blocked, so `test_cladding.py`'s FastAPI-dependent
tests (the `ApiTests` class) could not be executed there; `cladding.py`'s own logic
tests (already installed system pydantic, no framework needed) and all of
`test_analyzer.py` (9 tests, using pdftotext which was preinstalled) were run and pass.
Please run the full suite once after installing, as the very first step, to confirm the
`ApiTests` class -- unchanged except for the two tests noted below -- still passes in
your environment.

Two existing tests were touched only because they depended on PyMuPDF (`fitz`), which
this version no longer uses anywhere: `test_pdf_regression` now uploads the real bundled
`fixtures/AR-509.pdf` instead of building a one-line PDF with `fitz` at test time (this
also gives it more real coverage than before); one new test,
`test_upload_batch_builds_live_register`, checks the new batch-analysis behaviour.
Nothing about the fabrication rules in `cladding.py` was changed.
