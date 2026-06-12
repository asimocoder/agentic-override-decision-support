# Eval Framework — Agentic Override Decision Support System

This folder contains the evaluation harness for the system.
It is separate from the main application code and has no runtime dependencies on it beyond imports.

Fixture content, stress test design, ground truth signals, and scoring thresholds
are withheld from the public repository. These encode domain-specific judgment
about MSME credit risk patterns and are available in a walkthrough.

---

## Directory structure

```
eval/
  eval_ingestion.py       — Level 1: sheet classification accuracy (multi-run)
  eval_analyst.py         — Level 2: Analyst Agent output quality
  save_analyst_cache.py   — cache Analyst outputs without scoring
  eval_researcher.py      — Level 3: Researcher Agent output quality
  EVAL_LOG.md             — results log (committed to public repo)
  README.md               — this file
  fixtures/               — generated CAM workbooks + cached outputs (gitignored)
  results/                — JSON result files per eval run (gitignored)

tests/
  conftest.py                   — pytest configuration
  test_extract_go_nogo.py       — unit tests for stance parsing (no API calls)
  test_accordion.py             — unit tests for Gradio accordion UI logic
  test_entity_substitution.py   — unit tests for entity mapping and substitution
  test_pii_detection.py         — unit tests for pre-upload PII scan
```

---

## Eval levels

### Level 1 — Ingestion (`eval_ingestion.py`)

Tests `DataIngestor` sheet classification accuracy. Haiku receives each
sheet's name and up to 15 rows of content and classifies into one of seven
categories. Because classification is LLM-based, multiple runs are used to
measure variance.

**Pass criterion:** ≥95% accuracy across all sheets and runs.
Any sheet below 100% across runs is flagged for prompt investigation.

```bash
uv run python eval/eval_ingestion.py           # default 10 runs
uv run python eval/eval_ingestion.py --runs 1  # smoke test
uv run python eval/eval_ingestion.py --runs 20 # higher confidence
```

---

### Level 2 — Analyst Agent (`eval_analyst.py`)

Runs the Analyst Agent on each fixture and scores:

| Dimension | Method | Pass criterion |
|---|---|---|
| Output completeness | Structured output quality | Case-specific criteria |
| Anomaly signal detection | Keyword match + human score | ≥80% keyword hits |
| Query generation | Count | ≥2 queries per case |

Also caches analyst outputs for use by `eval_researcher.py`.

```bash
uv run python eval/eval_analyst.py                        # all cases
uv run python eval/eval_analyst.py case_01_sparse_data    # single case
```

---

### Level 3 — Researcher Agent (`eval_researcher.py`)

Loads cached analyst outputs, runs the full GPT-4o ReAct loop after the
human review stage, and scores:

| Dimension | Method | Pass criterion |
|---|---|---|
| Stance extraction | Stance parsed from brief | Non-null stance |
| Search coverage — news | Minimum tool calls per run | Sufficient calls |
| Search coverage — court | Minimum tool calls per run | Sufficient calls |
| Brief completeness | Section keyword check | All 4 sections present |
| Brief defensibility | Human score (1–5) | ≥3 |

**Cost estimate:** ~$0.10–0.30 per case (GPT-4o + Tavily).
Run selectively.

```bash
uv run python eval/eval_researcher.py case_01_sparse_data  # single case
uv run python eval/eval_researcher.py                      # all cases
```

**Known limitation:** Synthetic company names produce thin or generic
Tavily search results. Brief quality on synthetic fixtures is materially
lower than on real company names. See EVAL_LOG.md for details.

---

## Quick start

```bash
# Note: fixtures are not included in the public repo (gitignored).
# eval scripts require fixtures to run — contact the author or
# generate your own following the structure visible in the eval scripts.

# Step 1 — unit tests (no API calls)
uv run pytest tests/

# Step 2 — Level 1 (Haiku API, ~50 calls at 10 runs)
uv run python eval/eval_ingestion.py --runs 1   # smoke test first
uv run python eval/eval_ingestion.py            # full run

# Step 3 — Level 2 (Sonnet API, 5 calls)
uv run python eval/eval_analyst.py

# Step 4 — Level 3 (GPT-4o + Tavily, run selectively)
uv run python eval/eval_researcher.py case_01_sparse_data
uv run python eval/eval_researcher.py
```

---

## Synthetic test cases

Five synthetic CAM fixtures stress-test different aspects of the pipeline:

| Case |
|---|
| `case_01_sparse_data` |
| `case_02_messy_names` |
| `case_03_combined_sheet` |
| `case_04_late_data` |
| `case_05_generic_names` |

Stress test design for each case is withheld — contact the author.

---

## Results files

| File | Contents | Committed? |
|---|---|---|
| `eval/results/ingestion_results.json` | Level 1 run history | No (gitignored) |
| `eval/results/analyst_results.json` | Level 2 run history | No (gitignored) |
| `eval/results/researcher_results.json` | Level 3 run history | No (gitignored) |
| `eval/EVAL_LOG.md` | Human narrative log across runs | Yes |

---

## Notes on privacy

- No real borrower data is used in fixtures
- All company names, CINs, and director names are synthetic
- Fixture files are gitignored
- The public repo contains eval structure, scoring logic, and EVAL_LOG.md only
