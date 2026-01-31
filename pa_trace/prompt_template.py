PROMPT_TEMPLATE = r"""
You are extracting structured fields for a prior-authorization (PA) packet draft.
You MUST follow these rules:

1) Output MUST be valid JSON (no markdown, no extra keys).
2) For every non-null field you output, you MUST include at least one evidence span
   pointing to the exact substring in the NOTE or POLICY chunks.
3) If you cannot find evidence, output null/empty and list it under missing_evidence.

Input NOTE (string):
{note_text}

Retrieved POLICY CHUNKS (array of objects with chunk_id,text):
{policy_chunks_json}

Return JSON with this schema:
{{
  "symptoms_duration_weeks": <int|null>,
  "conservative_care_weeks": <int|null>,
  "treatments": <array of strings>,
  "red_flags": <array of strings>,
  "red_flags_present": <bool>,
  "evidence": {{
     "symptoms_duration_weeks": [{{"source":"note","start":<int>,"end":<int>,"quote":"..."}}] | [],
     "conservative_care_weeks": [{{...}}] | [],
     "treatments": [{{...}}] | [],
     "red_flags": [{{...}}] | []
  }},
  "missing_evidence": <array of strings>,
  "extraction_mode": "llm"
}}

Allowed red_flags values: ["cauda_equina","progressive_neuro_deficit","cancer","infection","fracture_trauma"]
Allowed treatments values: ["pt","nsaids","home_exercise","chiropractic","steroid","injection"]
"""
