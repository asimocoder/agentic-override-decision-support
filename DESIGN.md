# Design Document
## Agentic Override Decision Support System — MSME Lending

**Version:** 0.4 — Post First End-to-End Run
**Author:** Asiman K. Panda
**Date:** May 17, 2026
**Stack:** LangGraph · Claude Sonnet/Haiku (Ingestion + Analyst) · GPT-4o (Researcher) · Tavily · Python · Gradio

---

## 1. Problem Statement

When an MSME borrower is assessed for a loan, the internal scoring system produces
a credit score and a recommendation. However, the internal score is a filter, not a
verdict — it can paper over nuances that an experienced underwriter would catch:
related party risks, sector stress, director-level flags, anomalous financial trends.

Today, when underwriters do additional research beyond the score, they do it manually
— news searches, court record checks, related party lookups, bureau signal
interpretation — inconsistently and at varying depths. Two underwriters on the same
case may reach different conclusions not because the facts differ, but because their
research depth does.

This system automates the research layer. It does not make the credit decision. It
ensures every case that warrants deeper diligence arrives at the underwriter's desk
with a consistent, structured intelligence brief.

---

## 2. Trigger and Inputs

### When the Underwriter Runs the Workflow

In all three scenarios below, the workflow is initiated manually by the underwriter.
There is no automated trigger. The underwriter opens the interface, uploads the CAM
workbook, selects the trigger type, and clicks Run Analysis to start the workflow.
Automated initiation via integration with the lending system's scoring engine is
planned for a future version.

**Trigger 1 — Below Threshold**
Credit score falls below the internal cutoff. Underwriter initiates the workflow as
part of the mandatory override review process.

**Trigger 2 — Above Threshold, Anomalies Present**
Score clears the threshold, but the underwriter or credit manager judges that the
internal score may not be capturing the full risk picture — a related party flag,
deteriorating debtors, unusual inventory buildup, sector stress. Underwriter
initiates the workflow manually.

**Trigger 3 — Standard Diligence**
For cases above a certain loan size or risk category, the underwriter runs the
workflow as a consistent diligence step regardless of score.

The workflow is a diligence tool, not just a remediation tool.

### Inputs — Two Stages

**Stage 1 Inputs — Anonymised (fed to Ingestion Layer and Analyst)**
No company name. No CIN. No PAN. No PII of any kind.

- Credit Assessment Memo (CAM) workbook uploaded via Gradio interface
- Structured fields extracted and classified by the ingestion layer before
  the Analyst runs

Note: CAM workbooks do not have a consistent sheet structure across cases.
Sheet count, sheet names, and sheet content vary. The ingestion layer handles
this variability — the Analyst always receives consistently categorised data
regardless of the source workbook's structure.

Note: CAM workbooks already contain entity-level data including director names
and related company information. No separate MCA21 lookup is required.

**Stage 2 Inputs — Named Entity (fed to Researcher, after human review gate)**
Provided by the underwriter at the handoff point:

- Company Name
- CIN (Corporate Identification Number)
- Analyst output: confirmed trends list + query list (editable by underwriter)

### Explicit Exclusions (Both Stages)

- No raw financial documents or scanned statements passed to either component
- No unstructured text from internal systems
- No personal financial details of directors beyond what is publicly available
- Company Name, CIN, and PAN never passed to Ingestion Layer or Analyst under
  any condition

---

## 3. System Architecture

The system has three components:

**Ingestion Layer**
A deterministic pipeline with one LLM-assisted classification step. Haiku classifies
sheet types; the rest is pure Python.

**Analyst Agent (Agent 1)**
A single structured Sonnet call that reasons over CAM data and produces structured
output. Detects financial anomalies, interprets bureau signals, and extracts director
names and related companies.

**Researcher Agent (Agent 2)**
GPT-4o in a ReAct tool-calling loop with three external search tools. Has a loop,
uses tools, decides its own exit condition.

---

## 4. Ingestion Layer

