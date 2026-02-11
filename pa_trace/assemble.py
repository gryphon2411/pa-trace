import json
from pathlib import Path
from typing import Dict, Any
import html
from jinja2 import Environment, FileSystemLoader

def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def _render_packet_md(bundle: Dict[str, Any]) -> str:
    case = bundle["case"]
    ex = bundle["extracted"]
    ch = bundle["checklist"]
    lines = []
    lines.append(f"# PA-Trace Packet Draft — {case.get('case_id')}\n")
    lines.append("## Exam request")
    lines.append(f"- Procedure: {case.get('exam_request', {}).get('procedure')}")
    lines.append("")
    lines.append("## Extracted facts (draft)")
    lines.append(f"- Symptoms duration (weeks): {ex.get('symptoms_duration_weeks')}")
    lines.append(f"- Conservative care duration (weeks): {ex.get('conservative_care_weeks')}")
    lines.append(f"- Treatments: {', '.join(ex.get('treatments', [])) or '—'}")
    lines.append(f"- Red flags: {', '.join(ex.get('red_flags', [])) or '—'}")
    lines.append("")
    lines.append("## Checklist")
    lines.append(f"- Overall: **{ch.get('overall_status')}**")
    if ch.get("missing_evidence"):
        lines.append(f"- Missing evidence: {', '.join(ch['missing_evidence'])}")
    lines.append("")
    lines.append("## Provenance (evidence quotes)")
    ev = ex.get("evidence", {})
    for k, spans in ev.items():
        if not spans:
            continue
        lines.append(f"- **{k}**:")
        for sp in spans:
            lines.append(f"  - ({sp.get('source')}) “{sp.get('quote')}”")
    return "\n".join(lines) + "\n"

def _apply_marks(text: str, spans: list[dict]) -> str:
    """
    Wrap given spans with <mark> tags including category classes.
    Uses indexed placeholders to allow safe HTML escaping of the text content.
    """
    # Filter valid note spans and sort by start descending to avoid offset shifts
    valid_spans = [
        s for s in spans
        if s.get("source") == "note"
        and isinstance(s.get("start"), int)
        and isinstance(s.get("end"), int)
    ]
    spans_sorted = sorted(valid_spans, key=lambda s: s["start"], reverse=True)

    out = text
    # Insert unique indexed placeholders for each span
    for i, s in enumerate(spans_sorted):
        start, end = s["start"], s["end"]
        if start < 0 or end > len(out) or start >= end:
            continue
        out = out[:end] + f"__MARK_END_{i}__" + out[end:]
        out = out[:start] + f"__MARK_START_{i}__" + out[start:]

    # Escape the text to make it HTML-safe
    out = html.escape(out)

    # Replace placeholders with actual <mark> tags containing correct classes
    for i, s in enumerate(spans_sorted):
        field_class = s.get("field", "default")
        span_id = f"span_{i}"
        tag_start = f'<mark id="{span_id}" class="highlight {html.escape(field_class)}" data-field="{html.escape(field_class)}">'
        tag_end = "</mark>"
        out = out.replace(f"__MARK_START_{i}__", tag_start)
        out = out.replace(f"__MARK_END_{i}__", tag_end)

    return out

def _render_highlights_html(bundle: Dict[str, Any]) -> str:
    case = bundle["case"]
    note = case.get("note_text", "")
    ex = bundle["extracted"]
    ev = ex.get("evidence", {})
    checklist = bundle["checklist"]

    # Flatten evidence into a list of spans
    spans = []
    for field, span_list in ev.items():
        for sp in span_list:
            if sp.get("source") == "note":
                s_copy = sp.copy()
                s_copy["field"] = field
                spans.append(s_copy)

    note_marked = _apply_marks(note, spans)

    # Prepare Fact Table Rows
    heading_map = {
        "symptoms_duration_weeks": "Symptoms Duration",
        "conservative_care_weeks": "Conservative Care",
        "treatments": "Treatments",
        "red_flags": "Red Flags"
    }

    rows = []
    # explicit order
    keys = ["symptoms_duration_weeks", "conservative_care_weeks", "treatments", "red_flags"]
    
    for key in keys:
        val = ex.get(key)
        is_list = key in ["treatments", "red_flags"]
        
        display_val = "—"
        if val:
            if is_list:
                display_val = ", ".join(val) if val else "—"
            else:
                display_val = str(val)
        
        is_missing = key in checklist.get("missing_evidence", [])
        
        rows.append({
            "key": key,
            "label": heading_map.get(key, key),
            "display_val": display_val,
            "is_missing": is_missing
        })

    # Status Color
    status = checklist.get("overall_status", "UNKNOWN")
    if status == "MET":
        status_color = "#0f9d58"
    elif status == "NOT_MET":
        status_color = "#db4437"
    else:
        status_color = "#f9a825"

    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
    template = env.get_template("highlights.html.j2")
    
    return template.render(
        case=case,
        note_html=note_marked,
        rows=rows,
        overall_status=status,
        status_color=status_color,
        policy_chunks=bundle.get("retrieved_policy", [])
    )

def write_packet_bundle(bundle: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Packet: merge "form-like" fields (minimal)
    case = bundle["case"]
    ex = bundle["extracted"]
    checklist = bundle["checklist"]

    packet = {
        "case_id": case.get("case_id"),
        "exam_request": case.get("exam_request", {}),
        "patient": case.get("patient", {}),
        "requesting_provider": case.get("requesting_provider", {}),
        "clinical_summary": {
            "symptoms_duration_weeks": ex.get("symptoms_duration_weeks"),
            "conservative_care_weeks": ex.get("conservative_care_weeks"),
            "treatments": ex.get("treatments", []),
            "red_flags": ex.get("red_flags", []),
        },
        "checklist_overall": checklist.get("overall_status"),
    }

    _write_json(out_dir / "packet.json", packet)
    _write_json(out_dir / "checklist.json", checklist)
    _write_json(out_dir / "provenance.json", ex.get("evidence", {}))
    (out_dir / "packet.md").write_text(_render_packet_md(bundle), encoding="utf-8")
    (out_dir / "highlights.html").write_text(_render_highlights_html(bundle), encoding="utf-8")
