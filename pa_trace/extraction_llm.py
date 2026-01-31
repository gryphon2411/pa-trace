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

from .extraction_baseline import extract_facts_baseline
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
def _validate_evidence_spans(parsed: Dict[str, Any], note_text: str) -> Dict[str, Any]:
    """
    Validate that all evidence quotes are actual substrings of the note.
    Invalid evidence -> field set to null, added to missing_evidence.
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
            quote = ev.get("quote", "")
            if quote and quote in note_text:
                valid_evidence.append(ev)
            else:
                # Quote not found in note - mark as missing
                if field not in missing:
                    missing.append(field)
        
        if valid_evidence:
            evidence[field] = valid_evidence
        else:
            evidence[field] = []
            # No valid evidence -> null out the field value
            if field in parsed and parsed[field] is not None:
                if field not in missing:
                    missing.append(field)
                parsed[field] = None if field in ["symptoms_duration_weeks", "conservative_care_weeks"] else []
    
    parsed["evidence"] = evidence
    parsed["missing_evidence"] = missing
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
    
    # 7. Ensure required fields exist
    validated.setdefault("symptoms_duration_weeks", None)
    validated.setdefault("conservative_care_weeks", None)
    validated.setdefault("treatments", [])
    validated.setdefault("red_flags", [])
    validated.setdefault("red_flags_present", bool(validated.get("red_flags")))
    validated.setdefault("evidence", {})
    validated.setdefault("missing_evidence", [])
    validated["extraction_mode"] = "llm"
    
    return validated
