# Agentic Override Decision Support System
### MSME Credit Underwriting · Human-in-the-Loop AI

> ⚠️ This project is licensed under [PolyForm Noncommercial 1.0.0](LICENSE). Commercial use requires explicit written permission from the author.

---

## The Problem

When an MSME borrower is assessed for a loan, the internal credit score is a filter — not a verdict. It can paper over nuances an experienced underwriter would catch: related party risks, sector stress, director-level flags, anomalous financial trends.

When underwriters do additional research beyond the score, they do it manually — news searches, court record checks, related party lookups — inconsistently and at varying depths. Two underwriters on the same case may reach different conclusions not because the facts differ, but because their research depth does.

**This system automates the research layer. It does not make the credit decision. It ensures every case that warrants deeper diligence arrives at the underwriter's desk with a consistent, structured intelligence brief.**

---

## The Design Question

> *Where does the model stop and the expert begin?*

Every architecture decision was made in answer to that question. The system is
designed around a hard privacy boundary between the financial analysis layer and
the external research layer. A purpose-built anonymisation mechanism ensures no
LLM receives identifiable borrower or director data alongside raw financial data
in the same context window. The mechanics of this are available in a walkthrough.

---

## System Architecture

Three components across two agents and an ingestion layer.

The system ingests a Credit Assessment Memo (CAM) — the structured Excel workbook
prepared by the credit team for each loan case.

```
CAM Workbook Upload (Gradio)
        │
        ▼ PII scan on upload — underwriter confirms before proceeding
        │
        ▼
┌───────────────────┐
│  Ingestion Layer  │  Privacy boundary enforced → Haiku classifies
│                   │  sheets → full ingestion
│                   │  Variable workbook structure → consistent output
└────────┬──────────┘
         │  anonymised data only
         ▼
┌───────────────────┐
│  Analyst Agent    │  Single structured Sonnet call
│  (Agent 1)        │  · Financial anomaly detection
│                   │  · Bureau signal interpretation
│                   │  · Director + related company extraction
│                   │  · Trend list + query list generated
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  HUMAN REVIEW     │  Underwriter reviews and edits Analyst output
│  GATE             │  Provides Company Name + CIN
│  (interrupt_      │  Privacy boundary handoff
│   before)         │  Edited values written to state
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Researcher Agent │  GPT-4o in ReAct tool-calling loop
│  (Agent 2)        │  · News search (Tavily)
│                   │  · Court + legal records search (Tavily)
│                   │  · Industry outlook search (Tavily)
│                   │  Covers: primary company + each director
│                   │  + each related company
└────────┬──────────┘
         │
         ▼
  Intelligence Brief
  GO / NOGO / NEEDS FURTHER RESEARCH
```

---

## The Human Review Gate

The interrupt is not a UX feature. It is an architecture decision.

Before the workflow starts, a PII scan fires on file upload — Company Name fields,
CIN, and PAN are detected with exact cell references, and the underwriter must
respond before Run Analysis is enabled.

Once the workflow runs, the privacy boundary is enforced throughout the analysis
phase. At the human review gate the underwriter reviews the Analyst's output,
edits the trend and query tables if needed, and provides the named entity before
the graph resumes. Details of the privacy boundary are available in a walkthrough.

`interrupt_before=["human_input"]` in LangGraph. State updated via
`graph.update_state()` before the graph resumes.

---

## Stack

| Layer | Tool |
|---|---|
| Orchestration | LangGraph (StateGraph + MemorySaver checkpointing) |
| Ingestion classification | Claude Haiku |
| Analyst reasoning | Claude Sonnet |
| External research (ReAct loop) | GPT-4o |
| Search tools | Tavily (news · court · industry) |
| Structured outputs | Pydantic |
| Interface | Gradio 6.14.0 |
| Language | Python (uv) |

Multi-model by design. Each model is assigned to the layer that matches its cost-to-capability profile.

---

## Output — The Intelligence Brief

Structured 1–2 page brief delivered to the underwriter:

- **Key Positive Signals** — bureau behavioural signals, sector tailwinds, clean legal record
- **Key Risk Signals** — adverse news, litigation, director flags, sector stress, financial anomalies
- **Resolved and Unresolved Queries** — Analyst-generated queries with resolution status; unresolved queries become the underwriter's follow-up checklist for the credit call
- **Recommended Stance** — GO / NOGO / NEEDS FURTHER RESEARCH with one paragraph rationale

Brief is downloadable as DOCX or PDF.

---

## Evaluation

| Level | Scope | Status |
|---|---|---|
| Level 1 — Ingestion | Sheet classification | Complete |
| Level 2 — Analyst | Output quality | Complete |
| Level 3 — Researcher | Search coverage and brief quality | Complete |

See [eval/EVAL_LOG.md](eval/EVAL_LOG.md) for methodology and results.

---

## What "Done" Looks Like

The build is done when a real underwriter — or someone who has sat in a credit
committee — reads the output brief and says:

- *"This would have saved me 2 hours on this case"*
- *"I would have missed the related-party flag without this"*
- *"The query list is exactly what I would have asked in the credit call"*
- *"The financial anomalies section caught things I would have caught myself — but only after 20 minutes with the spreadsheet"*

---

## Status

Version 0.5. Three-level eval framework complete — all levels passing. Privacy
boundary implemented. DOCX and PDF export complete.

---

## Deployment Note

This application processes sensitive financial data — bank statements, bureau
scores, director information — that falls under RBI data localisation requirements
and the DPDP Act 2023. Production deployment requires India-based infrastructure
(AWS Mumbai, Azure Central India, GCP Mumbai, or on-premise). The application
runs locally on the underwriter's machine for evaluation purposes.

---

## What Is Not In This Repository

Prompt engineering, domain-specific underwriting logic, and the anonymisation
mechanism are withheld from the public repository.

**Happy to walk through the full architecture** — short version or deep-dive — in a conversation.

---

## Legal and Compliance

This project is released under the [PolyForm Noncommercial 1.0.0 License](LICENSE).

See [DISCLAIMER.md](DISCLAIMER.md) for intended use and scope.

See [COMPLIANCE_GAPS.md](COMPLIANCE_GAPS.md) for known gaps relevant to production deployment in an Indian regulatory context.

See [ThirdPartyLicenses.txt](ThirdPartyLicenses.txt) for third-party dependency license attributions.

---

*Built by Asiman Kumar Panda · [linkedin.com/in/asiman-panda](https://linkedin.com/in/asiman-panda)*
