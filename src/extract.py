"""Extract text + a confidence signal from an uploaded creative (README §5).

v1 handles DOCX and text-layer PDF (and plain text). Scanned PDFs and images
are detected and routed to the vision pipeline on Day 2; here they return a
warning and zero-confidence rather than silently trusting empty text.
"""
from __future__ import annotations

from pathlib import Path


def extract(path: str | Path) -> dict:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".docx":
        return _docx(p)
    if ext == ".pdf":
        return _pdf(p)
    if ext in {".txt", ".md"}:
        text = p.read_text(encoding="utf-8")
        return _result(text, "docx", 1.0 if text.strip() else 0.0)
    raise ValueError(f"Unsupported format {ext!r} (v1: .docx, .pdf, .txt)")


def _result(text: str, kind: str, conf: float, warnings=None) -> dict:
    return {
        "extracted_text": text,
        "source_kind": kind,
        "confidence": conf,
        "warnings": warnings or ([] if text.strip() else ["Extraction produced no text"]),
    }


def _docx(p: Path) -> dict:
    import docx  # python-docx

    d = docx.Document(str(p))
    parts = [para.text for para in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    text = "\n".join(t for t in parts if t is not None)
    return _result(text, "docx", 0.99 if text.strip() else 0.0)


def _pdf(p: Path) -> dict:
    import pdfplumber

    pages = []
    with pdfplumber.open(str(p)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()
    if text:
        return _result(text, "pdf_text", 0.95)
    # No text layer -> scanned / image-exported PDF; needs vision (Day 2).
    return _result(
        "", "pdf_scanned", 0.0,
        ["PDF has no text layer — scanned/image PDF needs the vision pipeline (Day 2)"],
    )
