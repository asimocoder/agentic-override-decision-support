"""
eval_analyst.py
Level 2 eval — Analyst Agent output quality.

Runs the Analyst Agent on each fixture and scores:
  - Anomaly recall: expected HIGH-severity signals detected (keyword check)
  - Entity extraction: director_names and related_companies completeness
  - Query generation: minimum query count

Caches analyst outputs to eval/fixtures/<case>/analyst_output.json
for use by eval_researcher.py.

Run:
    uv run python eval/eval_analyst.py
    uv run python eval/eval_analyst.py case_01_sparse_data  # single case

Results appended to eval/results/analyst_results.json.
"""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from data_ingestor import DataIngestor
from agents import Analyst, AnalystOutput, Severity, QueryCategory

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR  = Path(__file__).parent / "results"
RESULTS_FILE = RESULTS_DIR / "analyst_results.json"

ALL_CASES = [
    "case_01_sparse_data",
    "case_02_messy_names",
    "case_03_combined_sheet",
    "case_04_late_data",
    "case_05_generic_names",
]


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

EXPECTED_SIGNALS: dict[str, list[dict]] = {
    # Ground truth signals redacted from public version.
    # These encode domain-specific anomaly patterns, keywords, and severity
    # expectations for each synthetic CAM fixture.
    # Contact the author for details.
}

EXPECTED_ENTITIES: dict[str, dict] = {
    # Entity ground truth redacted from public version.
    # These encode synthetic director names and related company names per fixture.
    # Contact the author for details.
}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_signal(signal: dict, analyst_output: AnalystOutput) -> dict:
    if not signal["keywords"]:
        return {
            "id":               signal["id"],
            "description":      signal["description"],
            "expected_severity": signal["expected_severity"],
            "keyword_hit":      None,
            "note":             signal.get("note", "Manual scoring required"),
        }
    all_text = " ".join(
        f"{t.observation} {t.supporting_data}" for t in analyst_output.trends
    ).lower()
    hit = any(kw.lower() in all_text for kw in signal["keywords"])
    return {
        "id":               signal["id"],
        "description":      signal["description"],
        "expected_severity": signal["expected_severity"],
        "keyword_hit":      hit,
        "note":             "",
    }


