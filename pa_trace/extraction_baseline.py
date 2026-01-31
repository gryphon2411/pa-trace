import re
from typing import Dict, Any, List

TREATMENT_KEYWORDS = {
    "pt": ["physical therapy", "pt"],
    "nsaids": ["nsaid", "ibuprofen", "naproxen", "diclofenac"],
    "home_exercise": ["home exercise", "home exercises"],
    "chiropractic": ["chiropractic", "chiro"],
    "steroid": ["oral steroid", "prednisone", "methylprednisolone"],
    "injection": ["epidural", "steroid injection", "esi", "injection"],
}

RED_FLAG_KEYWORDS = {
    "cauda_equina": ["urinary retention", "saddle anesthesia", "bowel or bladder", "incontinence"],
    "progressive_neuro_deficit": ["progressive weakness", "worsening weakness", "foot drop"],
    "cancer": ["history of cancer", "malignancy", "unexplained weight loss"],
    "infection": ["fever", "iv drug use", "discitis", "osteomyelitis", "infection"],
    "fracture_trauma": ["trauma", "fell", "fall", "motor vehicle", "fracture"],
}

def _find_weeks(text: str) -> int | None:
    """
    Extract a coarse duration in weeks from phrases like:
      - "8 weeks"
      - "6-week"
      - "two months" (approx -> 8 weeks)
    """
    m = re.search(r"(\d{1,2})\s*-\s*week|(\d{1,2})\s*weeks?", text.lower())
    if m:
        # pick the first numeric group found
        for g in m.groups():
            if g and g.isdigit():
                return int(g)
    # months heuristic
    m2 = re.search(r"(\d{1,2})\s*months?", text.lower())
    if m2:
        return int(m2.group(1)) * 4
    if "two months" in text.lower():
        return 8
    if "three months" in text.lower():
        return 12
    return None

def _detect_treatments(text: str) -> List[str]:
    tl = text.lower()
    found = []
    for k, kws in TREATMENT_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            found.append(k)
    return sorted(set(found))

def _detect_red_flags(text: str) -> List[str]:
    tl = text.lower()
    flags = []
    for k, kws in RED_FLAG_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            flags.append(k)
    return sorted(set(flags))

def _evidence_span(text: str, needle: str) -> dict | None:
    """
    Return first occurrence span for a needle substring (case-insensitive).
    """
    tl = text.lower()
    nl = needle.lower()
    idx = tl.find(nl)
    if idx == -1:
        return None
    return {"source": "note", "start": idx, "end": idx + len(needle), "quote": text[idx:idx+len(needle)]}

def extract_facts_baseline(note_text: str, retrieved_policy: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Symptoms duration (weeks) — naive
    symptoms_weeks = _find_weeks(note_text)

    # Conservative care weeks: attempt to detect explicit "X weeks of PT" etc.
    conservative_weeks = None
    # look for "X weeks of physical therapy"
    m = re.search(r"(\d{1,2})\s*weeks?\s*of\s*(physical therapy|pt)", note_text.lower())
    if m:
        conservative_weeks = int(m.group(1))

    treatments = _detect_treatments(note_text)
    red_flags = _detect_red_flags(note_text)

    # Build provenance map (baseline: coarse quotes only)
    evidence = {}
    if symptoms_weeks is not None:
        # try to find the specific phrase
        m = re.search(rf"{symptoms_weeks}\s*weeks?", note_text.lower())
        if m:
            start, end = m.span()
            evidence["symptoms_duration_weeks"] = [{"source":"note","start":start,"end":end,"quote":note_text[start:end]}]
    if conservative_weeks is not None:
        m = re.search(rf"{conservative_weeks}\s*weeks?\s*of\s*(physical therapy|pt)", note_text.lower())
        if m:
            start, end = m.span()
            evidence["conservative_care_weeks"] = [{"source":"note","start":start,"end":end,"quote":note_text[start:end]}]
    if treatments:
        # store first keyword mention as evidence for each treatment
        evs = []
        for t in treatments:
            kws = TREATMENT_KEYWORDS.get(t, [])
            for kw in kws:
                sp = _evidence_span(note_text, kw)
                if sp:
                    evs.append(sp); break
        if evs:
            evidence["treatments"] = evs
    if red_flags:
        evs = []
        for f in red_flags:
            kws = RED_FLAG_KEYWORDS.get(f, [])
            for kw in kws:
                sp = _evidence_span(note_text, kw)
                if sp:
                    evs.append(sp); break
        if evs:
            evidence["red_flags"] = evs

    extracted = {
        "symptoms_duration_weeks": symptoms_weeks,
        "conservative_care_weeks": conservative_weeks,
        "treatments": treatments,
        "red_flags": red_flags,
        "red_flags_present": bool(red_flags),
        "evidence": evidence,
        "extraction_mode": "baseline",
    }
    return extracted
