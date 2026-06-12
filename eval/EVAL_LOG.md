# EVAL LOG — Agentic Override Decision Support System

This log documents eval runs, findings, prompt iterations, and improvements
across all three eval levels. Fixtures and raw results are gitignored.
This file is the human narrative layer committed to the public repo.

Fixture content, ground truth signals, stress test design, and prompt fix
details are withheld from this log. These encode domain-specific judgment
about MSME credit risk patterns and are available in a walkthrough.

---

## Level 1 — Ingestion Classification

**Date:** June 2026
**Eval script:** `eval/eval_ingestion.py`
**Fixture script:** `eval/generate_fixtures.py`
**Model:** `claude-haiku-4-5-20251001`

### What was tested

Sheet classification accuracy of `DataIngestor`. Haiku receives each sheet's
name and up to 15 rows of content and must classify it into one of seven
categories: `financial_statements`, `bureau_data`, `banking`, `emi_table`,
`debtor_creditor`, `scoring`, `irrelevant`.

Five synthetic CAM fixtures were designed to stress-test content-based
classification rather than name-based recognition:

| Fixture | Stress test |
|---|---|
| `case_01_sparse_data` | Clean sheet names, only 3–4 rows of data per sheet |
| `case_02_messy_names` | Realistic analyst names: `P&L`, `CIBIL`, `OD Acct`, `Book Debts`, `Entity` |
| `case_03_combined_sheet` | P&L + Balance Sheet merged on one tab; `Cover Page` sheet must be marked irrelevant |
| `case_04_late_data` | Financial data starts at row 8; `Loan Products` sheet with financial-looking numbers must be marked irrelevant |
| `case_05_generic_names` | Sheet names `Sheet1`, `Data`, `Summary`, `Table`, `Info` — name gives no signal |

### Run 1 — Initial prompt (1 run)

**Overall accuracy:** 92% (23/25 sheets correct)

**Failures:**
- `case_02_messy_names / Entity` → misclassified as `irrelevant` (0%)
- `case_05_generic_names / Data` → misclassified as `banking` (0%)

### Run 2 — Initial prompt (10 runs)

**Overall accuracy:** 92.8% (232/250 correct)

Confirmed failures are consistent, not sampling variance:
- `Entity` → `irrelevant` at 0% across all 10 runs. Deterministic failure.
- `Data` → `banking` at 80% failure rate (20% correct across 10 runs).

**Root cause analysis:**

`Entity` failure: the original system prompt gave Haiku no guidance on what
a `scoring` sheet looks like. A key-value parameter sheet with few rows and
a generic name was indistinguishable from an irrelevant sheet without explicit
criteria.

`Data` failure: the original prompt gave no distinguishing criteria between
`bureau_data` and `banking`. Both contain lender names and account amounts.
Without content-level differentiation (DPD columns = bureau; monthly
credits/debits = banking), Haiku defaulted to `banking` for ambiguous content.

### Prompt fix

Enriched the system prompt in `data_ingestor.py` with explicit distinguishing
criteria per category, common sheet name aliases, and edge case instructions.
See `data_ingestor.py` for current prompt (redacted in public repo).

### Run 3 — Improved prompt (1 run)

**Overall accuracy:** 100% (25/25 correct)

### Run 4 — Improved prompt (10 runs)

**Overall accuracy:** 100% (250/250 correct)

Zero failures across all cases, all runs.

### Session 5 re-run (1 run) — after entity substitution layer added

**Overall accuracy:** 100% (25/25 correct)

Confirmed: substitution layer does not affect Haiku classification accuracy.
Placeholders pass through the classification step correctly.

### Session 6 re-run (1 run) — after mid-sheet header scan added

**Overall accuracy:** 100% (25/25 correct)

Confirmed: mid-sheet header scan (fourth entity extraction pattern) does not
affect classification. All 25 sheets correctly classified.

### Conclusion

Level 1 passed and held across all pipeline changes in Sessions 5 and 6.

**Key learning:** LLM classifiers require explicit distinguishing criteria per
category, not just a list of category names. A minimal prompt is insufficient
when categories share surface features (bureau vs banking) or when content
is sparse and the sheet name gives no signal.

---

## Level 2 — Analyst Agent

**Date:** June 2026
**Eval script:** `eval/eval_analyst.py`
**Model:** `claude-sonnet-4-6`

### What was tested

Analyst Agent output quality across three dimensions:
- Entity extraction recall (directors and related companies)
- Anomaly signal detection (keyword match against expected signals)
- Query generation (minimum count)

Fixtures fed to the Analyst use `cam_anonymised.xlsx` — Company Name and CIN
stripped before ingestion, enforcing the system's privacy boundary.

### Architectural finding during eval design

