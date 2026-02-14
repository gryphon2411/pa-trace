PROMPT_TEMPLATE = r"""
You are extracting structured fields for a prior-authorization (PA) packet draft.
You MUST follow these rules:

1) Output MUST be valid JSON (no markdown, no extra keys).
2) For every non-null field you output, you MUST include at least one evidence span
   pointing to the exact substring in the NOTE or POLICY chunks.
3) If you cannot find evidence, output null/empty and list it under missing_evidence.

EVIDENCE REQUIREMENTS (STRICT):
- Every evidence.quote MUST be copied VERBATIM from note_text (exact substring match).
- Do NOT expand or normalize abbreviations inside evidence.quote.
- Prefer quotes with enough context: at least 2 words or >= 10 characters.
  Good: "6 weeks of physical therapy", "failed PT x 6 weeks"
  Bad: "PT", "6"
- If you cannot find an exact supporting quote in note_text, omit the evidence
  and mark the field under missing_evidence.

FIELD-SPECIFIC GUIDANCE:
- symptoms_duration_weeks: Extract duration of symptoms (e.g., "8 weeks", "3 months").
  Do NOT confuse with patient age (e.g., "45-year-old" is age, not duration).
  If onset is acute/sudden with no stated duration, mark as missing_evidence.
- conservative_care_weeks: Extract duration of conservative treatment attempted.
  Must be explicit (e.g., "6 weeks of PT", "failed 8 weeks of therapy").
  Convert months to weeks: "two months" = 8 weeks, "3 months" = 12 weeks.
  Word-form numbers are valid: "two months" = 2 months = 8 weeks.
  If multiple treatments have different durations, use the LONGEST duration.
  Example: "home exercises for two months and PT for 4 weeks" -> 8 weeks (max of 8, 4).
- acute_onset: If the note states "acute" or "since this morning", set symptoms_duration_weeks to 0.
- treatments: Extract ONLY therapies/medications tried. 
  Do NOT include symptoms (e.g., "incontinence"), exam findings (e.g., "weakness"), or diagnoses.
  If a treatment is NOT mentioned in the text, do NOT list it.

RED FLAG DETECTION (HIGHEST PRIORITY):
Red flags indicate serious pathology that BYPASSES conservative care requirements.
You MUST detect ALL red flags present in the note. This is the most critical extraction task.

Each red flag category and its clinical indicators:
- "cauda_equina": saddle anesthesia, urinary retention, urinary incontinence,
  bowel dysfunction, bladder dysfunction, bowel or bladder changes
- "progressive_neuro_deficit": progressive weakness, worsening weakness, foot drop,
  new neurological deficit, increasing numbness
- "cancer": history of cancer, malignancy, unexplained weight loss, prior malignancy
- "infection": fever with spine pain, IV drug use, discitis, osteomyelitis,
  spinal infection, recent infection
- "fracture_trauma": trauma, fall, fell, motor vehicle accident, fracture,
  significant injury, acute trauma

IMPORTANT — Do NOT confuse symptoms with treatments:
  WRONG: "urinary retention" -> treatments (it is a symptom / red flag indicator)
  WRONG: "weakness" -> treatments (it is a clinical finding / red flag indicator)
  RIGHT: "urinary retention" -> evidence for red_flag "cauda_equina"
  RIGHT: "progressive weakness" -> evidence for red_flag "progressive_neuro_deficit"
  RIGHT: "history of cancer" -> evidence for red_flag "cancer"
  RIGHT: "fell from a ladder" -> evidence for red_flag "fracture_trauma"

If ANY red flag indicator is found, set red_flags_present to true and list
the matching category in the red_flags array.

COMMON ERRORS TO AVOID:
- Do NOT extract patient age as symptom duration.
  WRONG: "29-year-old" -> symptoms_duration_weeks: 29
  RIGHT: If no duration stated, output null and list in missing_evidence.

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
