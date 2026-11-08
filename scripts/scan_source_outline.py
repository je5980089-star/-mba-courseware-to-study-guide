#!/usr/bin/env python3
"""Scan lecture files for pages, numbered step headings, and textless pages.

This is a mechanical pre-scan to challenge the agent's own coverage manifest.
It does NOT infer the meaning of a process or replace visual inspection.
Supported: PDF (PyMuPDF), PPTX (python-pptx), DOCX (python-docx), TXT, MD.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STEP_RE = re.compile(
    r"(?:第\s*(?:[一二三四五六七八九十百]+|\d{1,2})\s*(?:步|阶段|环节|部分)|"
    r"(?:step|phase)\s*[0-9]{1,2}\b)", re.I
)
NUM_RE = re.compile(r"\d+")
CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def step_number(label: str) -> int | None:
    m = NUM_RE.search(label)
    if m:
        return int(m.group())
    m = re.search(r"第\s*([一二三四五六七八九十百零〇]+)\s*(?:步|阶段|环节|部分)", label)
    if not m:
        return None
    value = m.group(1)
    if value in CN_DIGIT:
        return CN_DIGIT[value]
    if "百" in value:  # support common one-hundred forms without arbitrary inference
        left, _, right = value.partition("百")
        base = (CN_DIGIT.get(left, 1) or 1) * 100
        if not right:
            return base
        if "十" not in right:
            return base + CN_DIGIT.get(right, 0)
        tens, _, units = right.partition("十")
        return base + (CN_DIGIT.get(tens, 1) or 1) * 10 + CN_DIGIT.get(units, 0)
    if "十" in value:
        left, _, right = value.partition("十")
        return (CN_DIGIT.get(left, 1) or 1) * 10 + CN_DIGIT.get(right, 0)
    return None


def extract_units(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Install pymupdf to scan PDFs") from exc
        with fitz.open(path) as pdf:
            return [page.get_text("text") for page in pdf]
    if suffix == ".pptx":
        try:
            from pptx import Presentation
        except ImportError as exc:
            raise RuntimeError("Install python-pptx to scan slides") from exc
        pres = Presentation(str(path))
        out = []
        for slide in pres.slides:
            parts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    parts.append(shape.text)
                if shape.has_table:
                    for row in shape.table.rows:
                        parts.append(" ".join(c.text for c in row.cells))
            if slide.has_notes_slide:
                try:
                    parts.append(slide.notes_slide.notes_text_frame.text)
                except (AttributeError, ValueError):
                    pass
            out.append("\n".join(parts))
        return out
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Install python-docx to scan DOCX") from exc
        doc = Document(path)
        chunks = [p.text for p in doc.paragraphs]
        chunks += [c.text for tb in doc.tables for row in tb.rows for c in row.cells]
        return ["\n".join(chunks)]  # not page-aware without rendering
    if suffix in (".txt", ".md"):
        return [path.read_text(encoding="utf-8")]
    raise ValueError(f"Unsupported input: {path.suffix}")


def scan_files(paths: list[Path]) -> dict:
    units = []
    step_events = []
    for file in paths:
        pages = extract_units(file)
        for i, page_text in enumerate(pages, start=1):
            unit_id = f"{file.name}:p{i}"
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            seen = []
            for ix, line in enumerate(lines):
                for match in STEP_RE.finditer(line):
                    label = match.group(0)
                    context = line[max(0, match.start()-18):match.end()+65]
                    if context not in seen:
                        seen.append(context)
                    step_events.append({"unit_id": unit_id, "file": file.name, "page": i,
                                        "label": label, "number": step_number(label),
                                        "context": context})
            units.append({"id": unit_id, "text_chars": len(re.sub(r"\s+", "", page_text)),
                          "needs_visual_inspection": len(re.sub(r"\s+", "", page_text)) < 30,
                          "numbered_step_signals": seen})
    # Form candidates when an increasing numbered sequence appears on nearby pages in the same file.
    candidates = []
    grouped = {}
    for ev in step_events:
        grouped.setdefault(ev["file"], []).append(ev)
    count = 0
    for filename, evs in grouped.items():
        evs = sorted(evs, key=lambda x: (x["page"], x["number"] or 0))
        run = []
        def flush(run):
            nonlocal count
            # Require >=3 distinct sequential steps to keep false positives under control.
            distinct = sorted({e["number"] for e in run if e["number"] is not None})
            if len(distinct) < 3:
                return
            missing = sorted(set(range(distinct[0], distinct[-1]+1)) - set(distinct))
            count += 1
            candidates.append({"id": f"flow-{count}", "file": filename,
                               "unit_ids": list(dict.fromkeys(e["unit_id"] for e in run)),
                               "step_numbers": distinct, "missing_numbers": missing,
                               "step_events": run,
                               "instruction": "Review for a composite management process; record decision in manifest.flow_decisions"})
        for ev in evs:
            if not run:
                run = [ev]
                continue
            prev = run[-1]
            # Allow duplicate labels across slides; permit a max 8 page gap.
            if ev["page"] - prev["page"] <= 8 and (
                ev["number"] is None or prev["number"] is None or
                0 <= ev["number"] - prev["number"] <= 3):
                run.append(ev)
            else:
                flush(run)
                run = [ev]
        flush(run)
    return {"schema_version": 1, "units": units, "flow_candidates": candidates,
            "limitations": ["PDF scanned/image-only pages require visual inspection.",
                            "A word document is treated as one logical unit, not real pages.",
                            "Unnumbered cross-page frameworks require semantic review."]}


def main():
    ap = argparse.ArgumentParser(description="Pre-scan lecture files for source coverage and numbered workflows")
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, help="Output scan JSON; else print stdout")
    args = ap.parse_args()
    try:
        res = scan_files(args.inputs)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Cannot scan: {exc}", file=sys.stderr)
        return 2
    output = json.dumps(res, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
