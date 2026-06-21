#!/usr/bin/env python3
"""Run a small prompt/model quality eval for infra-ingest."""

import argparse
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from infra_ingest.llm_client import build_llm_config_from_env
from infra_ingest.pipeline import build_llm_output


class EvalConsole:
    def log(self, *args, **kwargs):
        return None


def load_jsonl(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def score_note(note, expected_terms, expected_evidence):
    rendered = json.dumps(note, ensure_ascii=False)
    term_hits = sum(1 for term in expected_terms if term in rendered)
    evidence_hits = sum(1 for item in expected_evidence if item in rendered)
    takeaways = note.get("takeaways", [])
    evidence_coverage = 0.0
    if takeaways:
        evidence_coverage = sum(1 for item in takeaways if item.get("evidence")) / len(takeaways)
    return {
        "term_recall": round(term_hits / max(len(expected_terms), 1), 3),
        "evidence_recall": round(evidence_hits / max(len(expected_evidence), 1), 3),
        "takeaway_evidence_coverage": round(evidence_coverage, 3),
        "quiz_count": len(note.get("quiz", [])),
        "atomic_note_count": len(note.get("atomic_notes", [])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run mini evals across models and prompt types.")
    parser.add_argument("--eval-file", default=str(ROOT_DIR / "evals" / "mini_eval.jsonl"))
    parser.add_argument("--models", default=os.getenv("EVAL_MODELS", ""))
    parser.add_argument("--output", default=str(ROOT_DIR / "evals" / "latest_results.jsonl"))
    args = parser.parse_args(argv)

    config = build_llm_config_from_env()
    if not config.get("api_key"):
        raise SystemExit("Missing LLM_API_KEY or OPENAI_API_KEY; cannot run model eval.")

    models = [item.strip() for item in args.models.split(",") if item.strip()] or [config["model"]]
    cases = load_jsonl(args.eval_file)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for model in models:
            config_for_model = dict(config, model=model)
            for case in cases:
                try:
                    note = build_llm_output(
                        case["input"],
                        config_for_model,
                        EvalConsole(),
                        material_type=case.get("material_type", "auto"),
                        glossary_terms=case.get("expected_terms", []),
                    )
                    result = {
                        "id": case["id"],
                        "model": model,
                        "material_type": case.get("material_type", "auto"),
                        "ok": True,
                        "scores": score_note(
                            note,
                            case.get("expected_terms", []),
                            case.get("expected_evidence", []),
                        ),
                    }
                except Exception as exc:
                    result = {
                        "id": case["id"],
                        "model": model,
                        "material_type": case.get("material_type", "auto"),
                        "ok": False,
                        "error": str(exc),
                    }
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(json.dumps(result, ensure_ascii=False))

    print(f"Wrote eval results to {output_path}")


if __name__ == "__main__":
    main()