During fixture design, a privacy gap was identified: the synthetic CAM
workbooks included Company Name in the Scoring sheet, which would be passed
to the Analyst LLM. This violates the intended privacy boundary — the Analyst
should never receive the primary identity of the borrower.

**Resolution:** Company Name and CIN stripping was implemented as a user
responsibility — the obligation is on the user to strip these fields before
uploading. This is documented in the UI and in `COMPLIANCE_GAPS.md`.
`generate_fixtures.py` produces both `cam.xlsx` (full) and
`cam_anonymised.xlsx` (stripped) for eval purposes.

A secondary finding: the Analyst prompt originally instructed entity
extraction only from scoring/entity sheets. This caused the Analyst to miss
related companies declared only in the Debtor/Creditor sheet relationship
column. The prompt was updated — see `agents.py`.

### Run 1 — Initial prompt

**Results:**
- `case_01_sparse_data` — FAIL: related company missing (fixture gap, not prompt gap)
- `case_02_messy_names` — FAIL: related company missed (prompt gap)
- `case_03_combined_sheet` — PASS
- `case_04_late_data` — PASS (5/5 keyword hits)
- `case_05_generic_names` — PASS

### Fixes applied

1. `EXPECTED_ENTITIES` updated for case_01 — removed related company
   expectation since the fixture does not contain it.

2. Analyst system prompt updated in `agents.py` — entity extraction
   instruction now explicitly scans debtor/creditor relationship columns.

### Run 2 — After fixes (all cases)

**Results:** 5/5 cases passing. Director recall 100%, company recall 100%,
keyword hits 9/9 across all scoreable cases.

### Session 5 re-run — after entity substitution layer added

**Results:** 5/5 PASS, 100% entity recall all cases.

`eval_analyst.py` updated to reverse-map anonymised identifiers before scoring
against ground truth real names. The substitution layer confirmed not affecting
Analyst output quality — entity recall holds at 100% through the anonymisation
layer.

### Session 6 re-run — after mid-sheet header scan added

**Results:** 5/5 PASS, 100% entity recall all cases.

Mid-sheet header scan addition to `data_ingestor.py` confirmed not breaking
Analyst pipeline. No regressions.

### Conclusion

Level 2 passed and held across all pipeline changes. The eval harness
correctly validates entity extraction through the substitution layer.

---

## Level 3 — Researcher Agent

**Date:** June 2026
**Eval script:** `eval/eval_researcher.py`
**Model:** `gpt-4o` (OpenAI) + Tavily search tools

### What was tested

Researcher Agent output quality across:
- Search agenda coverage (tool call counts vs minimum expected per entity)
- Stance extraction (extract_go_nogo parsing)
- Brief completeness (section keyword checks)
- Brief quality (human scoring: completeness 1–5, defensibility 1–5)

### Initial results (Session 3)

| Case | Stance | Coverage | Completeness | Defensibility |
|---|---|---|---|---|
| case_01_sparse_data | NOGO | PASS | 3/5 | 3/5 |
| case_02_messy_names | NEEDSMORE | PASS | 4/5 | 3/5 |
| case_03_combined_sheet | NEEDSMORE | FAIL | 3/5 | 2/5 |
| case_04_late_data | NOGO | PASS | 4/5 | 4/5 |
| case_05_generic_names | NEEDSMORE | PASS | 4/5 | 3/5 |

case_03 coverage failure: Researcher stopped after primary company without
researching directors or related company individually. Prompt gap identified.

### Session 5 re-run — after Researcher prompt fix and entity restoration

**Results:** 5/5 PASS, all coverage PASS.

Researcher prompt updated with mandatory per-entity separate tool calls.
This closed the case_03 director coverage gap. `eval_researcher.py` updated
to restore real names before passing to Researcher.

### Session 6 re-run — after mid-sheet header scan added

**Results:** 5/5 PASS, all coverage PASS.

No regressions. Pipeline end-to-end confirmed stable.

### Known limitation — synthetic company names

Brief quality is constrained by Tavily result quality on synthetic company
names. Real company names produce materially better briefs.

**Recommended next step:** Add `case_06_real_anonymised` — a real CAM case
with Company Name replaced and directors pseudonymised.

### Conclusion

Level 3 functional. All stance extractions pass. Search coverage passes on
all 5 cases after Session 5 prompt fix. Brief quality averages 3.6/5
completeness and 3.0/5 defensibility on synthetic fixtures.

---

## Open Items

- Fix identical monthly banking rows in fixtures (cases 03, 05)
- Add case_06_real_anonymised when a real anonymised CAM is available
- LLM-as-judge scoring for brief defensibility (v1 — needs domain-specific
  judge prompt for MSME lending context)

---

*Eval framework version: v0.2 — June 2026*
