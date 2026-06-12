# Compliance Gaps

This document lists known compliance gaps relevant to deployment in an Indian
regulatory context. These are acknowledged limitations of the proof-of-concept,
not oversights. Any production deployment would need to address all items below.

---

## Data Residency

Public Anthropic (Claude) and OpenAI (GPT-4o) API endpoints are used by default.
These route data to servers outside India. A production deployment would require
either on-premise model hosting or cloud endpoints with Indian data residency
guarantees, in line with RBI IT Framework 2024 requirements for regulated entities.

## PII Transmission to Third-Party Search API

The Researcher agent sends company names and director names to Tavily, a US-based
search API, as part of external diligence queries. A production deployment would
require a data processing agreement with the search provider, PII minimisation
before transmission, and assessment against DPDP Act 2023 obligations.

## No Persistent Audit Trail

LangGraph MemorySaver is in-memory only — state is not persisted to disk or a
database. No audit log of agent decisions, search queries, or intermediate outputs
is maintained across sessions. A production deployment would require a persistent
audit trail with case ID linkage, in line with RBI outsourcing and IT framework
guidelines.

## Privacy Boundary — Known Gaps

A purpose-built anonymisation mechanism is applied before any LLM call. Known
gaps in the current implementation:

**Freeform text cells.** The anonymisation covers structured columns and
recognised table layouts. Entity names appearing in freeform text cells (e.g.
notes fields or narrative paragraphs) are not covered. A production deployment
would require a more comprehensive approach over all cell content.

**User responsibility on PII confirmation.** Company Name fields, CIN, and PAN
are detected on upload and flagged to the underwriter before any LLM call.
However, the system cannot verify that the underwriter actually removed flagged
fields before confirming. A production deployment would require server-side
enforcement.

**Horizontal layout gap.** Certain multi-column horizontal table layouts are
not covered by the current implementation. Deferred to v1.

## Court Search — Best-Effort Only

Court and tribunal record searches are performed via Tavily general web search.
This is not a dedicated legal API and does not provide structured access to
NCLT, DRT, or other tribunal databases. A production deployment would require
integration with a dedicated legal records API.

## No Authentication Layer

The application has no authentication layer. Any user with network access can
upload a CAM and run the workflow. A production deployment requires role-based
access control tied to the lending system's identity management.

## No System Integration

The workflow is initiated manually by the underwriter. There is no automated
trigger from the lending system's scoring engine. Integration is planned for v1.

## Production Deployment — Local Only for Evaluation

The application processes sensitive financial data subject to RBI data
localisation requirements and DPDP Act 2023. US-based hosting platforms
(Railway, Render, HuggingFace Spaces) are not compliant for production use.
The application runs locally on the underwriter's machine for evaluation
purposes. This is a deliberate design decision, not a gap.

---

## Dependency License Audit

All third-party dependencies have been audited via pip-licenses. No GPL
licenses detected. One LGPL dependency (pybars4) is present as a
dynamically imported library — accepted under standard Python LGPL
interpretation. Full attributions in ThirdPartyLicenses.txt.
