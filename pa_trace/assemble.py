import json
from pathlib import Path
from typing import Dict, Any
import html

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
    Wrap given spans with <mark> based on start/end offsets.
    Assumes spans are within the original text.
    """
    # Sort spans by start descending to avoid offset shifts when inserting tags
    spans_sorted = sorted(
        [s for s in spans if s.get("source") == "note" and isinstance(s.get("start"), int) and isinstance(s.get("end"), int)],
        key=lambda s: s["start"],
        reverse=True,
    )
    out = text
    for s in spans_sorted:
        start, end = s["start"], s["end"]
        if start < 0 or end > len(out) or start >= end:
            continue
        # escape is applied later; here we insert sentinel tags
        out = out[:end] + "__MARK_END__" + out[end:]
        out = out[:start] + "__MARK_START__" + out[start:]
    # Now escape, then replace sentinels with HTML tags
    out = html.escape(out)
    out = out.replace("__MARK_START__", "<mark>")
    out = out.replace("__MARK_END__", "</mark>")
    return out

def _render_highlights_html(bundle: Dict[str, Any]) -> str:
    case = bundle["case"]
    note = case.get("note_text", "")
    ex = bundle["extracted"]
    ev = ex.get("evidence", {})
    # flatten note spans
    spans = []
    for k, lst in ev.items():
        for sp in lst:
            if sp.get("source") == "note":
                spans.append(sp)

    note_marked = _apply_marks(note, spans)

    # Policy: render retrieved chunks
    policy_html = []
    for ch in bundle.get("retrieved_policy", []):
        policy_html.append(f"<div class='chunk'><div class='chunk_id'>{html.escape(ch['chunk_id'])}</div><pre>{html.escape(ch['text'])}</pre></div>")

    # Field table
    rows = []
    rows.append(("symptoms_duration_weeks", ex.get("symptoms_duration_weeks")))
    rows.append(("conservative_care_weeks", ex.get("conservative_care_weeks")))
    rows.append(("treatments", ", ".join(ex.get("treatments", [])) or "—"))
    rows.append(("red_flags", ", ".join(ex.get("red_flags", [])) or "—"))
    rows.append(("overall_status", bundle["checklist"].get("overall_status")))

    rows_html = "\n".join([f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>" for k,v in rows])

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>PA-Trace Highlights — {html.escape(case.get('case_id',''))}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 12px 0; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 14px; }}
    pre {{ white-space: pre-wrap; word-wrap: break-word; }}
    mark {{ padding: 0 2px; border-radius: 3px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td {{ border: 1px solid #eee; padding: 6px 8px; vertical-align: top; }}
    .chunk_id {{ font-weight: 600; margin-bottom: 6px; }}
    .muted {{ color: #666; }}
  </style>
</head>
<body>
  <h1>PA-Trace Highlights</h1>
  <div class="muted">Draft-only demo artifact. Highlights show evidence spans found in the note.</div>

  <div class="grid" style="margin-top:16px;">
    <div class="card">
      <h2>Note (highlighted)</h2>
      <pre>{note_marked}</pre>
    </div>
    <div class="card">
      <h2>Extracted fields</h2>
      <table>{rows_html}</table>
      <h3 style="margin-top:14px;">Missing evidence</h3>
      <pre>{html.escape(", ".join(bundle["checklist"].get("missing_evidence", [])) or "—")}</pre>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <h2>Retrieved policy chunks (for traceability)</h2>
    {''.join(policy_html) or '<div class="muted">No policy chunks retrieved.</div>'}
  </div>
</body>
</html>
"""

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
