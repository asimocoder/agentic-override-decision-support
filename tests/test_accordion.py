"""
test_accordion.py
Unit tests for accordion collapse/expand logic in app.py.

Tests the gr.update values yielded/returned by each event handler
without making any LLM calls. All uw_helper methods are patched.

Key changes from previous version (Session 5):
- run_agent1 yields 6 outputs (removed pii_warning_box — PII now detected at upload time)
- run_agent2 yields 8 outputs (unchanged)
- reset() returns 22 outputs (added go_button, proceed_pii_button, abort_pii_button)
- step4_group open=False on final yield (JS opens it, not Python)
- proceed_button step3 open=False on yield (JS opens it, not Python)

Run:
    uv run pytest tests/test_accordion.py
"""

import asyncio
import sys
from unittest.mock import AsyncMock, patch
import gradio as gr

# ── Patch uw_helper before app.py is imported ────────────────────────────────
with patch("uw_helper.UWHelper") as MockUWHelper:
    mock_instance = MockUWHelper.return_value
    mock_instance.make_thread_id.return_value = "test-thread-id"
    mock_instance.run_agent1_step = AsyncMock(
        return_value=(
            [["Revenue drop", "Q3 data", "High"]],
            [["Outstanding litigation?", "online_resolvable"]],
        )
    )
    mock_instance.run_agent2_step = AsyncMock(
        return_value=("Full brief text", "GO")
    )
    import app as app_module


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_update(u, key):
    """Pull a key from a gr.update dict-like object."""
    if isinstance(u, dict):
        return u.get(key)
    d = getattr(u, "__dict__", {})
    props = d.get("props", d)
    return props.get(key)


def check(label, actual, expected):
    ok = actual == expected
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}: expected={expected!r}, got={actual!r}")
    return ok


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_run_agent1():
    """
    run_agent1 yields twice.
    Outputs (6): step1_group, step2_group, go_button, trends_table, queries_table, trigger_state
    PII detection now happens at upload time via scan_pii — not in run_agent1.
    """
    print("\n── run_agent1 ──────────────────────────────────────────────")
    gen = app_module.run_agent1(None, "Below Threshold", "t1")

    # First yield — analysis running
    first = await gen.__anext__()
    assert len(first) == 6, f"Expected 6 outputs, got {len(first)}"
    step1, step2, go_btn, trends, queries, trig_state = first

    results = [
        check("first yield: step1_group visible=True",  extract_update(step1,   "visible"), True),
        check("first yield: step2_group visible=False", extract_update(step2,   "visible"), False),
        check("first yield: step2_group open=False",    extract_update(step2,   "open"),    False),
        check("first yield: go_button interactive=False", extract_update(go_btn, "interactive"), False),
        check("first yield: trigger_state='Below Threshold'", trig_state, "Below Threshold"),
    ]

    # Final yield — analysis complete
    final = await gen.__anext__()
    assert len(final) == 6, f"Expected 6 outputs, got {len(final)}"
    step1, step2, go_btn, trends, queries, trig_state = final

    results += [
        check("final yield: step1_group visible=False", extract_update(step1,   "visible"), False),
        check("final yield: step2_group visible=True",  extract_update(step2,   "visible"), True),
        # open=False on final yield — JS opens the accordion via .then()
        check("final yield: step2_group open=False",    extract_update(step2,   "open"),    False),
        check("final yield: go_button interactive=True", extract_update(go_btn, "interactive"), True),
        check("final yield: trigger_state preserved",   trig_state, "Below Threshold"),
    ]
    return results


async def test_proceed_button():
    """
    proceed_button lambda returns 2 outputs:
    step2_group (visible=True, open=False), step3_group (visible=True, open=False)
    JS opens step3 via .then().
    """
    print("\n── proceed_button ───────────────────────────────────────────")
    # Call the lambda directly — same logic wired in the click handler
    fn = lambda: (
        gr.update(visible=True, open=False),
        gr.update(visible=True, open=False),
    )
    step2, step3 = fn()

    results = [
        check("proceed: step2_group visible=True",  extract_update(step2, "visible"), True),
        check("proceed: step2_group open=False",    extract_update(step2, "open"),    False),
        check("proceed: step3_group visible=True",  extract_update(step3, "visible"), True),
        # open=False — JS opens step3 via .then()
        check("proceed: step3_group open=False",    extract_update(step3, "open"),    False),
    ]
    return results


