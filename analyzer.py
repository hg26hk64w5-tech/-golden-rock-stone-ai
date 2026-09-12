"""Drawing analysis engine. Millimetres/metres as noted; never fabricate a missing dimension.

v0.3: replaces the fixed 3-code lookup with a generalised legend-table reader plus an
inline fallback scanner, and tags every detected material with the sheet/zone it came
from so the client can build more than one zone automatically instead of typing "Zone 1"
by hand.

Uses the `pdftotext` command from poppler-utils (via -bbox, which reports each word's
bounding box) instead of a Python PDF library. On these AutoCAD-exported architectural
sheets, PyMuPDF/pdfplumber's word-and-character clustering can take 10-60+ seconds per
page (heavy vector/hatch content), which is too slow for an interactive multi-file
upload; `pdftotext -bbox` returns the same word positions from poppler's C++ engine in a
few hundred milliseconds. Requires poppler-utils to be installed in the runtime image
(see Dockerfile).
"""
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from models import Material, Evidence, AnalysisResult, ZoneCandidate

# A project legend code looks like "EWMB-01", "EFST-02", "ECST-01" etc: 2-5 letters,
# a hyphen, 2 digits. Drawings render this as three separate text runs ("EWMB", "-", "01"),
# so detection happens on reconstructed lines, not on isolated words.
CODE_RE = re.compile(r"\b([A-Z]{2,6})\s*-\s*(\d{2,3})\b")
# The fallback scanner has no table structure to validate against, so it is restricted to
# this project's actual external-element coding convention (E + category + letters, e.g.
# EWMB/EWST/EFST/ECST) rather than the broad pattern above, which would otherwise also
# match drawing/revision references such as "AR-509" or "TD-02" on a sheet with no legend.
FALLBACK_CODE_RE = re.compile(r"\bE[A-Z]{1,4}-\d{2}\b")

LEVEL_RE = re.compile(r"(?:FFL|SSL|T\.?O\.?P\.?|RL)\s*[+=]?\s*-?\d+(?:\.\d+)?", re.I)
DIM_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.\d{1,3})(?![\d.])")
SHEET_RE = re.compile(r"\b([A-Z]{1,3}-\d{2,4})\b")

LEGEND_HEADER_WORDS = {"code", "description"}


class PdfReadError(RuntimeError):
    pass


def _run_pdftotext_bbox(path: str):
    try:
        result = subprocess.run(
            ["pdftotext", "-bbox", path, "-"],
            capture_output=True, timeout=30,
        )
    except FileNotFoundError as e:
        raise PdfReadError("poppler-utils (pdftotext) is not installed in this environment.") from e
    except subprocess.TimeoutExpired as e:
        raise PdfReadError("Timed out reading this PDF (30s).") from e
    if result.returncode != 0:
        raise PdfReadError(f"pdftotext failed: {result.stderr.decode(errors='replace')[:300]}")
    return result.stdout


def extract_pdf_words(path: str):
    """Return list of (page_no, full_text, words) per page. Each word dict has keys
    text/x0/x1/top/bottom, matching the shape the rest of this module expects."""
    xml_bytes = _run_pdftotext_bbox(path)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise PdfReadError(f"Could not parse pdftotext output: {e}") from e
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    pages = []
    for page_no, page_el in enumerate(root.iter(f"{ns}page"), start=1):
        words = []
        for w in page_el.iter(f"{ns}word"):
            words.append({
                "text": (w.text or ""),
                "x0": float(w.get("xMin", 0)), "x1": float(w.get("xMax", 0)),
                "top": float(w.get("yMin", 0)), "bottom": float(w.get("yMax", 0)),
            })
        text = " ".join(w["text"] for w in words)
        pages.append((page_no, text, words))
    return pages


def _group_lines(words, tol=3):
    """Group word dicts into visual lines by rounding their top coordinate."""
    lines = {}
    for w in words:
        key = round(w["top"] / tol) * tol
        lines.setdefault(key, []).append(w)
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in sorted(lines.items())]


def _line_text(line):
    return " ".join(w["text"] for w in line)


DRAWING_NUMBER_RE = re.compile(r"\b[A-Z0-9]{1,4}-[A-Z]?\d{2,4}-(?:IFC|DD|TD)-([A-Z]{1,3}-\d{2,4})\b", re.I)


