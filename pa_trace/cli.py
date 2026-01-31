import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline
from .eval import run_eval

def main():
    parser = argparse.ArgumentParser(prog="pa-trace", description="PA-Trace UI-less MVP")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run pipeline on a single case")
    p_run.add_argument("--case", required=True, help="Path to case JSON")
    p_run.add_argument("--out", required=True, help="Output directory")
    p_run.add_argument("--mode", choices=["baseline", "llm"], default="baseline", help="Extraction mode")

    p_eval = sub.add_parser("eval", help="Evaluate pipeline on a folder of cases")
    p_eval.add_argument("--cases", required=True, help="Folder with case_*.json")
    p_eval.add_argument("--gold", required=True, help="Gold labels JSON")
    p_eval.add_argument("--out", required=True, help="Output directory")
    p_eval.add_argument("--mode", choices=["baseline", "llm"], default="baseline", help="Extraction mode")

    args = parser.parse_args()

    if args.cmd == "run":
        run_pipeline(case_path=Path(args.case), out_dir=Path(args.out), mode=args.mode)
    elif args.cmd == "eval":
        run_eval(cases_dir=Path(args.cases), gold_path=Path(args.gold), out_dir=Path(args.out), mode=args.mode)

if __name__ == "__main__":
    main()
