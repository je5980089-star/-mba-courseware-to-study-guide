#!/usr/bin/env python3
"""Structural QA for AI-generated MBA study guides.

This verifies explicit and integrated coverage, not the factual accuracy of prose.
It deliberately requires a composite method to have its own heading and ordered,
explained steps rather than just six keywords scattered across a document.

Examples:
    python scripts/audit_guide.py --manifest coverage_manifest.json \
        --document guide.docx --pdf guide-print.pdf --report audit.json

Dependencies: python-docx for .docx, PyMuPDF for .pdf. .md/.txt require only stdlib.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def visible_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def docx_blocks(path: Path) -> list[dict[str, Any]]:
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pip install python-docx") from exc

    doc = Document(path)
    blocks = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            t = para.text.strip()
            if t:
                style = para.style.name if para.style else ""
                match = re.search(r"(?:Heading|标题)\s*([1-9])", style, re.I)
                level = int(match.group(1)) if match else None
                blocks.append({"kind": "paragraph", "text": t, "heading_level": level})
        elif child.tag == qn("w:tbl"):
            table = Table(child, doc)
            cells = ["  ".join(c.text for c in row.cells) for row in table.rows]
            blocks.append({"kind": "table", "text": "\n".join(cells), "heading_level": None})
    return blocks


def markdown_blocks(path: Path) -> list[dict[str, Any]]:
    blocks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            m = re.match(r"^(#{1,6})\s+", line)
            blocks.append({"kind": "paragraph", "text": line.strip(),
                           "heading_level": len(m.group(1)) if m else None})
    return blocks


def pdf_blocks(path: Path) -> list[dict[str, Any]]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pip install pymupdf") from exc
    out = []
    with fitz.open(path) as pdf:
        for page in pdf:
            text = page.get_text("text")
            for line in text.splitlines():
                if line.strip():
                    out.append({"kind": "paragraph", "text": line.strip(), "heading_level": None})
    return out


def load_blocks(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return docx_blocks(path)
    if suffix in (".md", ".txt"):
        return markdown_blocks(path)
    if suffix == ".pdf":
        return pdf_blocks(path)
    raise ValueError(f"Unsupported document format: {suffix}; use DOCX, PDF, MD or TXT")


def find_heading(blocks: list[dict], name: str) -> tuple[int, int] | None:
    key = compact(name)
    for i, block in enumerate(blocks):
        if block["heading_level"] is not None and key in compact(block["text"]):
            return i, block["heading_level"]
    return None


def section_text(blocks: list[dict], heading_index: int, level: int) -> str:
    parts = []
    for block in blocks[heading_index + 1:]:
        if block["heading_level"] is not None and block["heading_level"] <= level:
            break
        parts.append(block["text"])
    return "\n".join(parts)


def check_pdf(path: Path, max_pages: int | None) -> tuple[list[str], list[str], dict]:
    try:
        import fitz
    except ImportError:
        return [], ["PyMuPDF not installed: cannot verify print PDF pages"], {}
    failures, warnings = [], []
    metrics = {}
    with fitz.open(path) as pdf:
        page_count = len(pdf)
        metrics["rendered_page_count"] = page_count
        if page_count == 0:
            failures.append("Rendered PDF has zero pages")
        if max_pages is not None and page_count > max_pages:
            failures.append(f"Printed page cap exceeded: {page_count} > {max_pages}")
        for i, page in enumerate(pdf):
            # Visual objects/images may extend beyond text; text-based fullness is only a warning.
            blocks = page.get_text("blocks")
            blocks = [b for b in blocks if len(b) > 4 and b[4].strip()]
            if not blocks:
                warnings.append(f"PDF page {i+1} has no extractable text; visually inspect it")
                continue
            last_y = max(b[3] for b in blocks)
            utilized = max(0.0, min(1.0, last_y / page.rect.height))
            if i < page_count - 1 and utilized < 0.66:
                warnings.append(f"PDF page {i+1} may have excessive lower blank area ({(1-utilized):.0%}); inspect page breaks/tables")
    return failures, warnings, metrics


def check_guide(manifest: dict, blocks: list[dict], pdf: Path | None = None, source_scan: dict | None = None) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    review: list[str] = []
    text = "\n".join(b["text"] for b in blocks)
    compact_text = compact(text)
    constraints = manifest.get("constraints", {})

    units = manifest.get("source_units", [])
    if not units:
        failures.append("Manifest has no source_units: full source inspection cannot be certified")
    ids = set()
    for unit in units:
        ident = unit.get("id")
        if not ident or ident in ids:
            failures.append("Every source unit needs a unique nonblank id")
        ids.add(ident)
        status = unit.get("status")
        if status not in ("reviewed", "blank", "unreadable"):
            failures.append(f"Source unit {ident} has invalid/unset status: {status}")
        elif status == "unreadable":
            warnings.append(f"Source unit {ident} could not be read and needs manual inspection")

    if source_scan is not None:
        scan_unit_ids = {u.get("id") for u in source_scan.get("units", [])}
        missing_units = scan_unit_ids - ids
        if missing_units:
            failures.append("Missing inspected source pages: " + ", ".join(sorted(missing_units)[:20]))
        # Independent numbered-step scan prevents a manifest containing only topics the agent chose to write.
        decisions = {d.get("candidate_id"): d for d in manifest.get("flow_decisions", [])}
        for candidate in source_scan.get("flow_candidates", []):
            cid = candidate.get("id")
            d = decisions.get(cid)
            if d is None:
                failures.append(f"Detected numbered workflow {cid} has no accept/reject decision in flow_decisions")
            elif d.get("decision") == "composite":
                comp_id = d.get("composite_id")
                if not any(c.get("id") == comp_id for c in manifest.get("composites", [])):
                    failures.append(f"Workflow {cid} points to missing composite_id={comp_id}")
            elif d.get("decision") == "not_composite":
                if len(d.get("reason", "").strip()) < 15:
                    failures.append(f"Workflow {cid} rejected without a meaningful reason")
            else:
                failures.append(f"Workflow {cid} decision must be composite or not_composite")

    topics = manifest.get("topics", [])
    if not topics:
        failures.append("Manifest has no topics: knowledge completeness cannot be audited")
    topic_ids = set()
    for topic in topics:
        tid = topic.get("id")
        if not tid or tid in topic_ids:
            failures.append("Every topic needs a unique nonblank id")
        topic_ids.add(tid)
        for source_ref in topic.get("source_refs", []):
            if source_ref not in ids:
                failures.append(f"Topic {tid} cites a missing source unit: {source_ref}")
        if not topic.get("required", True):
            continue
        labels = topic.get("aliases") or [topic.get("title", "")]
        if not any(compact(label) in compact_text for label in labels if label):
            failures.append(f"Missing required topic: {topic.get('title', tid)}")

    for comp in manifest.get("composites", []):
        name = comp.get("title", "")
        label = f"Composite '{name or comp.get('id')}'"
        if not name:
            failures.append("A composite is missing its title")
            continue
        target = find_heading(blocks, name)
        if comp.get("must_have_dedicated_heading", True) and target is None:
            failures.append(f"{label} has NO dedicated heading (keywords elsewhere do not count)")
            continue
        content = section_text(blocks, *target) if target else text
        dense = compact(content)
        minimum = comp.get("min_chars", 400)
        if visible_char_count(content) < minimum:
            failures.append(f"{label} has too little explanatory text: {visible_char_count(content)} < {minimum}")

        prev = -1
        marks = []
        for step in comp.get("steps", []):
            idx = dense.find(compact(step), prev + 1)
            if idx < 0:
                failures.append(f"{label} missing/incorrectly ordered step: {step}")
            else:
                marks.append((step, idx))
                prev = idx
        min_per_step = int(comp.get("min_chars_per_step", 0))
        if min_per_step > 0 and len(marks) == len(comp.get("steps", [])):
            for k,(step,start) in enumerate(marks):
                end = marks[k+1][1] if k+1 < len(marks) else len(dense)
                explanation_len = end - start - len(compact(step))
                if explanation_len < min_per_step:
                    failures.append(f"{label} step '{step}' has insufficient narrative ({explanation_len} chars)")

    if not constraints.get("allow_exam_questions", False):
        for phrase in ("论述题参考答案", "预测大题", "模拟试题", "考题预测"):
            if phrase in text:
                warnings.append(f"Possible unsolicited exam-question section detected: {phrase}")

    # Detect repeated source-narration rather than direct knowledge prose.
    narration_total = sum(text.count(s) for s in ("课件指出", "课件提到", "老师讲过", "PPT讲了", "老师说"))
    if narration_total > 3:
        warnings.append(f"Repeated source-narration detected ({narration_total}); consider direct exposition")

    max_pages = constraints.get("max_pages")
    metrics = {"source_units": len(units), "topics": len(topics),
               "composites": len(manifest.get("composites", [])),
               "document_chars": visible_char_count(text)}
    if pdf:
        p_fail, p_warn, p_metrics = check_pdf(pdf, max_pages)
        failures.extend(p_fail)
        warnings.extend(p_warn)
        metrics.update(p_metrics)
    elif max_pages is not None:
        review.append("A max_pages constraint exists, but no rendered print PDF was supplied: page cap NOT VERIFIED")

    return {"status": "fail" if failures else ("review_required" if review else "pass"),
            "failures": failures, "warnings": warnings, "review_required": review,
            "metrics": metrics, "limitations": [
                "This is a structural audit, not a factual/source-grounding audit.",
                "A title and enough text do not prove that the explanation is correct or pedagogically sufficient.",
                "Inspect key sections and the rendered print visually before delivery."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a study guide against a coverage manifest")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--pdf", type=Path, help="Optional rendered print PDF, used to verify page limit")
    parser.add_argument("--source-scan", type=Path, help="Pre-scan JSON from scan_source_outline.py")
    parser.add_argument("--report", type=Path, help="Optional report JSON output")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported manifest schema; expected schema_version=1")
        blocks = load_blocks(args.document)
        pre_scan = json.loads(args.source_scan.read_text(encoding="utf-8")) if args.source_scan else None
        result = check_guide(manifest, blocks, args.pdf, pre_scan)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Audit cannot run: {exc}", file=sys.stderr)
        return 3
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 2 if result["status"] == "fail" else (1 if result["status"] == "review_required" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
