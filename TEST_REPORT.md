# Local validation — 11 September 2026

Source: GitHub main snapshot `7da5b8a`. Updated application v0.2.

* Automated suite: **29 tests passed** on Windows / Python 3.11.3, using the project's pinned FastAPI, Pydantic and PyMuPDF dependencies. Full output: `test-results.txt`.
* JavaScript syntax: `node --check app.js` passed (Node 24.19.0).
* Live local server: Uvicorn on 127.0.0.1:8765. Frontend, JavaScript, rules and plan endpoints loaded successfully.
* Browser workflow: verified area entry → U system selection → material/slabs → survey/fixing details → calculation → shop drawing → cutting list → quantity takeoff.
* Browser example: 3200 × 2100mm wall, 2500 × 1400mm slab, 3mm kerf, 10mm trim, 3 U-Channel pieces. Result: 6 panels of 1600 × 700 × 20mm; 6.72m² stone; 12 large + 12 small brackets. Survey offsets -10/0/8mm gave 18mm deviation and final face 142mm using waterproofing-face cavity reference.
* CSV and review JSON downloaded through the browser and verified as local files. CSV contains six panel rows and preliminary status.
* Changing material input disabled export and invalidated the old calculated results.
* Project Option 2 profile verified: 25mm stone, 5mm horizontal joints, 2mm vertical joints, 20×5/20×10mm parapet groove choices, 5mm corner cut, and 10×10mm groove; missing profile data remains RFI_REQUIRED. Detail records are numbered for elevation, window side, wall corner, typical crown and roof balustrade crown.
* Shop drawing visually inspected at desktop viewport; panel grid rendered correctly. A dedicated mobile-device run was not performed.
* Flat ZIP verified for integrity and root-level application files; no virtual environment, source archive, cache or credentials included.

No GitHub push, Railway deployment or local Docker image build was performed. These tests verify software behavior, not engineering certification. All shop drawing/cutting outputs remain preliminary and fabrication release is disabled.
