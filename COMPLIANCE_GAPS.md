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

## No PII Masking Layer

No PII masking or redaction layer is applied before CAM data is passed to the
LLM ingestion pipeline. A production deployment would require a masking layer
to redact or tokenise sensitive fields before LLM processing.

---

*This document will be updated as the project evolves toward a production path.*