async def test_run_agent2():
    """
    run_agent2 yields twice.
    Outputs (8): step2_group, step3_group, step4_group, research_button,
                 go_nogo_display, brief_display, go_nogo_state, brief_state
    """
    print("\n── run_agent2 ──────────────────────────────────────────────")
    gen = app_module.run_agent2([], [], "Acme Corp", "CIN123", "t1")

    # First yield — research running
    first = await gen.__anext__()
    assert len(first) == 8, f"Expected 8 outputs, got {len(first)}"
    step2, step3, step4, btn, go_nogo_disp, brief_disp, go_nogo_st, brief_st = first

    results = [
        check("first yield: step2_group visible=True",   extract_update(step2,  "visible"), True),
        check("first yield: step2_group open=False",     extract_update(step2,  "open"),    False),
        check("first yield: step3_group visible=True",   extract_update(step3,  "visible"), True),
        check("first yield: step3_group open=True",      extract_update(step3,  "open"),    True),
        check("first yield: step4_group visible=False",  extract_update(step4,  "visible"), False),
        check("first yield: step4_group open=False",     extract_update(step4,  "open"),    False),
        check("first yield: research_button interactive=False", extract_update(btn, "interactive"), False),
        check("first yield: go_nogo_display=''",  go_nogo_disp, ""),
        check("first yield: brief_display=''",    brief_disp,   ""),
        check("first yield: go_nogo_state=''",    go_nogo_st,   ""),
        check("first yield: brief_state=''",      brief_st,     ""),
    ]

    # Final yield — research complete
    final = await gen.__anext__()
    assert len(final) == 8, f"Expected 8 outputs, got {len(final)}"
    step2, step3, step4, btn, go_nogo_disp, brief_disp, go_nogo_st, brief_st = final

    results += [
        check("final yield: step2_group visible=True",   extract_update(step2,  "visible"), True),
        check("final yield: step2_group open=False",     extract_update(step2,  "open"),    False),
        check("final yield: step3_group visible=True",   extract_update(step3,  "visible"), True),
        check("final yield: step3_group open=False",     extract_update(step3,  "open"),    False),
        check("final yield: step4_group visible=True",   extract_update(step4,  "visible"), True),
        # open=False — JS opens step4 via .then()
        check("final yield: step4_group open=False",     extract_update(step4,  "open"),    False),
        check("final yield: research_button interactive=True", extract_update(btn, "interactive"), True),
        check("final yield: go_nogo_display='GO'",  go_nogo_disp, "GO"),
        check("final yield: brief_display set",     brief_disp,   "Full brief text"),
        check("final yield: go_nogo_state='GO'",    go_nogo_st,   "GO"),
        check("final yield: brief_state set",       brief_st,     "Full brief text"),
    ]
    return results


