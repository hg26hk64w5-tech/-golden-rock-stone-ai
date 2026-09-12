# Golden Rock Stone AI v1.5

Merged release: v1.3 drawing/white-interface work plus the supplied developer v0.3.1 upload/analyzer fixes (this was v1.4), plus a v1.5 review pass that extends the same explicit-geometry drawing approach from the U-Channel system to the L-Bracket/Z-Bracket/Omega systems. Prepared for manual GitHub upload; not deployed.

## What changed in v1.5 (this review)

- L-Bracket/Z-Bracket/Omega systems previously only produced a generic "confirm bracket quantity and arrangement" RFI on the S02/S03 sheets, with no geometry at all — every other installation system was silently left out of the drawing package. S02 now draws an actual bracket setting-out for these systems, and S03 (the build-up section) is now generated for any selected system instead of only U.
- 4-fixing arrangements (Z-Bracket, Omega, or L-Bracket set to 4) place one bracket at each stone panel corner using the fixing top/bottom/side offsets already confirmed in Fixing Details — no new input is required, the sheet only visualises what was already approved.
- 3-fixing arrangements (L-Bracket) drop one corner, and which side keeps the pair of brackets is a real engineering choice with no safe default — it is never assumed. A new "3-point arrangement" field states it explicitly, exactly like channel_layout never inferring channel positions.
- The build-up section's cavity figure now reflects the actual surveyed cavity for L/Z/Omega instead of the U-Channel system's fixed 110mm; it is withheld (not defaulted to 110) until the cavity and reference face are confirmed.
- `drawing_package` now also reports `brackets` and `bracket_quantities`, alongside the existing `channels`/`channel_quantities`, and the exported DXF carries the new bracket geometry on its own `GR_BRACKET` layer.
- 10 new tests cover both the 4-point and 3-point cases, the missing-input RFI paths, and the corrected cavity figure; all 12 original drawing-engine tests and the full previously-passing suite are re-verified unchanged (see Verification).

## What changed (v1.4 merge)

- White interface with dark text, plus separate sheet selection.
- Optional wall-first module: client-selectable preferred stone width (initial suggestion 800–1000mm), optional column count, and explicit channel edge offset. Wall length is always the supplied length; 4m is only a test example.
- Two channel centre lines per horizontal stone bay, from the corner to the stated end boundary. Slab usable size, kerf, trim and 700mm panel-height limit remain enforced. No fixed minimum width when the module is disabled.
- Separate stone elevation, U-channel setting-out sheet, and enlarged schematic waterproofing/insulation/stone section from a shared geometry model used by SVG, DXF and the AutoCAD bridge.
- Channel base, 2800mm length, 41mm profile bounds and four large/four small bracket levels validated. Missing/invalid levels withhold bracket symbols. Positions are not a structural design.
- Corrected final stone face to use selected thickness; fixed the erroneous conflict for the 30mm profile.
- English review notice states that compliance requires verification and is not certified.

## Run and test

Requires Python 3.11/3.12 and Poppler (`pdftotext`) on PATH. Dockerfile installs poppler-utils for Railway. For local Windows testing, install a Poppler build separately and add its bin directory to PATH. The bundled project fixture is included so no tests are skipped.

```text
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m unittest discover -p "test_*.py"
python -m uvicorn main:app --host 127.0.0.1 --port 8133
```

Open http://127.0.0.1:8133 on the same computer. Railway uses the existing Dockerfile/railway.toml. The web ZIP contains source files at its root: unpack and upload the files, not the ZIP itself. The AutoCAD bridge is supplied separately; update the backend before using GRDETAILS.

## Workflow

Enter the verified width and height of one solid wall segment, choose the system/material/slab sizes, then enable the wall module under Panelization. For U-Channel: enter the approved channel centre-line offset from the stone edge, and use Fixing Details for channel base/bracket levels. For L-Bracket/Z-Bracket/Omega: enter the fixing top/bottom/side offsets in Fixing Details as usual; if 3 fixings per piece is selected, also state the 3-point arrangement (which side takes the pair of brackets) since that has no default. Calculate, then choose the desired sheet in Shop Drawing. DXF contains all sheets on separate layers. A door/window end boundary identifies the stop only; regions above/below the opening require separate zones.

