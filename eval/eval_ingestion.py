"""
eval_ingestion.py
Level 1 eval — DataIngestor sheet classification accuracy.

DataIngestor passes sheet name + 15 rows of content to Haiku (LLM-based).
Because classification is LLM-based, this eval:
  - Runs each fixture N times (default 10) to measure variance
  - Reports per-sheet accuracy as a fraction across runs, not a single pass/fail
  - Flags any sheet that fails even once (reliability gap)

Pass criterion: ≥95% accuracy across all sheets and runs.
Any sheet below 100% across runs is flagged for prompt investigation.

Run:
    uv run python eval/eval_ingestion.py           # 10 runs (default)
    uv run python eval/eval_ingestion.py --runs 20
    uv run python eval/eval_ingestion.py --runs 1  # quick smoke test

Results appended to: eval/results/ingestion_results.json
"""

import json
import sys
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from data_ingestor import DataIngestor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR  = Path(__file__).parent / "results"
RESULTS_FILE = RESULTS_DIR / "ingestion_results.json"

DEFAULT_RUNS = 10


# ---------------------------------------------------------------------------
# Ground truth
# Maps: case_name → { sheet_name → expected_category }
# Sheet names match exactly what generate_fixtures.py creates.
# "irrelevant" sheets are also listed — we verify Haiku marks them correctly.
# ---------------------------------------------------------------------------

GROUND_TRUTH: dict[str, dict[str, str]] = {
    # Sheet classification ground truth redacted from public version.
    # These encode expected category labels per sheet per fixture.
    # Contact the author for details.
}


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_once(case_name: str, cam_path: Path) -> dict[str, str]:
    """
    Run DataIngestor on one fixture once.
    Returns: { sheet_name → classified_category }
    Sheets classified as "irrelevant" are not in cran_data (DataIngestor drops them),
    so we track them separately via the raw classifications dict.
    """
    ingestor = DataIngestor()

    # We need the raw classifications (including irrelevant) not just cran_data.
    # Call the internals directly: sample sheets → classify → return classifications.
    import pandas as pd

    workbook = pd.ExcelFile(str(cam_path))
    sheet_samples = {}
    for sheet_name in workbook.sheet_names:
        df = pd.read_excel(str(cam_path), sheet_name=sheet_name, header=None)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        sheet_samples[sheet_name] = {
            "columns": [ingestor.serialize_key(col) for col in df.columns],
            "row_count": len(df),
            "preview": ingestor.serialize_records(df.head(15).to_dict(orient="records")),
        }

    classifications = ingestor.classify_sheets_with_llm(sheet_samples)
    return classifications  # { sheet_name → category_string }


# ---------------------------------------------------------------------------
# Multi-run aggregation
# ---------------------------------------------------------------------------

def run_case(case_name: str, cam_path: Path, n_runs: int) -> dict:
    """Run ingestion N times on one fixture and aggregate results."""
    result = {
        "case":        case_name,
        "n_runs":      n_runs,
        "sheet_stats": {},   # sheet_name → { correct: int, total: int, failures: list }
        "overall_accuracy": 0.0,
        "passed":      False,
        "error":       None,
    }

    expected = GROUND_TRUTH.get(case_name, {})

    # Initialise stats
    for sheet_name in expected:
        result["sheet_stats"][sheet_name] = {
            "expected": expected[sheet_name],
            "correct":  0,
            "total":    0,
            "failures": [],  # list of wrong categories seen
        }

    try:
        for run_i in range(n_runs):
            classifications = run_once(case_name, cam_path)

            for sheet_name, expected_cat in expected.items():
                stats = result["sheet_stats"][sheet_name]
                stats["total"] += 1
                actual = classifications.get(sheet_name, "NOT_FOUND")
                if actual == expected_cat:
                    stats["correct"] += 1
                else:
                    stats["failures"].append(actual)

            sys.stdout.write(f"\r  {case_name}: run {run_i + 1}/{n_runs}")
            sys.stdout.flush()

        print()  # newline after progress

        # Aggregate accuracy
        total_correct = sum(s["correct"] for s in result["sheet_stats"].values())
        total_evals   = sum(s["total"]   for s in result["sheet_stats"].values())
        result["overall_accuracy"] = round(total_correct / total_evals, 4) if total_evals else 0.0

        # Add per-sheet accuracy fraction
        for sheet_name, stats in result["sheet_stats"].items():
            stats["accuracy"] = round(stats["correct"] / stats["total"], 4) if stats["total"] else 0.0

        result["passed"] = result["overall_accuracy"] >= 0.95

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(results: list[dict], n_runs: int):
    all_correct = sum(
        s["correct"]
        for r in results
        for s in r["sheet_stats"].values()
    )
    all_total = sum(
        s["total"]
        for r in results
        for s in r["sheet_stats"].values()
    )
    overall = (all_correct / all_total * 100) if all_total else 0

    print("\n" + "=" * 65)
    print(f"LEVEL 1 EVAL — INGESTION CLASSIFICATION  ({n_runs} runs per case)")
    print("=" * 65)

    for r in results:
        if r["error"]:
            print(f"\n  [ERROR] {r['case']}")
            print(f"    {r['error'][:300]}")
            continue

        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n  [{status}] {r['case']}  "
              f"(overall accuracy: {r['overall_accuracy']:.1%})")

        for sheet_name, stats in r["sheet_stats"].items():
            acc = stats["accuracy"]
            tick = "[+]" if acc == 1.0 else ("[-]" if acc >= 0.8 else "[X]")
            failure_str = ""
            if stats["failures"]:
                unique_failures = list(set(stats["failures"]))
                failure_str = f"  ← misclassified as: {unique_failures}"
            print(f"    {tick} {sheet_name:<28s} "
                  f"expected={stats['expected']:<22s} "
                  f"accuracy={acc:.0%}{failure_str}")

    print("\n" + "-" * 65)
    print(f"Overall accuracy : {overall:.1f}%  ({all_correct}/{all_total} correct)")
    print(f"Pass threshold   : 95%")
    print(f"Status           : {'PASS' if overall >= 95 else 'FAIL'}")

    # Flag any sheet below 100%
    unreliable = [
        (r["case"], sheet_name, stats["accuracy"])
        for r in results
        for sheet_name, stats in r["sheet_stats"].items()
        if stats["accuracy"] < 1.0 and not r["error"]
    ]
    if unreliable:
        print("\nSheets below 100% reliability (investigate prompt):")
        for case, sheet, acc in unreliable:
            print(f"  {case} / {sheet:<28s} {acc:.0%}")

    print("=" * 65)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Level 1 eval — ingestion classification")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                        help=f"Number of runs per fixture (default: {DEFAULT_RUNS})")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for case_name in sorted(GROUND_TRUTH.keys()):
        cam_path = FIXTURES_DIR / case_name / "cam.xlsx"
        if not cam_path.exists():
            print(f"SKIP {case_name}: fixture not found. Run generate_fixtures.py first.")
            continue
        print(f"\nRunning: {case_name}  ({args.runs} runs) ...")
        result = run_case(case_name, cam_path, args.runs)
        results.append(result)

    if not results:
        print("No fixtures found. Run generate_fixtures.py first.")
        return

    print_summary(results, args.runs)

    run_record = {
        "run_at":  datetime.utcnow().isoformat() + "Z",
        "level":   1,
        "n_runs":  args.runs,
        "results": results,
    }
    existing = []
    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text())
        except Exception:
            existing = []
    existing.append(run_record)
    RESULTS_FILE.write_text(json.dumps(existing, indent=2))
    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
