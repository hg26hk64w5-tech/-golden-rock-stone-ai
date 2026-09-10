import re
from pathlib import Path
import fitz
from models import Material, Evidence, AnalysisResult

MATERIAL_PATTERNS = {
    "EWMB-01": {
        "category": "Natural Stone",
        "name": "Beige Travertine Romano Classico",
        "thickness_mm": 20.0,
        "regex": r"EWMB\s*-?\s*01|BEIGE\s+TRAVERTINE\s+ROMANO\s+CLASSICO"
    },
    "EWST-02": {
        "category": "Natural Stone",
        "name": "Flagstone Cladding Random Cut",
        "thickness_mm": None,
        "regex": r"EWST\s*-?\s*02|FLAGSTONE\s+CLADDING"
    },
    "EWPT-01": {
        "category": "Paint",
        "name": "White Paint",
        "thickness_mm": None,
        "regex": r"EWPT\s*-?\s*01|WHITE\s+PAINT"
    },
}

LEVEL_RE = re.compile(r"(?:FFL|SSL|T\.O\.P\.|TOP)?\s*[+=]\s*-?\d+(?:\.\d+)?", re.I)
DIM_RE = re.compile(r"(?<![\d.])(?:\d{1,2}\.\d{2})(?![\d.])")


def extract_pdf_text(path: str):
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc, start=1):
        pages.append((i, page.get_text("text")))
    return pages


def analyze_pdf(path: str) -> AnalysisResult:
    pages = extract_pdf_text(path)
    all_text = "\n".join(t for _, t in pages)
    mats = []
    codes = []
    for code, spec in MATERIAL_PATTERNS.items():
        hit_page = None
        hit_text = None
        for pageno, text in pages:
            m = re.search(spec["regex"], text, flags=re.I)
            if m:
                hit_page = pageno
                start = max(0, m.start()-120)
                end = min(len(text), m.end()+220)
                hit_text = " ".join(text[start:end].split())
                break
        if hit_page:
            codes.append(code)
            mats.append(Material(
                code=code,
                category=spec["category"],
                name=spec["name"],
                thickness_mm=spec["thickness_mm"],
                evidence=[Evidence(source=Path(path).name, page=hit_page, text=hit_text, confidence=0.99)]
            ))

    levels = sorted(set(m.group(0).strip() for m in LEVEL_RE.finditer(all_text)))
    dims = []
    for m in DIM_RE.finditer(all_text):
        try:
            v = float(m.group(0))
            if 0.05 <= v <= 50:
                dims.append(v)
        except ValueError:
            pass
    dims = sorted(set(dims))

    warnings = [
        "Never fabricate a missing dimension.",
        "Prefer explicit dimensions over scale-derived measurements.",
        "If wall width/height cannot be verified from explicit dimensions or levels, mark RFI_REQUIRED."
    ]
    return AnalysisResult(
        file_name=Path(path).name,
        materials=mats,
        detected_codes=codes,
        levels=levels,
        dimensions_m=dims,
        warnings=warnings,
    )
