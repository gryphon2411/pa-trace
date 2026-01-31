import json
from typing import Dict, Any, List

from .extraction_baseline import extract_facts_baseline
from .prompt_template import PROMPT_TEMPLATE

def extract_facts_llm(note_text: str, retrieved_policy: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Placeholder: wire your LLM here.

    Recommended behavior:
    - Build prompt using PROMPT_TEMPLATE
    - Call your model to produce STRICT JSON
    - Validate evidence spans before returning
    - If validation fails, fallback to abstain or baseline

    For now, we fallback to baseline to keep the scaffold runnable.
    """
    # ---- Replace the following with your LLM call ----
    extracted = extract_facts_baseline(note_text=note_text, retrieved_policy=retrieved_policy)
    extracted["extraction_mode"] = "llm_stub_baseline"
    extracted["missing_evidence"] = []
    return extracted
