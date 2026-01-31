import json
from pathlib import Path
from typing import Dict, Any

from .policy_store import load_policy_store
from .retrieval import retrieve_policy_chunks
from .extraction_baseline import extract_facts_baseline
from .extraction_llm import extract_facts_llm
from .checklist import build_checklist
from .assemble import write_packet_bundle

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "policy_demo_spine_mri.json"

def run_pipeline(case_path: Path, out_dir: Path, mode: str = "baseline") -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    case = json.loads(case_path.read_text(encoding="utf-8"))

    # Load policy store (chunked text)
    policy_store = load_policy_store(DEFAULT_POLICY_PATH)

    # Retrieve relevant policy chunks for the requested exam
    query = f"{case.get('exam_request', {}).get('procedure', '')} criteria conservative care red flags"
    retrieved = retrieve_policy_chunks(policy_store, query=query, k=3)

    # Extract structured facts from note text
    note_text = case.get("note_text", "")

    if mode == "baseline":
        extracted = extract_facts_baseline(note_text=note_text, retrieved_policy=retrieved)
    else:
        extracted = extract_facts_llm(note_text=note_text, retrieved_policy=retrieved)

    # Build checklist (deterministic)
    checklist = build_checklist(extracted)

    # Assemble outputs
    bundle = {
        "case": case,
        "retrieved_policy": retrieved,
        "extracted": extracted,
        "checklist": checklist,
    }
    write_packet_bundle(bundle=bundle, out_dir=out_dir)

    # Console summary for demo recording
    print(f"[PA-Trace] Case: {case.get('case_id')}")
    print(f"[PA-Trace] Retrieved policy chunks: {[c['chunk_id'] for c in retrieved]}")
    print(f"[PA-Trace] Decision: {checklist['overall_status']} | Missing: {checklist['missing_evidence']}")
    print(f"[PA-Trace] Wrote bundle to: {out_dir.resolve()}")
    return bundle