def find_sheet_number(pages, file_name: str) -> str:
    """The drawing number's position in the page's own text stream is not reliable
    across sheets (which one comes "last" depends on how each sheet happened to be
    plotted), and a raw frequency count can be beaten by an unrelated revision-cloud
    note such as "TD-02". Uploaded filenames for this project reliably encode the real
    sheet ("...AR509_Roof_Floor..."), so prefer that; then a specific project drawing-
    number pattern ("B8-D139-IFC-AR-509"); only then fall back to a bare frequency count."""
    stem = Path(file_name).stem
    m = re.search(r"\b(AR|EFST|ECST)-?\d{2,4}\b", stem, re.I)
    if m:
        num = re.search(r"\d{2,4}", m.group(0)).group(0)
        letters = re.match(r"[A-Za-z]+", m.group(0)).group(0).upper()
        return f"{letters}-{num}"
    all_text = "\n".join(t for _, t, _ in pages)
    m = DRAWING_NUMBER_RE.search(all_text)
    if m:
        return m.group(1).upper()
    matches = list(SHEET_RE.finditer(all_text))
    if matches:
        counts = {}
        for mm in matches:
            counts[mm.group(1)] = counts.get(mm.group(1), 0) + 1
        return max(counts, key=counts.get)
    return stem


def _find_legend_columns(words):
    """Locate the Code/Description/Comments header row of a LEGEND table, if present."""
    header_words = [w for w in words if w["text"].strip(":").lower() in ("code", "description", "comments", "symbol")]
    by_row = {}
    for w in header_words:
        key = round(w["top"] / 4) * 4
        by_row.setdefault(key, set()).add(w["text"].strip(":").lower())
    header_row_top = None
    for key, present in by_row.items():
        if LEGEND_HEADER_WORDS <= present:
            header_row_top = key
            break
    if header_row_top is None:
        return None
    cols = {w["text"].strip(":").lower(): w for w in words if round(w["top"] / 4) * 4 == header_row_top}
    code_x0 = cols["code"]["x0"] - 4
    desc_x0 = cols["description"]["x0"] - 4
    comments_x0 = cols["comments"]["x0"] - 4 if "comments" in cols else None
    return {"header_top": header_row_top, "code_x0": code_x0, "desc_x0": desc_x0, "comments_x0": comments_x0}


def _parse_legend_table(words, page_no, source_name):
    """Read a LEGEND table's Code/Description columns into Material entries.

    This template centres a code between its own description lines rather than always
    printing the description below the code (a description line can appear above the
    code row, below it, or both), so lines are not attached sequentially to "whichever
    entry is currently open". Instead every non-code description line is assigned to
    whichever code line on the sheet is vertically nearest to it, and same-row text
    (when a code and its description share one line) is captured directly.
    """
    layout = _find_legend_columns(words)
    if layout is None:
        return []
    desc_right_bound = layout["comments_x0"] if layout["comments_x0"] else layout["desc_x0"] + 500
    table_words = [w for w in words if w["top"] > layout["header_top"] + 4 and layout["code_x0"] - 20 <= w["x0"] < desc_right_bound]
    lines = _group_lines(table_words, tol=4)

    code_lines = []  # [top, code, [same_row_desc_str_or_(top,text)_tuples]]
    other_lines = []  # (top, text)
    for line in lines:
        text = _line_text(line)
        m = CODE_RE.search(text)
        code_word = next((w for w in line if layout["code_x0"] - 15 <= w["x0"] <= layout["desc_x0"]), None)
        top = line[0]["top"]
        if m and code_word:
            same_row_desc = " ".join(w["text"] for w in line if w["x0"] >= layout["desc_x0"])
            code_lines.append([top, f"{m.group(1)}-{m.group(2)}", [same_row_desc] if same_row_desc else []])
        else:
            desc_words = [w["text"] for w in line if w["x0"] >= layout["desc_x0"] - 5]
            if desc_words:
                other_lines.append((top, " ".join(desc_words)))

    if not code_lines:
        return []

    for top, text in other_lines:
        nearest = min(code_lines, key=lambda c: abs(c[0] - top))
        nearest[2].append((top, text))

    # A title-block info box (client/consultant/scale/copyright) can sit close enough to
    # the last legend rows that the nearest-line heuristic above pulls a line from it in
    # by mistake; such lines are dropped rather than joined into a material description.
    TITLEBLOCK_NOISE_RE = re.compile(
        r"\bCLIENT\s*:|\bCONSULTANT\s*:|\bARCHITECT\s*:|\bDRAWING\s+(N\.?|DESCRIPTION\s*:)|"
        r"\bSCALE\s*:|\bCOPYRIGHT\b|\bISSUE\s+FOR\b|\bSTAGE\s*:|\bSH\.\s*SIZE\s*:|\bPROJECT\s*:",
        re.I,
    )

    entries = []
    for top, code, desc_parts in code_lines:
        same_row = [p for p in desc_parts if isinstance(p, str)]
        others = sorted((p for p in desc_parts if not isinstance(p, str)), key=lambda p: p[0])
        ordered = same_row + [t for _, t in others if not TITLEBLOCK_NOISE_RE.search(t)]
        entries.append({"code": code, "desc_lines": ordered, "page": page_no, "top": top})

    materials = []
    for e in entries:
        desc = " ".join(x for x in e["desc_lines"] if x).strip()
        if not desc:
            continue
        thickness = None
        tm = re.search(r"(\d+(?:\.\d+)?)\s*CM\b", desc, re.I)
        if tm:
            thickness = float(tm.group(1)) * 10
        else:
            tm = re.search(r"(\d+(?:\.\d+)?)\s*MM\b", desc, re.I)
            if tm:
                thickness = float(tm.group(1))
        category = "Natural Stone" if re.search(r"TRAVERTINE|LIMESTONE|MARBLE|GRANITE|STONE|FLAGSTONE", desc, re.I) else (
            "Paint" if re.search(r"PAINT", desc, re.I) else (
            "Aluminium/Cladding" if re.search(r"ALUMIN", desc, re.I) else "Other"))
        materials.append(Material(
            code=e["code"], category=category, name=desc, thickness_mm=thickness,
            evidence=[Evidence(source=source_name, page=e["page"], text=desc, confidence=0.95)],
        ))
    return materials


