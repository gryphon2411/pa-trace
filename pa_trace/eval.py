import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .pipeline import run_pipeline

FIELDS = ["symptoms_duration_weeks", "conservative_care_weeks", "red_flags_present"]

def _load_cases(cases_dir: Path) -> List[Path]:
    return sorted([p for p in cases_dir.glob("case_*.json") if p.is_file()])

def _validate_provenance(case: Dict[str, Any], bundle: Dict[str, Any]) -> Tuple[int,int]:
    """
    Returns (valid_evidence_count, total_evidence_count) where "valid" means
    quote is a substring of the declared source text.
    """
    note = case.get("note_text", "")
    policy_chunks = {c["chunk_id"]: c["text"] for c in bundle.get("retrieved_policy", [])}
    evidence = bundle.get("extracted", {}).get("evidence", {})
    valid = 0
    total = 0
    for key, spans in evidence.items():
        for sp in spans:
            total += 1
            q = sp.get("quote", "")
            src = sp.get("source")
            if not q:
                continue
            if src == "note" and q in note:
                valid += 1
            elif src == "policy":
                cid = sp.get("chunk_id")
                if cid and cid in policy_chunks and q in policy_chunks[cid]:
                    valid += 1
    return valid, total

def run_eval(cases_dir: Path, gold_path: Path, out_dir: Path, mode: str = "baseline") -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    case_paths = _load_cases(cases_dir)

    y_true = {f: [] for f in FIELDS}
    y_pred = {f: [] for f in FIELDS}
    decision_true = []
    decision_pred = []

    prov_valid = 0
    prov_total = 0

    for cp in case_paths:
        case = json.loads(cp.read_text(encoding="utf-8"))
        case_id = case["case_id"]
        bundle = run_pipeline(cp, out_dir / case_id, mode=mode)

        ex = bundle["extracted"]
        chk = bundle["checklist"]

        g = gold[case_id]

        for f in FIELDS:
            y_true[f].append(g.get(f))
            y_pred[f].append(ex.get(f))

        decision_true.append(g.get("expected_status"))
        decision_pred.append(chk.get("overall_status"))

        v,t = _validate_provenance(case, bundle)
        prov_valid += v
        prov_total += t

    def acc(a,b):
        n = len(a)
        return sum(1 for i in range(n) if a[i] == b[i]) / n if n else 0.0

    metrics = {
        "mode": mode,
        "n_cases": len(case_paths),
        "field_accuracy": {f: acc(y_true[f], y_pred[f]) for f in FIELDS},
        "decision_accuracy": acc(decision_true, decision_pred),
        "provenance_valid_rate": (prov_valid / prov_total) if prov_total else None,
    }

    # Abstention precision on UNKNOWN cases
    unknown_idx = [i for i, d in enumerate(decision_true) if d == "UNKNOWN"]
    if unknown_idx:
        abstain_correct = sum(1 for i in unknown_idx if decision_pred[i] == "UNKNOWN")
        metrics["abstention_precision_on_unknown"] = abstain_correct / len(unknown_idx)
    else:
        metrics["abstention_precision_on_unknown"] = None

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    report = []
    report.append("# PA-Trace Evaluation Report\n")
    report.append(f"- Mode: {mode}")
    report.append(f"- Cases: {metrics['n_cases']}")
    report.append("\n## Field accuracy")
    for f, v in metrics["field_accuracy"].items():
        report.append(f"- {f}: {v:.2f}")
    report.append(f"\n## Decision accuracy\n- {metrics['decision_accuracy']:.2f}")
    if metrics["provenance_valid_rate"] is not None:
        report.append(f"\n## Provenance validity rate\n- {metrics['provenance_valid_rate']:.2f}")
    if metrics.get("abstention_precision_on_unknown") is not None:
        report.append(f"\n## Abstention precision (on UNKNOWN gold cases)\n- {metrics['abstention_precision_on_unknown']:.2f}")
    (out_dir / "eval_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"[PA-Trace] Eval complete. Metrics written to: {out_dir.resolve()}")
    return metrics
