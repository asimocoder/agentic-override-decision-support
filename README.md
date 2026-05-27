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

Every architecture decision was made in answer to that question. The system is designed around a hard privacy boundary: the anonymised financial analysis and the named-entity external research are kept strictly separate, with a human review gate between them.

---

## System Architecture

Three components across two agents and an ingestion layer.

The system ingests a Credit Assessment Memo (CAM) — the structured Excel workbook
prepared by the credit team for each loan case.

```
CAM Workbook Upload (Gradio)
        │
        ▼
┌───────────────────┐
│  Ingestion Layer  │  Haiku classifies sheets; pure Python ingests data
│                   │  Variable workbook structure → consistent output
└────────┬──────────┘
         │  anonymised data only — no company name, CIN, or PAN
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
│  (interrupt_      │  Edited values written to state before Researcher runs
│   before)         │
└────────┬──────────┘
         │  named entity now enters the workflow
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

The Analyst never sees the company name, CIN, or PAN — by design. The underwriter reviews the Analyst's output, edits the trend and query tables if needed, and only then provides the named entity to the Researcher. This enforces a clean privacy boundary between the anonymised analysis layer and the external research layer.

`interrupt_before=["human_input"]` in LangGraph. State updated via `graph.update_state()` before the graph resumes.

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
| Interface | Gradio 6.0 |
| Language | Python (uv) |

Multi-model by design. Each model is assigned to the layer that matches its cost-to-capability profile.

---

## Output — The Intelligence Brief

Structured 1–2 page brief delivered to the underwriter:

- **Key Positive Signals** — bureau behavioural signals, sector tailwinds, clean legal record
- **Key Risk Signals** — adverse news, litigation, director flags, sector stress, financial anomalies
- **Resolved and Unresolved Queries** — Analyst-generated queries with resolution status; unresolved queries become the underwriter's follow-up checklist for the credit call
- **Recommended Stance** — GO / NOGO / NEEDS FURTHER RESEARCH with one paragraph rationale

---

## What "Done" Looks Like

The build is done when a real underwriter reads the output and says:

- *"This would have saved me 2 hours on this case"*
- *"I would have missed the related-party flag without this"*
- *"The query list is exactly what I would have asked in the credit call"*

---

## Status

First end-to-end run complete. Currently in testing and evaluation design phase.

---

## What Is Not In This Repository

Prompt engineering and domain-specific underwriting logic are withheld from the public repository.

**Happy to walk through the full architecture** — short version or deep-dive — in a conversation.

---

## Legal and Compliance

This project is released under the [PolyForm Noncommercial 1.0.0 License](LICENSE).

See [DISCLAIMER.md](DISCLAIMER.md) for intended use and scope.

See [COMPLIANCE_GAPS.md](COMPLIANCE_GAPS.md) for known gaps relevant to production deployment in an Indian regulatory context.

---

*Built by Asiman Kumar Panda · [linkedin.com/in/asiman-panda](https://linkedin.com/in/asiman-panda)*