### Purpose

Sits between the Gradio interface and the Analyst. Converts a variable-structure CAM
workbook into consistently categorised, structured data that the Analyst can
reason over reliably.

### Two-Step Process

**Step 1 — Sample All Sheets**
Read all sheets in the workbook. For each sheet, extract:
- Column names
- Row count
- 15-row preview

**Step 2 — LLM-Assisted Sheet Classification (Haiku)**
Pass sheet metadata to Haiku. Haiku classifies each sheet into one of seven
categories: `financial_statements`, `bureau_data`, `banking`, `emi_table`,
`debtor_creditor`, `scoring`, `irrelevant`. Classification is based on sheet
column names and a 15-row preview sample.

**Step 3 — Full Ingestion of Relevant Sheets Only**
Read complete data from all relevant sheets. Drop fully empty rows and columns.
Serialize all datetime objects to ISO format strings before storing.

### Output Structure

```python
cran_data = {
    "Sheet Name As In Workbook": {
        "category": "financial_statements",
        "data": [...]  # full records as list of dicts
    },
    ...
}
```

### Implementation

`DataIngestor` class in `data_ingestor.py`. Key methods:
- `classify_sheets_with_llm()` — Haiku classification call
- `serialize_value()`, `serialize_key()`, `serialize_records()` — datetime
  serialization helpers
- `excel_ingestor()` — LangGraph node function, reads state, returns
  `{"cran_data": cran_data}`

---

## 5. Tools

### Ingestion Layer Tools

No external tools. One Haiku LLM call for sheet classification only.

### Analyst Tools

None. The Analyst is a single structured Sonnet call over data already present
in state. Financial Anomaly Detection and Bureau Signal Interpretation are
capabilities described in the system prompt, not `@tool` decorated functions.

### Researcher Tools

Three tools, all implemented via Tavily Python SDK direct calls:

**Tool A — News Search**
Input: Query string (company name, director name, or related company name)
Output: Summarised news items with source and date
Scope: Last 3 years preferred

**Tool B — Court and Legal Records Search**
Input: Query string
Output: Court cases, NCLT filings, DRT proceedings, enforcement actions
Known limitation: Tavily best-effort; not a dedicated legal data API

**Tool C — Industry Outlook**
Input: Sector classification query
Output: Sector growth trend, regulatory changes, peer stress signals,
commodity price movements
Scope: Last 12 months prioritised

All tools append today's date to the query string for recency grounding.

---

## 6. State Object

```python
class GoNoGo(str, Enum):
    GO = "go"
    NOGO = "nogo"
    NEEDSMORE = "needsmoreresearch"

class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class QueryCategory(str, Enum):
    ONLINE_RESOLVABLE = "online_resolvable"
    DOCUMENT_REQUEST = "document_request"
    INTERNAL_ACCOUNTING = "internal_accounting"

class Trend(BaseModel):
    observation: str
    supporting_data: str
    severity: Severity

class Query(BaseModel):
    question: str
    category: QueryCategory
    answer: Optional[str] = None
    resolvable: bool = True
    source: Optional[str] = None
    resolved: bool = False

class AnalystOutput(BaseModel):
    trends: List[Trend]
    queries: List[Query]
    director_names: Optional[List[str]]
    related_companies: Optional[List[str]]

class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    excel_path: Optional[str]
    cran_data: Optional[Dict]
    trends: Optional[List[Trend]]
    queries: Optional[List[Query]]
    company_name: Optional[str]
    cin: Optional[str]
    director_names: Optional[List[str]]
    related_companies: Optional[List[str]]
    go_nogo: Optional[GoNoGo]
```

### How State Builds Up

| Stage | Fields populated |
|---|---|
| Start | `excel_path` |
| After ingestion | `cran_data` |
| After Analyst | `trends`, `queries`, `director_names`, `related_companies` |
| After human review gate | `company_name`, `cin` (via `graph.update_state()`), plus updated `trends` and `queries` if underwriter edited tables |
| After Researcher | `messages` (full research history), `go_nogo` |

