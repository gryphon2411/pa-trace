"""
MedGemma-based fact extraction using llama-cpp-python.

Implements:
- LLM inference via GGUF model
- Refusal guardrail for clinical decision questions
- Evidence span validation
- Fallback to baseline on errors
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from .extraction_baseline import (
    extract_facts_baseline, _detect_red_flags, _detect_treatments,
    _find_conservative_care_weeks,
    RED_FLAG_KEYWORDS, TREATMENT_KEYWORDS, _evidence_span, _is_negated,
)
from .prompt_template import PROMPT_TEMPLATE

# -----------------------------------------------------------------------------
# Model Configuration
# -----------------------------------------------------------------------------
MODEL_PATH = Path(__file__).parent.parent / "models" / "google_medgemma-4b-it-Q4_K_M.gguf"
_model = None  # Lazy-loaded singleton


def _get_model():
    """Lazy-load MedGemma model (singleton)."""
    global _model
    if _model is None:
        try:
            from llama_cpp import Llama
            _model = Llama(
                model_path=str(MODEL_PATH),
                n_gpu_layers=-1,  # Offload all layers to GPU
                n_ctx=4096,       # Context window
                verbose=False,
            )
        except Exception as e:
            print(f"[WARN] Failed to load MedGemma model: {e}")
            return None
    return _model


# -----------------------------------------------------------------------------
# Refusal Guardrail
# -----------------------------------------------------------------------------
REFUSAL_TRIGGERS = ["should", "recommend", "advise", "prescribe", "diagnose"]


def _check_refusal(text: str) -> Optional[Dict[str, Any]]:
    """
    Refuse to answer clinical decision questions.
    Returns a refusal response dict if triggered, else None.
    """
    lower = text.lower()
    for trigger in REFUSAL_TRIGGERS:
        if f"{trigger} patient" in lower or f"{trigger} i " in lower or f"{trigger} the patient" in lower:
            return {
                "refusal": True,
                "message": "This tool drafts PA documentation only. It does not provide clinical recommendations.",
                "extraction_mode": "llm_refused",
            }
    return None


# -----------------------------------------------------------------------------
# JSON Parsing
# -----------------------------------------------------------------------------
def _parse_json_response(raw_output: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from model output.
    Handles markdown code blocks and stray text.
    """
    # Try to find JSON block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_output)
    if json_match:
        raw_output = json_match.group(1)
    
    # Find JSON object boundaries
    start = raw_output.find("{")
    end = raw_output.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    
    try:
        return json.loads(raw_output[start:end])
    except json.JSONDecodeError:
        return None

# -----------------------------------------------------------------------------
# Evidence Validation
# -----------------------------------------------------------------------------

# Minimum quote requirements to ensure meaningful provenance
MIN_QUOTE_LENGTH = 8  # characters
MIN_QUOTE_TOKENS = 2  # words


def _is_valid_quote_length(quote: str) -> bool:
    """
    Check if quote meets minimum length requirements.
    Accepts quotes that are either:
    - >= MIN_QUOTE_LENGTH characters, OR
    - >= MIN_QUOTE_TOKENS words, OR
    - contain a digit (e.g., "6 weeks", "x6")
    """
    if len(quote) >= MIN_QUOTE_LENGTH:
        return True
    if len(quote.split()) >= MIN_QUOTE_TOKENS:
        return True
    if any(c.isdigit() for c in quote):
        return True
    return False


def _find_quote_in_text(quote: str, text: str) -> tuple[int, str]:
    """
    Find quote in text. Uses word-boundary matching for short quotes
    to prevent false positives (e.g., "pt" in "symptoms").
    Returns (position, matched_text) or (-1, "") if not found.
    """
    # For short quotes (single token), use word-boundary matching
    if len(quote.split()) == 1:
        pattern = r'\b' + re.escape(quote) + r'\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.start(), text[match.start():match.end()]
        return -1, ""
    
    # For multi-token quotes, use case-insensitive substring search
    text_lower = text.lower()
    quote_lower = quote.lower()
    idx = text_lower.find(quote_lower)
    if idx != -1:
        # Return the actual text (preserving original case)
        return idx, text[idx:idx + len(quote)]
    
    return -1, ""