NAMED_STONE_RE = re.compile(r"([A-Z][a-zA-Z]*\s+)?(?:Travertine|Limestone|Marble|Flagstone)[^.\n]{0,80}", re.I)


def _inline_fallback_materials(all_text: str, source_name: str, page_lookup):
    """When a sheet has no parseable legend table, still flag stone/material mentions
    found in running text (e.g. section/detail notes) so nothing silently gets skipped."""
    found = {}
    for m in FALLBACK_CODE_RE.finditer(all_text):
        code = m.group(0)
        if code not in found:
            start = max(0, m.start() - 40)
            end = min(len(all_text), m.end() + 120)
            found[code] = " ".join(all_text[start:end].split())
    materials = []
    for code, snippet in found.items():
        materials.append(Material(code=code, category="Other (no legend table on this sheet)", name=snippet,
                                   thickness_mm=None,
                                   evidence=[Evidence(source=source_name, page=page_lookup(code), text=snippet, confidence=0.5)]))
    for m in NAMED_STONE_RE.finditer(all_text):
        snippet = " ".join(m.group(0).split())
        key = f"TEXT::{snippet[:40]}"
        if key not in found:
            found[key] = snippet
            materials.append(Material(code="(unlabelled)", category="Natural Stone (named in text, no code)",
                                       name=snippet, thickness_mm=None,
                                       evidence=[Evidence(source=source_name, page=page_lookup(None), text=snippet, confidence=0.4)]))
    return materials