def _score_entities(expected: dict, actual: AnalystOutput) -> dict:
    exp_dir = {n.lower() for n in expected.get("director_names", [])}
    exp_co  = {n.lower() for n in expected.get("related_companies", [])}
    act_dir = {n.lower() for n in (actual.director_names or [])}
    act_co  = {n.lower() for n in (actual.related_companies or [])}

    dir_recall = len(exp_dir & act_dir) / len(exp_dir) if exp_dir else 1.0
    co_recall  = len(exp_co  & act_co)  / len(exp_co)  if exp_co  else 1.0

    return {
        "directors": {
            "expected": sorted(expected.get("director_names", [])),
            "actual":   sorted(actual.director_names or []),
            "recall":   round(dir_recall, 2),
            "missed":   sorted(exp_dir - act_dir),
        },
        "related_companies": {
            "expected": sorted(expected.get("related_companies", [])),
            "actual":   sorted(actual.related_companies or []),
            "recall":   round(co_recall, 2),
            "missed":   sorted(exp_co - act_co),
        },
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_case(case_name: str, cam_path: Path) -> dict:
    result = {
        "case":                  case_name,
        "trends_generated":      0,
        "queries_generated":     0,
        "signals":               [],
        "entities":              {},
        "raw_trends":            [],
        "raw_queries":           [],
        "passed_entity_recall":  False,
        "error":                 None,
    }

    try:
        ingestor = DataIngestor()
        ingestor_result = ingestor.excel_ingestor({"excel_path": str(cam_path)})
        cran_data     = ingestor_result["cran_data"]
        entity_mapping = ingestor_result["entity_mapping"]
        # Reverse mapping: placeholder -> real name (for scoring against EXPECTED_ENTITIES)
        reverse_mapping = {v: k for k, v in entity_mapping.items()}

        analyst = Analyst()
        output  = analyst.analyst({"cran_data": cran_data})

        analyst_output = AnalystOutput(
            trends=output["trends"],
            queries=output["queries"],
            director_names=output["director_names"],
            related_companies=output["related_companies"],
        )

        # Cache for eval_researcher.py — store anonymised identifiers as-is.
        # Privacy boundary handoff in production handles restoration before Researcher runs.
        cache = {
            "case":             case_name,
            "trends":           [t.model_dump() for t in analyst_output.trends],
            "queries":          [q.model_dump() for q in analyst_output.queries],
            "director_names":   analyst_output.director_names,
            "related_companies": analyst_output.related_companies,
            "entity_mapping":   entity_mapping,  # stored so eval_researcher can restore names
        }
        cache_path = cam_path.parent / "analyst_output.json"
        cache_path.write_text(json.dumps(cache, indent=2))
        print(f"  Cached → {cache_path.name}")

        result["trends_generated"]  = len(analyst_output.trends)
        result["queries_generated"] = len(analyst_output.queries)
        result["raw_trends"]  = [
            {"severity": t.severity.value, "observation": t.observation}
            for t in analyst_output.trends
        ]
        result["raw_queries"] = [
            {"category": q.category.value, "question": q.question}
            for q in analyst_output.queries
        ]

        for signal in EXPECTED_SIGNALS.get(case_name, []):
            result["signals"].append(_score_signal(signal, analyst_output))

        # Restore real names before scoring against EXPECTED_ENTITIES (which uses real names).
        # Mirrors the privacy boundary handoff in production before Researcher runs.
        restored_directors = [
            reverse_mapping.get(n, n) for n in (analyst_output.director_names or [])
        ]
        restored_companies = [
            reverse_mapping.get(n, n) for n in (analyst_output.related_companies or [])
        ]
        analyst_output_for_scoring = AnalystOutput(
            trends=analyst_output.trends,
            queries=analyst_output.queries,
            director_names=restored_directors,
            related_companies=restored_companies,
        )
        result["entities"] = _score_entities(
            EXPECTED_ENTITIES.get(case_name, {}), analyst_output_for_scoring
        )

        dir_recall = result["entities"]["directors"]["recall"]
        co_recall  = result["entities"]["related_companies"]["recall"]
        result["passed_entity_recall"] = (dir_recall == 1.0 and co_recall == 1.0)

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    return result


def print_summary(results: list[dict]):
    print("\n" + "=" * 70)
    print("LEVEL 2 EVAL — ANALYST AGENT")
    print("=" * 70)
    for r in results:
        if r["error"]:
            error_msg = r['error'][:300].encode('utf-8', errors='replace').decode('utf-8')
            print(f"\n  [ERROR] {r['case']}\n    {error_msg}")
            continue

        status = "PASS" if r["passed_entity_recall"] else "FAIL"
        print(f"\n  [{status}] {r['case']}")
        print(f"    Trends: {r['trends_generated']}  |  Queries: {r['queries_generated']}")
        print(f"    Entity recall — directors: {r['entities']['directors']['recall']:.0%}  "
              f"companies: {r['entities']['related_companies']['recall']:.0%}")

        if r["entities"]["directors"]["missed"]:
            print(f"    MISSED directors : {r['entities']['directors']['missed']}")
        if r["entities"]["related_companies"]["missed"]:
            print(f"    MISSED companies : {r['entities']['related_companies']['missed']}")

        keyword_hits  = sum(1 for s in r["signals"] if s["keyword_hit"] is True)
        keyword_total = sum(1 for s in r["signals"] if s["keyword_hit"] is not None)
        if keyword_total:
            print(f"    Keyword signal hits: {keyword_hits}/{keyword_total}")

        manual = [s["id"] for s in r["signals"] if s["keyword_hit"] is None]
        if manual:
            print(f"    Manual review needed: {manual}")

    print("\n" + "=" * 70)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    target_cases = sys.argv[1:] if len(sys.argv) > 1 else ALL_CASES
    invalid = [c for c in target_cases if c not in ALL_CASES]
    if invalid:
        print(f"Unknown cases: {invalid}\nValid: {ALL_CASES}")
        sys.exit(1)

    results = []
    for case_name in target_cases:
        cam_path = FIXTURES_DIR / case_name / "cam_anonymised.xlsx"
        if not cam_path.exists():
            print(f"SKIP {case_name}: cam_anonymised.xlsx not found. Run generate_fixtures.py first.")
            continue
        print(f"\nRunning analyst on: {case_name} ...")
        results.append(run_case(case_name, cam_path))

    if not results:
        print("No cases ran.")
        return

    print_summary(results)

    run_record = {
        "run_at":  datetime.now(datetime.UTC).isoformat() if hasattr(datetime, 'UTC')
                   else datetime.utcnow().isoformat() + "Z",
        "level":   2,
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
