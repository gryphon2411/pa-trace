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

_WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}

# Regex fragment that matches a number — either digits or word-form
_NUM_PAT = r"(\d{1,2}|" + "|".join(_WORD_TO_NUM.keys()) + r")"


def _to_int(s: str) -> int | None:
    """Convert a digit string or word-form number to int."""
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return _WORD_TO_NUM.get(s)


def _to_weeks(value: int, unit: str) -> int:
    """Convert a duration value + unit to weeks."""
    if "month" in unit:
        return value * 4
    return value


def _find_weeks(text: str) -> int | None:
    """
    Extract a coarse duration in weeks from phrases like:
      - "8 weeks", "6-week"
      - "3 months", "two months"
    """
    tl = text.lower()
    # digit-form weeks: "8 weeks", "6-week"
    m = re.search(r"(\d{1,2})\s*-?\s*weeks?", tl)
    if m:
        return int(m.group(1))
    # digit-form months: "3 months"
    m2 = re.search(r"(\d{1,2})\s*months?", tl)
    if m2:
        return int(m2.group(1)) * 4
    # word-form: "two months", "six weeks"
    pat = _NUM_PAT + r"\s+(weeks?|months?)"
    m3 = re.search(pat, tl)
    if m3:
        v = _to_int(m3.group(1))
        if v is not None:
            return _to_weeks(v, m3.group(2))
    return None


# Treatment name patterns for conservative care matching
_CARE_NAMES = [
    r"physical therapy", r"pt\b", r"home exercises?",
    r"chiropractic", r"chiro",
]
_CARE_PAT = "|".join(_CARE_NAMES)
_UNIT_PAT = r"(weeks?|months?)"


def _find_conservative_care_weeks(text: str) -> tuple[int | None, str | None]:
    """
    Extract the maximum conservative care duration in weeks.

    Handles both directions:
      - "<N> weeks/months of <treatment>"   (e.g. "8 weeks of physical therapy")
      - "<treatment> for <N> weeks/months"  (e.g. "home exercises for two months")

    Returns (max_weeks, matched_quote) or (None, None).
    """
    tl = text.lower()
    durations: list[tuple[int, str]] = []  # (weeks, matched_text)

    # Pattern A: "<N> <unit> of <treatment>"
    pat_a = _NUM_PAT + r"\s+" + _UNIT_PAT + r"\s+of\s+(" + _CARE_PAT + r")"
    for m in re.finditer(pat_a, tl):
        v = _to_int(m.group(1))
        if v is not None:
            weeks = _to_weeks(v, m.group(2))
            durations.append((weeks, text[m.start():m.end()]))

    # Pattern B: "<treatment> for <N> <unit>"
    pat_b = r"(" + _CARE_PAT + r")\s+for\s+" + _NUM_PAT + r"\s+" + _UNIT_PAT
    for m in re.finditer(pat_b, tl):
        v = _to_int(m.group(2))
        if v is not None:
            weeks = _to_weeks(v, m.group(3))
            durations.append((weeks, text[m.start():m.end()]))

    if not durations:
        return None, None

    # Return the maximum duration
    best = max(durations, key=lambda x: x[0])
    return best[0], best[1]

def _detect_treatments(text: str) -> List[str]:
    tl = text.lower()
    found = []
    for k, kws in TREATMENT_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            found.append(k)
    return sorted(set(found))

_NEGATION_PREFIXES = [
    "no evidence of", "negative for", "ruled out", "rules out",
    "denies", "deny", "denied", "without", "no", "not", "absent",
]

def _is_negated(text_lower: str, match_start: int) -> bool:
    """Check if the keyword at match_start is preceded by a negation cue."""
    # Look at a window of up to 30 chars before the match
    window_start = max(0, match_start - 30)
    prefix = text_lower[window_start:match_start].strip().rstrip(".,;:")
    # Check if the prefix ends with a negation phrase
    for neg in _NEGATION_PREFIXES:
        if prefix.endswith(neg):
            return True
    return False

def _detect_red_flags(text: str) -> List[str]:
    tl = text.lower()
    flags = []
    for k, kws in RED_FLAG_KEYWORDS.items():
        flag_found = False
        for kw in kws:
            idx = tl.find(kw)
            while idx != -1:
                if not _is_negated(tl, idx):
                    flag_found = True
                    break
                # Search for next occurrence after this one
                idx = tl.find(kw, idx + len(kw))
            if flag_found:
                break
        if flag_found:
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

    # Conservative care weeks: flexible pattern matching
    conservative_weeks, care_quote = _find_conservative_care_weeks(note_text)

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
    if conservative_weeks is not None and care_quote is not None:
        span = _evidence_span(note_text, care_quote)
        if span:
            evidence["conservative_care_weeks"] = [span]
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
