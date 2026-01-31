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

Requires [Task](https://taskfile.dev) (`go install github.com/go-task/task/v3/cmd/task@latest`).

```bash
task deps              # Create venv + install project
task model             # Download MedGemma GGUF (~2.5GB)
MODE=llm task run      # Run with MedGemma on case_01
MODE=llm task eval     # Evaluate all 10 cases
```

Open the outputs:
- `runs/case_01/highlights.html` — evidence spans highlighted in clinical note
- `runs/case_01/packet.md` — human-readable PA packet draft

### Baseline (no LLM)
```bash
task run               # Uses regex/keyword extraction
task eval              # Evaluate baseline on all cases
```

### Manual commands (escape hatch)
```bash
python -m pa_trace run --case cases/case_01.json --out runs/case_01 --mode llm
python -m pa_trace eval --cases cases --gold cases/gold_labels.json --out runs/eval --mode llm
```

## Model Setup (MedGemma)

**Preferred:** Use `task model` (idempotent, downloads if missing).

**Manual:** Download the GGUF from Hugging Face:
```bash
huggingface-cli download google/medgemma-4b-it-gguf \
  google_medgemma-4b-it-Q4_K_M.gguf --local-dir models/
```

### Requirements
- **GPU (recommended):** ~6GB VRAM with CUDA-enabled `llama-cpp-python`
- **CPU fallback:** Works but slow (~2-3 min per case vs ~10s on GPU)
- **First run:** Model load takes ~10-20s; subsequent inferences are faster

### llama-cpp-python installation

The default `pip install llama-cpp-python` builds CPU-only. For CUDA:
```bash
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --force-reinstall --no-cache-dir
```
See [llama-cpp-python docs](https://github.com/abetlen/llama-cpp-python#installation) for other backends (Metal, ROCm, Vulkan).

## Expected Results

On the 10-case synthetic eval set:

| Metric | Expected |
|--------|----------|
| `symptoms_duration_weeks` | ~0.90 |
| `conservative_care_weeks` | ~0.90 |
| `red_flags_present` | ~0.70 |
| `decision_accuracy` | ~0.60–0.70 |
| `provenance_valid_rate` | 1.00 |
| `abstention_precision` | 1.00 |

> **Note:** Decision accuracy may vary slightly run-to-run due to stochastic LLM inference.
> Provenance validity should remain 1.0 — all evidence spans are validated as substrings of the source text.

## Policy text
For demo purposes we ship a *paraphrased* policy snippet in `policies/policy_demo_spine_mri.json`.
For a real submission, replace it with a **public payer guideline excerpt** you can cite, chunked into JSON.

## License
MIT for this starter scaffold (your project can choose differently).
