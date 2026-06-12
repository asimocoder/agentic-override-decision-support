"""
eval_researcher.py
Level 3 eval — Researcher Agent output quality.

Loads cached analyst outputs from eval/fixtures/<case>/analyst_output.json,
injects synthetic company_name + cin, and runs the full GPT-4o ReAct loop.

Scores:
  - Search agenda coverage: tool call counts vs minimum expected
  - Stance extraction: did extract_go_nogo parse correctly?
  - Brief completeness: keyword checks for required sections
  - Human score columns: left for manual annotation after reviewing briefs

Run:
    uv run python eval/eval_researcher.py
    uv run python eval/eval_researcher.py case_01_sparse_data  # single case

Results appended to eval/results/researcher_results.json.

COST NOTE: Each case runs the full GPT-4o ReAct loop (multiple tool calls).
Estimated cost: ~$0.10-0.30 per case. Run selectively.
"""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from agents import Researcher, Trend, Query, GoNoGo, Severity, QueryCategory

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR  = Path(__file__).parent / "results"
RESULTS_FILE = RESULTS_DIR / "researcher_results.json"


# ---------------------------------------------------------------------------
# Synthetic company identities per fixture
# Injected at the human-input gate — simulating underwriter identification.
# ---------------------------------------------------------------------------

CASE_IDENTITIES: dict[str, dict] = {
    # Case identity data redacted from public version.
    # These encode synthetic company names and CINs used to inject
    # identity at the equivalent of the human review gate in the eval.
    # Contact the author for details.
}

ALL_CASES = list(CASE_IDENTITIES.keys())


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _count_tool_calls(messages: list) -> dict:
    counts: dict[str, int] = {}
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "unknown")
                counts[name] = counts.get(name, 0) + 1
    return counts


def _check_search_coverage(
    tool_call_counts: dict,
    director_names: list,
    related_companies: list,
) -> dict:
    news_calls    = tool_call_counts.get("news_search", 0)
    court_calls   = tool_call_counts.get("court_search", 0)
    industry_calls = tool_call_counts.get("industry_outlook", 0)

    # Minimum expected: 1 news + 1 court per entity (primary + directors + related cos)
    entity_count = 1 + len(director_names or []) + len(related_companies or [])

    return {
        "total_tool_calls":      sum(tool_call_counts.values()),
        "news_search_calls":     news_calls,
        "court_search_calls":    court_calls,
        "industry_outlook_calls": industry_calls,
        "entity_count":          entity_count,
        "min_expected_news":     entity_count,
        "min_expected_court":    entity_count,
        "news_sufficient":       news_calls >= entity_count,
        "court_sufficient":      court_calls >= entity_count,
        "human_verified_coverage": None,  # fill manually: True/False
    }


def _check_brief_completeness(brief_text: str) -> dict:
    required = {
        "positive_signals": ["positive", "strength", "stable", "consistent", "clean"],
        "risk_signals":     ["risk", "concern", "flag", "adverse", "anomaly", "red flag"],
        "query_resolution": ["query", "question", "resolve", "unresolved", "found", "could not"],
        "stance_line":      ["recommended stance"],
    }
    text_lower = brief_text.lower()
    results = {k: any(kw in text_lower for kw in keywords)
               for k, keywords in required.items()}
    results["human_score_completeness"]  = None  # 1-5
    results["human_score_defensibility"] = None  # 1-5
    return results


