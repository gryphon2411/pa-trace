from typing import Dict, Any, List

def build_checklist(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simplified spine MRI criteria checklist for demo purposes.
    DO NOT use for real clinical decisions.

    Overall logic (demo):
      - If red flags present -> MET
      - Else if conservative_care_weeks >= 6 -> MET
      - Else if conservative_care_weeks is None -> UNKNOWN (needs human review)
      - Else -> NOT_MET
    """
    items = []
    missing = []

    red = bool(extracted.get("red_flags_present"))
    ccw = extracted.get("conservative_care_weeks")

    # C1: Red flags
    items.append({
        "id": "C1_RED_FLAGS",
        "description": "Red-flag indication present (exception to conservative care requirement).",
        "status": "MET" if red else "NOT_MET",
        "evidence_keys": ["red_flags"] if red else [],
    })

    # C2: Conservative care duration
    if ccw is None:
        status = "UNKNOWN"
        missing.append("conservative_care_weeks")
    elif ccw >= 6:
        status = "MET"
    else:
        status = "NOT_MET"
    items.append({
        "id": "C2_CONSERVATIVE_CARE",
        "description": "Conservative care duration meets typical threshold (>=6 weeks) when no red flags.",
        "status": status,
        "evidence_keys": ["conservative_care_weeks"] if ccw is not None else [],
    })

    if red:
        overall = "MET"
    else:
        overall = status  # based on conservative care

    # Missing evidence checklist (also include if symptoms duration missing)
    if extracted.get("symptoms_duration_weeks") is None:
        missing.append("symptoms_duration_weeks")

    return {
        "overall_status": overall,
        "criteria": items,
        "missing_evidence": sorted(set(missing)),
        "notes": "Demo checklist only; grounded in typical utilization management patterns.",
    }