---

## 7. StateGraph / Orchestration Flow

```python
gbuilder = StateGraph(State)

gbuilder.add_node("excel_ingestor", self.data_ingestor.excel_ingestor)
gbuilder.add_node("analyst", self.analyst.analyst)
gbuilder.add_node("human_input", self.human_input)
gbuilder.add_node("researcher", self.researcher.researcher)
gbuilder.add_node("tools", ToolNode(tools=researcher_tools))

gbuilder.add_edge(START, "excel_ingestor")
gbuilder.add_edge("excel_ingestor", "analyst")
gbuilder.add_edge("analyst", "human_input")
gbuilder.add_edge("human_input", "researcher")
gbuilder.add_conditional_edges("researcher", tools_condition)
gbuilder.add_edge("tools", "researcher")
gbuilder.add_edge("researcher", END)

graph = gbuilder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["human_input"]
)
```

### Node Responsibilities

| Node | Responsibility |
|---|---|
| `excel_ingestor` | Sample all sheets, classify via Haiku, ingest relevant sheets fully, serialize datetimes |
| `analyst` | Detect financial anomalies, interpret bureau signals, extract director names and related companies, generate trends and queries |
| `human_input` | Interrupt point — underwriter reviews and edits Analyst Agent output, provides Company Name + CIN via Gradio before graph resumes |
| `researcher` | External research via tool-calling loop, query resolution, go/no-go decision |
| `tools` | ToolNode executing Researcher's three external tools |

### Researcher Loop Logic

The researcher node runs multiple times during the ReAct loop. On each pass:
- If `response.tool_calls` is non-empty → return `{"messages": [response]}`,
  loop continues via `tools_condition`
- If `response.tool_calls` is empty → final pass, return
  `{"messages": [response], "go_nogo": extract_go_nogo(response)}`

### Search Agenda

The researcher prompt pre-generates a structured checklist covering:
- Primary company: news search, court search, industry outlook
- Each director individually: news search, court search
- Each related/group company individually: news search, court search

Director names and related companies are extracted by the Analyst from CAM
data and stored in State — available to the Researcher without any additional
lookup tool.

---

## 8. User Interface — Gradio

**Framework:** Gradio 6.0
**Layout:** Single scrolling page, four sections with progressive disclosure
**Purpose:** Structured workflow interface — not a general chatbot

### Four Workflow Steps

**Step 1 — Intake**
Underwriter uploads CAM workbook via `gr.File` component. Selects
trigger type (Below Threshold / Anomaly Flagged / Standard Diligence).
Clicks Run Analysis. Button disables and shows "Running analysis..." while
Agent 1 runs.

**Step 2 — Analyst Output Review**
Interface displays:
- Flagged financial anomalies with supporting data and severity (editable
  Dataframe)
- Generated query list, pre-classified by type (editable Dataframe)

Underwriter can edit, add, or delete rows in both tables before proceeding.
Edited values are written back to state via `graph.update_state()` before
Agent 2 runs.

**Step 3 — Named Entity Handoff**
Interface prompts underwriter to provide Company Name + CIN. Confirms that
this information was not shared with the Analyst. Clicks Run External Research.
Button disables and shows "Running external research..." while Agent 2 runs.

**Step 4 — Intelligence Brief Delivery**
Recommended stance displayed in a dedicated field (GO / NOGO / NEEDS FURTHER
RESEARCH). Full intelligence brief displayed in a scrollable text area.
Start New Case button resets the interface and generates a new thread ID.

### Thread Management

Each case gets a unique `thread_id` generated via `uuid.uuid4()`. Thread ID
is stored in Gradio `gr.State` and passed into `uw_helper` methods as a
parameter. This allows LangGraph checkpointing to correctly associate each
run with its own conversation history.

---

## 9. Output — The Intelligence Brief

**Format:** Structured text, 1–2 pages
**Recipient:** Underwriter or credit manager reviewing the case