def analyze_pdf(path: str) -> AnalysisResult:
    pages = extract_pdf_words(path)
    all_text = "\n".join(t for _, t, _ in pages)
    source_name = Path(path).name
    sheet_number = find_sheet_number(pages, source_name)

    materials = []
    page_of_code = {}
    for page_no, text, words in pages:
        legend_materials = _parse_legend_table(words, page_no, source_name)
        for mat in legend_materials:
            page_of_code[mat.code] = page_no
        materials.extend(legend_materials)

    if not materials:
        def _page_for(code):
            return page_of_code.get(code, pages[0][0] if pages else 1)
        materials = _inline_fallback_materials(all_text, source_name, _page_for)

    codes = [m.code for m in materials if m.code != "(unlabelled)"]

    levels = sorted(set(m.group(0).strip() for m in LEVEL_RE.finditer(all_text)))
    dims = []
    for m in DIM_RE.finditer(all_text):
        try:
            v = float(m.group(0))
            if 0.05 <= v <= 60:
                dims.append(v)
        except ValueError:
            pass
    dims = sorted(set(dims))

    # One zone candidate per detected NATURAL-STONE material on this sheet (per the
    # client's instruction to keep this to external stone/marble codes only, not the
    # aluminium/paint/HPL entries the same legend also lists): this is what lets the
    # client see "more than one zone" proposed automatically instead of a single
    # hand-typed "Zone 1" -- but width/height are left blank (RFI) since text extraction
    # cannot safely assign a specific wall length/height to a specific code without the
    # underlying CAD geometry or a site survey.
    zones = []
    opening_count = len(re.findall(r"\b(?:WINDOWS?|DOORS?|OPENINGS?|GLAZING|SHOPFRONT)\b", all_text, re.I))
    for mat in materials:
        if mat.code == "(unlabelled)" or not mat.category.startswith("Natural Stone"):
            continue
        zones.append(ZoneCandidate(
            zone_id=f"{sheet_number}-{mat.code}",
            sheet=sheet_number,
            material_code=mat.code,
            material_name=mat.name,
            thickness_mm=mat.thickness_mm,
            candidate_dimensions_m=dims[:12],
            status="RFI_REQUIRED",
            note="Auto-proposed from the legend table; width/height must still be confirmed from CAD/survey before panelization.",
            confidence=0.95,
            source="pdf_legend",
            opening_count=opening_count,
            boundary_hint="Review corners, doors and windows from CAD elevation before approval.",
        ))

    # Keep a selectable work area when the finish legend is on another sheet. The
    # proposal is deliberately low-confidence and remains RFI_REQUIRED.
    facade_cues = len(re.findall(r"\b(?:ELEVATION|FACADE|FAÇADE|WALL\s+SECTION|EXTERNAL\s+WALL|CLADDING|STONE\s+FINISH)\b", all_text, re.I))
    excluded = bool(re.search(r"\bECLM\s*[- ]?01\b", all_text, re.I))
    if not zones and facade_cues and not excluded:
        zones.append(ZoneCandidate(
            zone_id=f"{sheet_number}-EXTERNAL-WALL-01",
            sheet=sheet_number,
            material_code="RFI-MATERIAL",
            material_name="External wall finish to be confirmed",
            thickness_mm=None,
            candidate_dimensions_m=dims[:12],
            status="RFI_REQUIRED",
            note="AI detected an elevation/facade or external-wall work area, but no stone code was found on this sheet. Confirm material, wall run and openings from CAD/survey.",
            confidence=min(0.75, 0.35 + 0.08 * facade_cues),
            source="pdf_text_inference",
            opening_count=opening_count,
            boundary_hint="Proposed sheet-level area; exact wall boundaries and termination points require CAD review.",
        ))

    warnings = [
        "Never fabricate a missing dimension.",
        "Prefer explicit dimensions over scale-derived measurements.",
        "If wall width/height cannot be verified from explicit dimensions or levels, mark RFI_REQUIRED.",
        "candidate_dimensions_m lists every plausible number found on the sheet; it is not yet assigned to a specific wall run.",
        "AI zone proposals are review aids. Confirm each boundary, opening termination and material code against CAD/survey before fabrication.",
    ]
    return AnalysisResult(
        file_name=source_name,
        sheet_number=sheet_number,
        materials=materials,
        detected_codes=codes,
        levels=levels,
        dimensions_m=dims,
        zones=zones,
        warnings=warnings,
    )


STANDING_RFI = [
    "Use CAD geometry and survey to assign each candidate dimension to a specific wall elevation/zone; extracted PDF numbers are reference evidence only.",
    "Provide verified external wall lengths/heights and opening schedules for every window and door termination.",
    "Confirm stone panel module, vein direction/bookmatch and approved 20mm/25mm/30mm profile by elevation.",
    "Confirm substrate, cavity reference, uniform bracket/U-channel projection, anchor capacity and engineer-approved fixing spacing.",
    "Confirm waterproofing build-up, flashings, drips, returns and termination details at pool, pond, roof and landscape interfaces.",
]


def merge_project_register(results, project_name: str = "Stone Works"):
    """Combine per-file AnalysisResult objects into one live ProjectRegister, computed
    fresh from whatever the client just uploaded (replacing the previous static,
    hand-authored external_stone_project_register.json)."""
    from models import ProjectRegister

    materials, zones = [], []
    levels_by_sheet, dims_by_sheet = {}, {}
    no_legend_sheets = []
    for r in results:
        materials.extend(r.materials)
        zones.extend(r.zones)
        levels_by_sheet[r.sheet_number] = r.levels
        dims_by_sheet[r.sheet_number] = r.dimensions_m
        if not any(m.category != "Other (no legend table on this sheet)" and "no legend" not in m.category for m in r.materials) and \
           any(m.category == "Other (no legend table on this sheet)" for m in r.materials):
            no_legend_sheets.append(r.sheet_number)

    rfi = list(STANDING_RFI)
    if no_legend_sheets:
        rfi.append(f"No LEGEND/Code-Description table was found on: {', '.join(sorted(set(no_legend_sheets)))}; "
                    f"material codes on these sheets were matched by inline text search only and should be checked manually.")
    if not zones:
        rfi.append("No natural-stone cladding code was detected on any uploaded sheet; confirm the correct wall-finish/legend sheet was included.")

    warnings = []
    for r in results:
        for w in r.warnings:
            if w not in warnings:
                warnings.append(w)

    return ProjectRegister(
        project=project_name,
        status="LIVE ANALYSIS - DIMENSIONS EXTRACTED FROM UPLOADED DRAWING TEXT; VERIFY AGAINST CAD AND SITE SURVEY",
        sheets_analyzed=[r.sheet_number for r in results],
        materials=materials,
        zones=zones,
        levels_by_sheet=levels_by_sheet,
        dimensions_by_sheet=dims_by_sheet,
        rfi_required=rfi,
        warnings=warnings,
    )