## Explicit limits

- This is not a complete project shop-drawing package or an approved structural design.
- Window/door heads, jambs, sills, thresholds, anchor/rail interfaces and corner fabrication sections are not generated as construction-ready details. Missing geometry remains RFI_REQUIRED.
- The 2800mm channel must fit the zone. No automatic cutting, splice or extension is inferred for shorter/taller walls.
- Two continuous channel lines per horizontal bay can serve several stone rows. This differs from the earlier request for two separate 2.8m pieces per individual stone. An RFI records this unresolved stock/continuity basis. Drawn channel quantities are separately reported under drawing_package.channel_quantities and are preliminary.
- L/Z/Omega bracket positions follow the confirmed fixing offsets, not a structural design; loads, bracket size/gauge, anchor capacity, substrate and edge distances still require engineering verification, same as the channel system. Drawn bracket quantities are separately reported under drawing_package.bracket_quantities and are preliminary.
- Bracket coordinates, substrate, capacity, loads, fire and waterproofing compatibility still require engineering verification. No fabrication release is issued.
- PDFs, including those inside a ZIP, are analysed for text evidence. DWG/DXF/images and nested ZIPs are catalogued only, not interpreted as verified wall geometry. Original uploads are not retained. The live PDF register is process-memory only, not durable or isolated project storage.
- The legacy 25mm project profile still carries its explicit project-specific joint/groove requirements. Do not copy those into a different project without confirmation.

## Merged upload fixes

- Preserves the original PDF basename for correct sheet identification, including Windows paths and ZIP member names.
- Reads PDF members of a ZIP; nested ZIPs remain catalogued only. Does not extract archive paths into the project filesystem.
- Handles corrupt/unreadable members and rejects oversized archives before reading members. Limits: 100 input files / 200MB per batch; ZIP 200 members / 50MB per member / 500MB expanded total; single PDF 50MB.
- Keeps the complete archive/member path in evidence while using only the PDF basename for sheet detection.
- Clears the prior in-memory register when a new batch has no valid analysis, avoiding a stale project appearing as the new result.
- Preserves drawing_engine.py, wall_module, explicit channel layout, variable wall widths, thickness setting-out correction, RFI logic, SVG sheet selection and DXF export.

## Verification

61 tests passed, zero skipped, using the actual supplied fixtures/AR-509.pdf and real FastAPI TestClient (see test-results.txt; this is the v1.4 merge run, reproduced independently by a second review pass using direct calls into cladding.py/drawing_engine.py against the same fixture and assertions, since a real FastAPI install was unavailable in that review environment). JavaScript syntax passed. White interface and module inputs checked in a local browser. Tests include PDF/ZIP processing, correct sheet numbering, natural-stone filtering (ECLM-01 is not a proposed stone zone), archive failures/limits, variable wall widths, separate channel layers, and 30mm survey setting-out.

v1.5 adds 10 tests for the new L/Z/Omega bracket setting-out (4-point corner placement, 3-point arrangement with no default, missing-input RFIs, and the corrected non-U cavity figure) in test_drawing_engine.py, bringing the suite to 71 tests. All were run and pass; the original 61 were re-run unchanged to confirm no regression.

Docker/Railway deployment was not run locally (Docker is unavailable). AutoCAD Bridge v1.3 is a separate package from ChatGPT, out of scope for this review (not supplied, not examined here); per its own status report its GRDETAILS command still requires a live AutoCAD check before relying on it. The DXF export built into this app (Download AutoCAD DXF) is the verified way to get drawings into AutoCAD today. This merge does not complete project-specific opening or anchor sections.

## GitHub upload

Extract Golden-Rock-v1.4-GitHub.zip. Upload the contents directly into the repository root, including drawing_engine.py and the fixtures folder; there is no extra enclosing application folder in the archive. Replace same-named application files. Do not upload the ZIP as the application. Dockerfile/railway.toml retain the existing Railway PORT and /health behavior. This update does not publish anything automatically from this workspace; your existing GitHub-to-Railway integration may deploy after you commit the upload.