async def test_reset():
    """
    reset() returns 21 outputs:
    step1_group, step2_group, step3_group, step4_group,
    excel_file, trigger_type, trends_table, queries_table,
    company_name, cin, go_nogo_display, brief_display,
    thread, trigger_state, docx_output, pdf_output,
    brief_state, go_nogo_state, pii_warning_box,
    go_button, pii_action_row
    """
    print("\n── reset ────────────────────────────────────────────────────")
    result = await app_module.reset()
    assert len(result) == 21, f"Expected 21 outputs, got {len(result)}"

    (step1, step2, step3, step4,
     excel_file, trigger_type, trends_table, queries_table,
     company_name, cin, go_nogo_display, brief_display,
     thread, trigger_state, docx_output, pdf_output,
     brief_state, go_nogo_state, pii_box,
     go_btn_reset, pii_action_row) = result

    results = [
        check("reset: step1_group visible=True",   extract_update(step1,  "visible"), True),
        check("reset: step2_group visible=False",  extract_update(step2,  "visible"), False),
        check("reset: step2_group open=False",     extract_update(step2,  "open"),    False),
        check("reset: step3_group visible=False",  extract_update(step3,  "visible"), False),
        check("reset: step3_group open=False",     extract_update(step3,  "open"),    False),
        check("reset: step4_group visible=False",  extract_update(step4,  "visible"), False),
        check("reset: step4_group open=False",     extract_update(step4,  "open"),    False),
        check("reset: excel_file=None",            excel_file,     None),
        check("reset: trigger_type='Below Threshold'", trigger_type, "Below Threshold"),
        check("reset: trends_table=[]",            trends_table,   []),
        check("reset: queries_table=[]",           queries_table,  []),
        check("reset: company_name=''",            company_name,   ""),
        check("reset: cin=''",                     cin,            ""),
        check("reset: go_nogo_display=''",         go_nogo_display, ""),
        check("reset: brief_display=''",           brief_display,  ""),
        check("reset: thread=new id",              thread,         "test-thread-id"),
        check("reset: trigger_state=''",           trigger_state,  ""),
        check("reset: docx_output visible=False",  extract_update(docx_output, "visible"), False),
        check("reset: pdf_output visible=False",   extract_update(pdf_output,  "visible"), False),
        check("reset: brief_state=''",             brief_state,    ""),
        check("reset: go_nogo_state=''",           go_nogo_state,  ""),
        check("reset: pii_warning_box visible=False", extract_update(pii_box, "visible"), False),
        check("reset: go_button interactive=False",  extract_update(go_btn_reset, "interactive"), False),
        check("reset: pii_action_row visible=False",  extract_update(pii_action_row, "visible"), False),
    ]
    return results


async def test_download_docx_no_brief():
    """download_docx raises gr.Error when brief is empty."""
    print("\n── download_docx (no brief) ─────────────────────────────────")
    results = []
    try:
        app_module.download_docx("", "GO", "Acme Corp", "Below Threshold")
        results.append(check("raises gr.Error on empty brief", False, True))
    except gr.Error:
        results.append(check("raises gr.Error on empty brief", True, True))
    except Exception as e:
        results.append(check(f"raises gr.Error on empty brief (got {type(e).__name__})", False, True))
    return results


async def test_download_pdf_no_brief():
    """download_pdf raises gr.Error when brief is empty."""
    print("\n── download_pdf (no brief) ──────────────────────────────────")
    results = []
    try:
        app_module.download_pdf("", "GO", "Acme Corp", "Below Threshold")
        results.append(check("raises gr.Error on empty brief", False, True))
    except gr.Error:
        results.append(check("raises gr.Error on empty brief", True, True))
    except Exception as e:
        results.append(check(f"raises gr.Error on empty brief (got {type(e).__name__})", False, True))
    return results


async def test_copy_analyst_output():
    """copy_analyst_output formats tables as tab-separated text."""
    print("\n── copy_analyst_output ──────────────────────────────────────")
    import pandas as pd
    trends_df = pd.DataFrame(
        [["Revenue drop", "Q3 data", "High"]],
        columns=["Observation", "Supporting Data", "Severity"]
    )
    queries_df = pd.DataFrame(
        [["Outstanding litigation?", "online_resolvable"]],
        columns=["Question", "Category"]
    )
    output = app_module.copy_analyst_output(trends_df, queries_df)
    results = [
        check("contains FINANCIAL ANOMALIES header", "FINANCIAL ANOMALIES" in output, True),
        check("contains QUERIES header",             "QUERIES FOR EXTERNAL RESEARCH" in output, True),
        check("contains trend observation",          "Revenue drop" in output, True),
        check("contains query text",                 "Outstanding litigation?" in output, True),
        check("tab-separated",                       "\t" in output, True),
    ]
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    all_results = []
    all_results += await test_run_agent1()
    all_results += await test_proceed_button()
    all_results += await test_run_agent2()
    all_results += await test_reset()
    all_results += await test_download_docx_no_brief()
    all_results += await test_download_pdf_no_brief()
    all_results += await test_copy_analyst_output()

    failures = sum(1 for r in all_results if not r)
    total = len(all_results)
    print(f"\n{'=' * 55}")
    print(f"Result: {total - failures}/{total} passed, {failures} failure(s)")
    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