def _validate_evidence_spans(parsed: Dict[str, Any], note_text: str) -> Dict[str, Any]:
    """
    Validate that all evidence quotes are actual verbatim substrings of the note.
    
    - Rejects ultra-short quotes (< 8 chars AND single token AND no digits)
    - Uses word-boundary matching for single-token quotes
    - Uses substring matching for multi-token quotes
    - Recalculates start/end offsets from the actual match position
    
    Invalid evidence -> field nulled out, added to missing_evidence.
    """
    evidence = parsed.get("evidence", {})
    missing = list(parsed.get("missing_evidence", []))
    
    fields_to_check = ["symptoms_duration_weeks", "conservative_care_weeks", "treatments", "red_flags"]
    
    for field in fields_to_check:
        field_evidence = evidence.get(field, [])
        if not field_evidence:
            continue
        
        valid_evidence = []
        for ev in field_evidence:
            # Defensive: LLM sometimes returns strings instead of objects
            if isinstance(ev, str):
                ev = {"source": "note", "quote": ev}
            if not isinstance(ev, dict):
                continue
            quote = ev.get("quote", "")
            if not quote:
                continue
            
            # Reject ultra-short quotes (weak provenance)
            if not _is_valid_quote_length(quote):
                continue
            
            # Find actual position in note text
            idx, matched_text = _find_quote_in_text(quote, note_text)
            if idx != -1:
                valid_evidence.append({
                    "source": "note",
                    "start": idx,
                    "end": idx + len(matched_text),
                    "quote": matched_text
                })
        
        if valid_evidence:
            evidence[field] = valid_evidence
        else:
            evidence[field] = []
            # No valid evidence -> null out the field value and mark missing
            if field in parsed and parsed[field] is not None:
                if field not in missing:
                    missing.append(field)
                parsed[field] = None if field in ["symptoms_duration_weeks", "conservative_care_weeks"] else []
    
    parsed["evidence"] = evidence
    parsed["missing_evidence"] = missing
    return parsed


# -----------------------------------------------------------------------------
# Baseline-Boosted Red Flag Detection
# -----------------------------------------------------------------------------
def _boost_red_flags_from_baseline(parsed: Dict[str, Any], note_text: str) -> Dict[str, Any]:
    """
    Safety net: run baseline regex red flag detection and merge any flags
    the LLM missed. This is a union — LLM-detected flags are preserved,
    baseline only adds what was missed.
    """
    baseline_flags = _detect_red_flags(note_text)
    llm_flags = list(parsed.get("red_flags", []))

    # Find flags detected by baseline but missed by LLM
    missing_flags = [f for f in baseline_flags if f not in llm_flags]

    if not missing_flags:
        return parsed  # LLM caught everything, nothing to add

    # Merge missing flags
    merged_flags = sorted(set(llm_flags + missing_flags))
    parsed["red_flags"] = merged_flags
    parsed["red_flags_present"] = True

    # Synthesize evidence spans for baseline-detected flags
    evidence = parsed.get("evidence", {})
    existing_rf_evidence = list(evidence.get("red_flags", []))

    for flag in missing_flags:
        keywords = RED_FLAG_KEYWORDS.get(flag, [])
        for kw in keywords:
            span = _evidence_span(note_text, kw)
            if span:
                existing_rf_evidence.append(span)
                break  # one evidence span per flag is enough

    evidence["red_flags"] = existing_rf_evidence
    parsed["evidence"] = evidence

    return parsed


# -----------------------------------------------------------------------------
# Baseline-Boosted Conservative Care Detection
# -----------------------------------------------------------------------------
def _boost_conservative_care_from_baseline(parsed: Dict[str, Any], note_text: str) -> Dict[str, Any]:
    """
    Safety net: if LLM did not extract conservative_care_weeks, run baseline
    regex detection and inject the result if found.
    """
    if parsed.get("conservative_care_weeks") is not None:
        return parsed  # LLM already found a value

    baseline_weeks, matched_quote = _find_conservative_care_weeks(note_text)
    if baseline_weeks is None:
        return parsed  # baseline found nothing either

    parsed["conservative_care_weeks"] = baseline_weeks

    # Synthesize evidence span
    if matched_quote:
        evidence = parsed.get("evidence", {})
        span = _evidence_span(note_text, matched_quote)
        if span:
            evidence["conservative_care_weeks"] = [span]
            parsed["evidence"] = evidence

    # Remove from missing_evidence if it was listed there
    missing = parsed.get("missing_evidence", [])
    parsed["missing_evidence"] = [m for m in missing if m != "conservative_care_weeks"]

    return parsed


# -----------------------------------------------------------------------------
# Baseline-Boosted Treatment Detection
# -----------------------------------------------------------------------------
def _boost_treatments_from_baseline(parsed: Dict[str, Any], note_text: str) -> Dict[str, Any]:
    """
    Safety net: run baseline regex treatment detection and merge any
    treatments the LLM missed. Normalizes LLM display-name treatments
    to baseline category keys.
    """
    baseline_treats = _detect_treatments(note_text)  # returns keys like 'nsaids', 'pt'
    llm_treats = list(parsed.get("treatments", []))

    # Normalize LLM display names -> baseline keys
    llm_keys = set()
    for t in llm_treats:
        t_lower = t.lower().replace(" ", "_")
        # Direct key match
        if t_lower in TREATMENT_KEYWORDS:
            llm_keys.add(t_lower)
            continue
        # Check if the LLM name is a keyword value
        for key, kws in TREATMENT_KEYWORDS.items():
            if t.lower() in [kw.lower() for kw in kws]:
                llm_keys.add(key)
                break

    # Merge baseline-detected treatments the LLM missed
    missing_treats = [t for t in baseline_treats if t not in llm_keys]
    if missing_treats:
        merged = sorted(set(list(llm_keys) + missing_treats))
        parsed["treatments"] = merged
    elif llm_keys != set(llm_treats):
        # Normalize existing LLM treatment names to baseline keys
        parsed["treatments"] = sorted(llm_keys)
    # else: keep as-is

    return parsed