def _extract_final_brief(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            return msg.content
    return ""


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_case(case_name: str) -> dict:
    result = {
        "case":                      case_name,
        "go_nogo":                   None,
        "tool_call_counts":          {},
        "search_coverage":           {},
        "brief_completeness":        {},
        "final_brief_excerpt":       "",
        "error":                     None,
        "passed_stance_extraction":  False,
        "passed_search_coverage":    False,
    }

    cache_path = FIXTURES_DIR / case_name / "analyst_output.json"
    if not cache_path.exists():
        result["error"] = (
            f"Analyst cache not found: {cache_path}. "
            "Run eval_analyst.py first."
        )
        return result

    identity = CASE_IDENTITIES[case_name]

    try:
        cache = json.loads(cache_path.read_text())

        trends = [
            Trend(
                observation=t["observation"],
                supporting_data=t["supporting_data"],
                severity=Severity(t["severity"]),
            )
            for t in cache["trends"]
        ]
        queries = [
            Query(
                question=q["question"],
                category=QueryCategory(q["category"]),
                answer=q.get("answer"),
                resolvable=q.get("resolvable", True),
                source=q.get("source"),
                resolved=q.get("resolved", False),
            )
            for q in cache["queries"]
        ]
        director_names_raw    = cache.get("director_names") or []
        related_companies_raw = cache.get("related_companies") or []

        # Restore real names before passing to Researcher — mirrors privacy boundary handoff in production.
        # Analyst cache stores placeholder names (PERSON_1 etc); Researcher needs real names to search.
        entity_mapping  = cache.get("entity_mapping", {})  # built during ingestion, used to restore real names
        reverse_mapping = {v: k for k, v in entity_mapping.items()}
        director_names    = [reverse_mapping.get(n, n) for n in director_names_raw]
        related_companies = [reverse_mapping.get(n, n) for n in related_companies_raw]

        state = {
            "messages":          [],
            "company_name":      identity["company_name"],
            "cin":               identity["cin"],
            "trends":            trends,
            "queries":           queries,
            "director_names":    director_names,
            "related_companies": related_companies,
            "go_nogo":           None,
            "excel_path":        None,
            "cran_data":         None,
        }

        researcher = Researcher()

        from tools import news_search, court_search, industry_outlook
        tool_map = {
            "news_search":      news_search,
            "court_search":     court_search,
            "industry_outlook": industry_outlook,
        }

        max_iterations = 25
        for i in range(max_iterations):
            output = researcher.researcher(state)
            new_messages = output.get("messages", [])
            state["messages"] = state["messages"] + new_messages

            if output.get("go_nogo") is not None:
                state["go_nogo"] = output["go_nogo"]
                break

            last = state["messages"][-1] if state["messages"] else None
            if not isinstance(last, AIMessage):
                break

            if not last.tool_calls:
                state["go_nogo"] = researcher.extract_go_nogo(last)
                break

            # Execute tool calls
            tool_messages = []
            for tc in last.tool_calls:
                tool_fn = tool_map.get(tc["name"])
                if tool_fn:
                    try:
                        tool_result = tool_fn.invoke(tc["args"])
                        tool_messages.append(
                            ToolMessage(
                                content=str(tool_result),
                                tool_call_id=tc["id"],
                            )
                        )
                    except Exception as e:
                        tool_messages.append(
                            ToolMessage(
                                content=f"Tool error: {e}",
                                tool_call_id=tc["id"],
                            )
                        )
            state["messages"] = state["messages"] + tool_messages

        # Score
        tool_call_counts = _count_tool_calls(state["messages"])
        result["tool_call_counts"] = tool_call_counts
        result["go_nogo"] = state["go_nogo"].value if state["go_nogo"] else None
        result["passed_stance_extraction"] = state["go_nogo"] is not None

        result["search_coverage"] = _check_search_coverage(
            tool_call_counts, director_names, related_companies
        )
        result["passed_search_coverage"] = (
            result["search_coverage"]["news_sufficient"]
            and result["search_coverage"]["court_sufficient"]
        )

        final_brief = _extract_final_brief(state["messages"])
        result["final_brief_excerpt"] = (
            final_brief[:500] + "..." if len(final_brief) > 500 else final_brief
        )
        result["brief_completeness"] = _check_brief_completeness(final_brief)

        # Save full brief for human review
        brief_path = FIXTURES_DIR / case_name / "researcher_brief.txt"
        brief_path.write_text(final_brief, encoding="utf-8")
        print(f"  Brief saved → {brief_path.name}")

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    return result


def print_summary(results: list[dict]):
    print("\n" + "=" * 70)
    print("LEVEL 3 EVAL — RESEARCHER AGENT")
    print("=" * 70)
    for r in results:
        if r["error"]:
            print(f"\n  [ERROR] {r['case']}\n    {r['error'][:300]}")
            continue

        stance = "PASS" if r["passed_stance_extraction"] else "FAIL"
        cov    = "PASS" if r["passed_search_coverage"]   else "FAIL"
        print(f"\n  [stance:{stance} coverage:{cov}] {r['case']}")
        print(f"    Stance: {r['go_nogo']}  |  Tool calls: {r['tool_call_counts']}")

        sc = r["search_coverage"]
        print(f"    Search coverage — "
              f"news: {sc.get('news_search_calls',0)}/{sc.get('min_expected_news',0)}  "
              f"court: {sc.get('court_search_calls',0)}/{sc.get('min_expected_court',0)}  "
              f"industry: {sc.get('industry_outlook_calls',0)}")

        bc = r["brief_completeness"]
        print(f"    Brief sections — "
              f"positive: {bc.get('positive_signals')}  "
              f"risk: {bc.get('risk_signals')}  "
              f"queries: {bc.get('query_resolution')}  "
              f"stance line: {bc.get('stance_line')}")
        print(f"    Human scores needed: completeness (1-5), defensibility (1-5)")

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
        cache_path = FIXTURES_DIR / case_name / "analyst_output.json"
        if not cache_path.exists():
            print(f"\nSKIP {case_name}: no analyst cache. Run eval_analyst.py first.")
            continue
        print(f"\nRunning researcher on: {case_name} ...")
        results.append(run_case(case_name))

    if not results:
        print("No cases ran.")
        return

    print_summary(results)

    run_record = {
        "run_at":  datetime.utcnow().isoformat() + "Z",
        "level":   3,
        "results": results,
    }
    existing = []
    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text())
        except Exception:
            existing = []
    existing.append(run_record)
    RESULTS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
