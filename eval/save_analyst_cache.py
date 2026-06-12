"""
save_analyst_cache.py
Runs the Analyst Agent on all fixtures and saves outputs to
eval/fixtures/<case>/analyst_output.json.

Use this to pre-populate the cache before running eval_researcher.py,
or to regenerate the cache after prompt changes without re-running
the full Level 2 eval.

Does NOT score outputs — use eval_analyst.py for scoring.
Does NOT run the Researcher — use eval_researcher.py for that.

Run:
    uv run python eval/save_analyst_cache.py
    uv run python eval/save_analyst_cache.py case_01_sparse_data  # single case
"""

import json
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_ingestor import DataIngestor
from agents import Analyst

FIXTURES_DIR = Path(__file__).parent / "fixtures"

ALL_CASES = [
    "case_01_sparse_data",
    "case_02_messy_names",
    "case_03_combined_sheet",
    "case_04_late_data",
    "case_05_generic_names",
]


def cache_case(case_name: str) -> bool:
    cam_path = FIXTURES_DIR / case_name / "cam_anonymised.xlsx"
    if not cam_path.exists():
        print(f"  SKIP: {case_name} — fixture not found. Run generate_fixtures.py first.")
        return False

    try:
        ingestor = DataIngestor()
        result = ingestor.excel_ingestor({"excel_path": str(cam_path)})
        cran_data = result["cran_data"]
        entity_mapping = result["entity_mapping"]

        analyst = Analyst()
        output = analyst.analyst({"cran_data": cran_data})

        cache_data = {
            "case": case_name,
            "trends": [t.model_dump() for t in output["trends"]],
            "queries": [q.model_dump() for q in output["queries"]],
            "director_names": output["director_names"],
            "related_companies": output["related_companies"],
            "entity_mapping": entity_mapping,  # stored so eval_researcher can restore names
        }
        cache_path = cam_path.parent / "analyst_output.json"
        cache_path.write_text(json.dumps(cache_data, indent=2))
        print(f"  Saved: {cache_path}")
        print(f"    Trends: {len(output['trends'])}  "
              f"Queries: {len(output['queries'])}  "
              f"Directors: {len(output['director_names'] or [])}  "
              f"Related cos: {len(output['related_companies'] or [])}")
        return True

    except Exception as e:
        print(f"  ERROR on {case_name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def main():
    # Optional: run single case if passed as arg
    target_cases = sys.argv[1:] if len(sys.argv) > 1 else ALL_CASES

    invalid = [c for c in target_cases if c not in ALL_CASES]
    if invalid:
        print(f"Unknown cases: {invalid}")
        print(f"Valid cases: {ALL_CASES}")
        sys.exit(1)

    print(f"Caching analyst output for: {target_cases}\n")
    results = {case: cache_case(case) for case in target_cases}

    passed = sum(v for v in results.values())
    print(f"\nDone. {passed}/{len(results)} cases cached successfully.")


if __name__ == "__main__":
    main()
