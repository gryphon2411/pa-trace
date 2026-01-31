# PA-Trace (Starter) — UI-less Hackathon MVP

This is a starter scaffold for an **agentic prior authorization (PA) packet drafter** demo:
**clinic note + imaging order + payer criteria text → filled PA packet draft + criteria checklist + evidence tracing**.

## What this is (and isn't)
- ✅ A *demo / hackathon prototype* focused on **documentation assembly**, not clinical decision-making.
- ✅ Works with **synthetic** notes (no PHI).
- ✅ Produces a "packet bundle" folder per run:
  - `packet.json`, `checklist.json`, `provenance.json`, `packet.md`, `highlights.html`
- ❌ Not a medical device.
- ❌ Not a payer portal integration.
- ❌ Not autonomous diagnosis/treatment.

## Quickstart
```bash
python -m pa_trace run --case cases/case_01.json --out runs/case_01
python -m pa_trace run --case cases/case_06.json --out runs/case_06
python -m pa_trace eval --cases cases --gold cases/gold_labels.json --out runs/eval
```

Open:
- `runs/case_01/highlights.html`
- `runs/case_01/packet.md`

## How to swap in an LLM (MedGemma, etc.)
This scaffold includes:
- a **baseline extractor** (regex/keywords), and
- a **prompt template** for strict JSON + evidence spans.

Wire your model in `pa_trace/extraction_llm.py` and choose mode:
```bash
python -m pa_trace run --case cases/case_01.json --out runs/case_01 --mode llm
```

## Policy text
For demo purposes we ship a *paraphrased* policy snippet in `policies/policy_demo_spine_mri.json`.
For a real submission, replace it with a **public payer guideline excerpt** you can cite, chunked into JSON.

## License
MIT for this starter scaffold (your project can choose differently).
