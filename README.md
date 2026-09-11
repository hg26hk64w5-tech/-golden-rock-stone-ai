# Golden Rock Stone AI v0.2

Updated from GitHub `hg26hk64w5-tech/-golden-rock-stone-ai`, main snapshot `7da5b8a`, retrieved 11 September 2026. The existing FastAPI/PDF analyzer is preserved and extended with an external wall planning API and browser workflow.

## Start locally

Python 3.11 or 3.12:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest -v
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. API documentation: `/docs`; health: `/health`.

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

## GitHub / Railway package

The delivery ZIP is flat: `main.py`, `requirements.txt`, `Dockerfile`, `railway.toml`, frontend files and README are directly at archive root. Extract them into the GitHub repository root. Keep the included Railway Dockerfile configuration; it runs Uvicorn on `0.0.0.0` with Railway's `PORT`, falling back to 8000. Health check is `/health`.

No GitHub push or Railway deployment was performed. Python/API tests and local browser checks were performed; a Docker image was not built locally. Run the included tests before deployment. No database or persistent project storage is included; save the review JSON to retain the request and its calculated results.

## Validation

See `TEST_REPORT.md`. Automated coverage includes all four systems, per-channel bracket quantities, missing dimensions, material dependencies, small-strip avoidance, 700mm cap, joints, detail profiles, waterproofing, insulation reference, survey deviation, final-face conflicts, input validation and PDF regression.