# -----------------------------------------------------------------------------
# Baseline-Boosted Evidence Spans
# -----------------------------------------------------------------------------
def _boost_evidence_spans_from_baseline(parsed: Dict[str, Any], note_text: str) -> Dict[str, Any]:
    """
    Enrich LLM evidence with additional keyword highlights from baseline.

    For each detected treatment/red flag category, scan the note for ALL
    matching keywords and add evidence spans the LLM didn't quote.
    Respects negation for red flags (won't highlight "Denies fever").
    """
    evidence = parsed.get("evidence", {})
    note_lower = note_text.lower()

    # --- Treatments: add spans for all matching keywords ---
    treatments = parsed.get("treatments", [])
    if treatments:
        existing_quotes = {sp.get("quote", "").lower() for sp in evidence.get("treatments", [])}
        extra_spans = []
        for treat in treatments:
            for kw in TREATMENT_KEYWORDS.get(treat, []):
                if kw.lower() not in existing_quotes:
                    span = _evidence_span(note_text, kw)
                    if span:
                        extra_spans.append(span)
                        existing_quotes.add(kw.lower())
        if extra_spans:
            evidence["treatments"] = list(evidence.get("treatments", [])) + extra_spans

    # --- Red flags: add spans for all non-negated matching keywords ---
    red_flags = parsed.get("red_flags", [])
    if red_flags:
        existing_quotes = {sp.get("quote", "").lower() for sp in evidence.get("red_flags", [])}
        extra_spans = []
        for flag in red_flags:
            for kw in RED_FLAG_KEYWORDS.get(flag, []):
                if kw.lower() not in existing_quotes:
                    idx = note_lower.find(kw.lower())
                    if idx != -1 and not _is_negated(note_lower, idx):
                        span = _evidence_span(note_text, kw)
                        if span:
                            extra_spans.append(span)
                            existing_quotes.add(kw.lower())
        if extra_spans:
            evidence["red_flags"] = list(evidence.get("red_flags", [])) + extra_spans

    parsed["evidence"] = evidence
    return parsed


# -----------------------------------------------------------------------------
# Main Extraction Function
# -----------------------------------------------------------------------------
def extract_facts_llm(note_text: str, retrieved_policy: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract structured facts using MedGemma via llama-cpp-python.
    
    Implements:
    - Refusal guardrail for clinical decision questions
    - Evidence span validation (quotes must be substrings)
    - Fallback to baseline on model/parse errors
    """
    # 1. Check refusal guardrail
    refusal = _check_refusal(note_text)
    if refusal:
        return refusal
    
    # 2. Load model
    model = _get_model()
    if model is None:
        print("[WARN] Model not available, falling back to baseline")
        result = extract_facts_baseline(note_text, retrieved_policy)
        result["extraction_mode"] = "llm_fallback_baseline"
        return result
    
    # 3. Build prompt using chat format
    user_message = PROMPT_TEMPLATE.format(
        note_text=note_text,
        policy_chunks_json=json.dumps(retrieved_policy, indent=2),
    )
    
    # 4. Call MedGemma using chat completion (proper Gemma format)
    try:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are a medical document extraction assistant. You ONLY output valid JSON, never code or explanations."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1024,
            temperature=0.1,  # Low temperature for consistent output
        )
        raw_output = response["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[WARN] Model inference failed: {e}, falling back to baseline")
        result = extract_facts_baseline(note_text, retrieved_policy)
        result["extraction_mode"] = "llm_fallback_baseline"
        return result
    
    # 5. Parse JSON response
    parsed = _parse_json_response(raw_output)
    if parsed is None:
        print(f"[WARN] Failed to parse JSON from model output, falling back to baseline")
        result = extract_facts_baseline(note_text, retrieved_policy)
        result["extraction_mode"] = "llm_fallback_baseline"
        return result
    
    # 6. Validate evidence spans
    validated = _validate_evidence_spans(parsed, note_text)
    
    # 7. Boost red flags from baseline (safety net for missed detections)
    validated = _boost_red_flags_from_baseline(validated, note_text)

    # 8. Boost conservative care from baseline (safety net for missed detections)
    validated = _boost_conservative_care_from_baseline(validated, note_text)

    # 9. Boost treatments from baseline (safety net for missed detections)
    validated = _boost_treatments_from_baseline(validated, note_text)

    # 10. Boost evidence spans from baseline (fill highlight gaps)
    validated = _boost_evidence_spans_from_baseline(validated, note_text)
    
    # 10. Ensure required fields exist
    validated.setdefault("symptoms_duration_weeks", None)
    validated.setdefault("conservative_care_weeks", None)
    validated.setdefault("treatments", [])
    validated.setdefault("red_flags", [])
    validated.setdefault("red_flags_present", bool(validated.get("red_flags")))
    validated.setdefault("evidence", {})
    validated.setdefault("missing_evidence", [])
    validated["extraction_mode"] = "llm"
    
    return validated