### Sections

**Key Positive Signals**
Bureau behavioral signals despite low score (if applicable), sector tailwinds,
clean legal record (if applicable), relationship history with lender.

**Key Risk Signals**
Adverse news, litigation, enforcement actions, director-level flags, sector
stress, financial anomalies surfaced by Analyst.

**Resolved and Unresolved Queries**
Queries the Analyst generated, with resolution status. Unresolved queries
become the underwriter's follow-up checklist for the credit call, classified
by type: document-request / internal-accounting / insufficient public data.

**Recommended Stance**
GO / NOGO / NEEDS FURTHER RESEARCH with one paragraph rationale. The final
line of the brief must be exactly one of:
- `RECOMMENDED STANCE: GO`
- `RECOMMENDED STANCE: NOGO`
- `RECOMMENDED STANCE: NEEDS FURTHER RESEARCH`

This line is parsed by `extract_go_nogo()` to populate `state["go_nogo"]`.

---

## 10. Technical Guardrails

### Architectural Guardrails *(implemented in code)*

- Multi-model routing — Haiku for classification, Sonnet for reasoning and synthesis,
  GPT-4o for external research ReAct loop
- Privacy boundary — Company Name, CIN, and PAN never passed to Ingestion Layer or
  Analyst under any condition; enforced at state design level
- Datetime serialization in ingestion layer prevents JSON encoding errors downstream
- Gradio yield pattern prevents double-clicking and provides underwriter feedback
  during long-running LLM calls
- No native code execution tool — purely token-based billing, no sandbox required

### Operational Guardrails *(set externally)*

- Spend limits configured on Anthropic and OpenAI consoles before live runs
- Mock tools used during development; live API calls only after logic stabilised

---

## 11. What "Done" Looks Like

The build is done when a real underwriter — or someone who has sat in a credit
committee — reads the output brief and says:

- "This would have saved me 2 hours on this case"
- "I would have missed the related-party flag without this"
- "The query list is exactly what I would have asked in the credit call"
- "The financial anomalies section caught things I would have caught myself —
  but only after 20 minutes with the spreadsheet"

---

## 12. Known Limitations and Roadmap

| Limitation | Current State | Roadmap |
|---|---|---|
| MCA21 / entity data | Third-party populated CAM | Adequate for v1; revisit if CAM coverage gaps found |
| Court record search | Tavily best-effort | Dedicated legal data API (eCourts, NCLT direct) |
| Variable CAM structure | Handled via LLM classification | Formalise CAM schema company-wide |
| No audit trail | Not built | Logging layer + case ID linkage |
| No system integration | Standalone Gradio app | API wrapper for lending system |
| Automated trigger | Manual initiation only | Integration with scoring engine to trigger workflow automatically when threshold conditions are met |
| No auth | Not built | Standard API auth layer |
| Analyst loop | Single pass, no self-critique | Self-critique loop in v1 |
| Underwriter feedback | No re-run capability | Feedback loop to Analyst in v1 |
| PDF export | Not built | v1 feature |
| Excel ingestion | Haiku-classified | Formalise if CAM structure standardised |
| go_nogo parsing | String matching on final brief | Verify exact string format in GPT-4o output |
| Eval framework | Not yet built | Separate eval harness — three-layer rubric covering sheet classification accuracy (ingestion), anomaly recall and entity extraction (Analyst), search agenda coverage, query resolution rate, and brief completeness and defensibility (Researcher); requires semi-synthetic CAMs with known ground truth |

---

## 13. V1 Features

- **Self-critique loop** — Analyst + Analyst Critic nodes with autonomous exit
  condition based on output quality
- **Underwriter feedback loop** — conditional edge from `human_input` back
  to `analyst` if underwriter requests revision before proceeding to research
- **PDF export** of intelligence brief
- **Audit trail** — case ID, run timestamp, data sources used, logged per run
- **Max retries** hardcoded on researcher tool-calling loop
