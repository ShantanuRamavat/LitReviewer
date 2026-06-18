# Product Requirements Document (PRD)
## Multi-Agent Research Platform

| Field | Value |
|---|---|
| Product Name | LitReviewer |
| Version | 1.0 — MVP |
| Author | Product Management |
| Date | 2026-06-16 |
| Status | Approved for Engineering |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Market Context](#3-market-context)
4. [User Personas](#4-user-personas)
5. [User Stories](#5-user-stories)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Success Metrics](#8-success-metrics)
9. [MVP Definition](#9-mvp-definition)
10. [Future Features](#10-future-features)
11. [Assumptions & Dependencies](#11-assumptions--dependencies)
12. [Risks & Mitigations](#12-risks--mitigations)
13. [Out of Scope](#13-out-of-scope)

---

## 1. Executive Summary

LitReviewer is a production-grade AI platform that automates the literature review process for PhD students. Instead of a single AI model producing a single unverified response, LitReviewer orchestrates a team of four specialised AI agents — a Researcher, Fact-Checker, Critic, and Writer — that work in sequence to produce verified, structured, and fully attributed academic literature reviews.

The platform's primary users are PhD students and academic researchers who currently spend weeks — sometimes months — manually searching databases, screening papers, synthesising findings, and drafting literature review chapters. LitReviewer compresses that workflow from weeks to hours while preserving academic rigour through built-in fact-verification, source attribution, and a quality-gate critique loop that identifies and fills research gaps before writing begins.

**PhD mode** produces 10,000–20,000-word literature reviews with thesis statements, thematic body sections, synthesis, research gap analysis, and PhD-specific annotations. **General mode** produces 3,000–5,000-word research summaries for broader use cases.

---

## 2. Problem Statement

### 2.1 The Core Problem

PhD students conducting literature reviews face two compounding problems: the sheer volume of literature to survey, and the low trustworthiness of existing AI assistance. Current AI tools produce outputs that are:

- **Unverified**: Claims are generated without cross-checking against independent sources.
- **Uncited or mis-cited**: Sources are frequently hallucinated or misattributed — academically unacceptable.
- **Shallow**: Single-pass generation misses counter-evidence, methodological nuance, and research gaps.
- **Unstructured**: Chat output is conversational prose, not the thematic, thesis-driven structure a literature review chapter requires.
- **Not thesis-aware**: General-purpose tools do not understand the difference between a web summary and an academic synthesis.

As a result, PhD students either cannot trust AI output for academic work, or spend more time correcting and restructuring it than the tool saved them.

### 2.2 The User Pain in Practice

A first-year PhD student needs to write a 15,000-word literature review chapter on transformer-based NLP architectures. With today's tools, she:

1. Manually searches Google Scholar, Semantic Scholar, and arXiv — hours to find relevant papers.
2. Reads and annotates 40–80 papers over several weeks to extract key findings.
3. Attempts to use ChatGPT to help draft sections — output is shallow, misses key papers, and cites non-existent sources.
4. Spends days identifying the thematic structure (groupings of related findings, competing schools of thought).
5. Writes the review manually, spending another week cross-referencing citations and ensuring every claim traces to a real source.
6. Gets feedback from her supervisor that the review misses a whole sub-area and needs another iteration.

This process takes 4–8 weeks for a single chapter and is the primary bottleneck delaying PhD progress.

### 2.3 Root Causes

| Pain Point | Root Cause |
|---|---|
| Hallucinated citations | LLMs generate, not verify. No internal fact-checking loop against real sources. |
| Missing research gaps | Single-pass generation has no mechanism to ask "what did we miss?" |
| Poor academic structure | Chat interfaces produce conversational prose, not thematic academic synthesis. |
| No iterative improvement | No quality-gate to loop back and fill identified gaps before writing. |
| No PhD-specific output | General tools don't know what a literature review chapter needs to contain. |

### 2.4 Why This Problem Is Worth Solving Now

- There are approximately 2.5 million active PhD students globally, with a further 10+ million postdocs, faculty, and research staff conducting systematic literature reviews annually.
- LLM capabilities have matured to the point where multi-agent coordination is reliable enough for production use.
- Retrieval-Augmented Generation (RAG) has proven that grounding LLM output in retrieved documents dramatically reduces hallucination — the single largest blocker to academic trust.
- PhD students are time-constrained and actively seeking tools they can trust; the literature review phase is universally cited as one of the most painful parts of doctoral research.

---

## 3. Market Context

### 3.1 Existing Solutions & Their Gaps

| Tool | What It Does | Critical Gap for PhD Students |
|---|---|---|
| Elicit | Structured paper search + extraction | No web search, no synthesis, no draft writing |
| Consensus | Academic claim search | No report generation, limited synthesis |
| ResearchRabbit | Paper discovery via citation graphs | No writing output; purely a discovery tool |
| Semantic Scholar | Paper indexing + AI summaries | No gap analysis, no structured review output |
| Connected Papers | Citation network visualisation | No writing; visual exploration only |
| Perplexity AI | Web search + LLM synthesis | No fact-checking layer, no academic structure |
| ChatGPT / Copilot | General-purpose chat | Hallucinates citations; no verification; no PhD structure |
| Google NotebookLM | Source-grounded Q&A | Requires manual upload; no autonomous research or writing |

### 3.2 Our Differentiation

LitReviewer is the first platform to combine all of the following for PhD-grade literature review:
- **Autonomous multi-agent research** — no manual source upload or paper selection required
- **Built-in fact-verification** at the claim level using independent web searches
- **Quality critique loop** — identifies gaps and re-researches before writing begins
- **Inline citations** on every factual statement, eliminating hallucinated references
- **PhD-mode output** — 10,000–20,000-word thematic reviews with thesis, synthesis, gap analysis, and PhD annotations
- **Persistent research history** with full session replay for iterative refinement
- **PDF export** formatted for direct inclusion in thesis appendices or supervisor review

---

## 4. User Personas

### Persona 1 — Priya, The PhD Student (Primary)

**Role:** Second-year PhD student, Computer Science (NLP focus)  
**Age:** 26  
**Experience with AI:** High technical literacy; uses AI tools daily; acutely aware of hallucination risks after an advisor flagged a false citation in an earlier draft.

**Goals:**
- Draft the literature review chapter of her thesis without spending 4–6 weeks on it
- Produce a review her supervisor will accept as rigorous — accurate citations are non-negotiable
- Identify research gaps she can position her own work against
- Have a shareable PDF to send to her supervisor for early feedback

**Frustrations:**
- ChatGPT and Perplexity produce shallow summaries that either miss key papers or cite non-existent ones
- Elicit and Consensus only cover published academic papers — misses preprints and recent blog/conference posts in her fast-moving field
- Structuring 50+ sources into a coherent thematic narrative takes weeks
- Every iteration after supervisor feedback means starting the synthesis from scratch

**Behaviors:**
- Needs a single tool that goes from research topic → verified, cited, structured literature review chapter
- Uses `phd` mode to get full 10,000–20,000-word output with gap analysis and thesis framing
- Exports the PDF and sends it to her supervisor; uses the annotations section to highlight open questions
- Runs multiple sessions on adjacent topics to build a comprehensive review

**What success looks like for Priya:**
> "I ran LitReviewer on my thesis topic Friday afternoon. By Saturday I had a 14,000-word literature review with 40+ verified citations and a section specifically identifying research gaps I can target. My supervisor said it was the most structured first draft she'd seen from a second-year student."

---

### Persona 2 — Dr. Marcus, The Research Supervisor

**Role:** Associate Professor supervising 6 PhD students  
**Age:** 44  
**Experience with AI:** Moderate; uses AI for writing assistance; strict about academic integrity and citation accuracy.

**Goals:**
- Help students get past the literature review bottleneck faster without sacrificing quality
- Receive drafts that are already well-structured, so review time is spent on intellectual content not formatting
- Ensure students can defend every source in their reviews

**Frustrations:**
- Students submit lit review drafts with hallucinated or unchecked citations, wasting his review time
- Students spend so long on the review phase that thesis progress stalls
- Existing AI tools don't produce output at the length or structure a chapter requires

**Behaviors:**
- Recommends tools to students that meet the bar for academic rigour
- Cares about the fact-checking transparency — wants students to be able to justify every claim
- Reviews PDFs, not web links

**What success looks like for Dr. Marcus:**
> "Two of my students started using LitReviewer. Their first lit review drafts came in structured and fully cited. I spent my review time on the intellectual arguments, not chasing down bad references. The fact-checking summary told me exactly which claims needed closer scrutiny."

---

### Persona 3 — Aisha, The Research Analyst (Secondary)

**Role:** Senior Research Analyst at a management consulting firm  
**Age:** 31  
**Experience with AI:** Daily user of ChatGPT and Perplexity; skeptical after being burned by hallucinated facts in a client deliverable.

**Goals:**
- Produce verified, client-ready research reports quickly
- Maintain professional credibility — accuracy is non-negotiable
- Build a personal knowledge base across repeat research domains

**Frustrations:**
- Spends more time verifying AI output than it would take to research manually
- AI tools don't produce output in the structured format clients expect

**Behaviors:**
- Does 3–5 deep research sessions per week in `general` mode
- Exports deliverables as PDFs for client delivery
- Needs to show a source chain when clients challenge a claim

**What success looks like for Aisha:**
> "I submitted a competitive analysis this morning that LitReviewer generated. I spot-checked 10 claims — all verified. I sent the PDF to the client in under two hours. Previously that took me a full day."

---

## 5. User Stories

### Epic 1: Research Initiation

**US-001** — As a PhD student, I want to enter a natural-language research topic so that I can start a literature review session without configuring anything.

**US-002** — As a PhD student, I want to select `phd` mode so that I receive a full 10,000–20,000-word literature review chapter rather than a general summary.

**US-003** — As a power user, I want to optionally configure the depth of research (number of iterations, minimum quality threshold) so that I can control the balance between speed and thoroughness.

**US-004** — As any user, I want to see a confirmation that my research has started and is being processed so that I know the system received my request.

---

### Epic 2: Real-Time Agent Progress

**US-004** — As a user, I want to see which AI agent is currently active (e.g., "Fact-Checker is running...") so that I understand what the system is doing and can trust the process.

**US-005** — As a user, I want to see a brief, plain-English description of what each agent is doing so that I don't have to understand the technical architecture to follow along.

**US-006** — As a user, I want to see a timeline of completed agent steps so that I can understand what has happened if I join mid-research or return to a session.

**US-007** — As a user, I want to be notified when a research session completes so that I don't have to watch the screen the entire time.

---

### Epic 3: Research Report

**US-008** — As a PhD student, I want the PhD-mode report to include a thesis statement, thematic body sections, a synthesis section, a conclusion, and a research gaps / PhD annotations section so that the output is structured as a genuine literature review chapter.

**US-009** — As a user, I want to read the final report with a clear title, introduction, and organised sections so that I can quickly grasp the findings without reading everything.

**US-010** — As a user, I want every factual claim in the report to have an inline citation marker so that I can trace any statement back to its source.

**US-011** — As a user, I want to see a numbered bibliography at the end of the report so that I have all sources consolidated in one place.

**US-012** — As a user, I want to click a citation to open the original source URL so that I can verify or read further.

**US-013** — As a user, I want to see a quality score for the report so that I understand how thoroughly the research was vetted.

**US-014** — As a PhD student, I want to see the identified research gaps explicitly listed so that I can use them to position my own research contribution.

---

### Epic 4: PDF Export

**US-014** — As a user, I want to download the research report as a professionally formatted PDF so that I can share it with colleagues or clients without them needing access to the platform.

**US-015** — As a user, I want the PDF to include all citations and the bibliography so that the exported document is self-contained.

**US-016** — As a user, I want the PDF to include the research query, date, and quality score in the header/footer so that the document is traceable.

---

### Epic 5: Research History

**US-017** — As a returning user, I want to see a list of all my past research sessions so that I can revisit previous work.

**US-018** — As a user, I want to search my research history by keyword so that I can find a specific past session quickly.

**US-019** — As a user, I want to open a past research session and read its full report so that I can reference earlier findings.

**US-020** — As a user, I want to delete a research session and its associated data so that I can manage my history.

---

### Epic 6: Source Attribution

**US-021** — As a user, I want to see the list of sources the Research Agent found before fact-checking so that I understand where the raw information came from.

**US-022** — As a user, I want sources to show their domain name and page title so that I can judge their credibility at a glance.

**US-023** — As a user, I want to see which sources were used to verify (or refute) specific claims so that I understand the fact-checking evidence chain.

---

### Epic 7: System Health & Reliability

**US-024** — As a user, if the research process fails mid-run, I want to receive an informative error message (not a blank screen) so that I know what happened and what to do next.

**US-025** — As an operator, I want a `/health` endpoint that reports the status of all downstream services so that I can monitor system health without logging into each service.

---

## 6. Functional Requirements

Requirements are prioritized using MoSCoW: **M** = Must Have, **S** = Should Have, **C** = Could Have, **W** = Won't Have (this release).

### 6.1 Research Session Management

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | System shall accept a free-text research query of up to 500 characters | M |
| FR-002 | System shall create a unique session ID for every research request | M |
| FR-003 | System shall persist session state (query, status, timestamps) to a database | M |
| FR-004 | System shall support optional parameters: `max_iterations` (1–3) and `min_quality_score` (0.0–1.0) | S |
| FR-005 | System shall allow a session to be cancelled while in progress | S |
| FR-006 | System shall enforce a maximum session runtime of 5 minutes before timing out | M |
| FR-007 | System shall support 10 concurrent research sessions without degradation | M |

### 6.2 Agent Execution

| ID | Requirement | Priority |
|---|---|---|
| FR-010 | ResearchAgent shall query Tavily Search API and return a minimum of 5 findings per run | M |
| FR-011 | ResearchAgent shall retrieve contextually relevant passages from the Qdrant vector store | M |
| FR-012 | Each finding shall carry a source URL, extracted text, and a relevance score | M |
| FR-013 | FactCheckerAgent shall evaluate every finding from ResearchAgent and assign `verified: bool` and `confidence: float` | M |
| FR-014 | FactCheckerAgent shall record counter-sources for any finding it cannot verify | S |
| FR-015 | CriticAgent shall produce a quality score between 0.0 and 1.0 for the current set of findings | M |
| FR-016 | CriticAgent shall produce a structured critique listing specific gaps and missing perspectives | M |
| FR-017 | If quality score is below the configured threshold, the graph shall loop back to ResearchAgent for a maximum of 3 iterations total | M |
| FR-018 | WriterAgent shall support two modes: `general` (3,000–5,000 words: intro + 2–3 body sections + synthesis + conclusion) and `phd` (10,000–20,000 words: intro + 3–5 thematic body sections + synthesis + conclusion + PhD annotations with research gap analysis) | M |
| FR-019 | CitationAgent shall assign a numbered citation marker to every factual sentence in the report body | M |
| FR-020 | CitationAgent shall produce a consolidated bibliography in numbered order | M |
| FR-021 | Agent execution steps shall be persisted to the `agent_logs` table with input, output, and duration | S |

### 6.3 RAG Pipeline

| ID | Requirement | Priority |
|---|---|---|
| FR-030 | System shall chunk source documents at 512 tokens with 64-token overlap before embedding | M |
| FR-031 | System shall embed chunks using BAAI/bge-large-en-v1.5 (1024-dimensional vectors) | M |
| FR-032 | System shall store embeddings in a Qdrant collection named `research_docs` | M |
| FR-033 | System shall support filtered retrieval by `session_id` to scope results to the current session | M |
| FR-034 | Default retrieval shall return top-8 most similar chunks by cosine similarity | M |

### 6.4 Streaming

| ID | Requirement | Priority |
|---|---|---|
| FR-040 | System shall emit Server-Sent Events (SSE) for the following event types: `agent_start`, `agent_output`, `agent_end`, `graph_complete`, `error` | M |
| FR-041 | SSE events shall include: `event_type`, `agent_name`, `data` (plain text description), `timestamp` | M |
| FR-042 | SSE stream shall remain open until the `graph_complete` or `error` event is emitted | M |
| FR-043 | Frontend shall display a real-time agent progress tracker updating on each SSE event | M |
| FR-044 | Frontend shall gracefully reconnect if the SSE connection drops | S |

### 6.5 Report Viewing

| ID | Requirement | Priority |
|---|---|---|
| FR-050 | System shall store the full structured report in the database as JSONB | M |
| FR-051 | Frontend shall render the report with a title, executive summary, section headings, body text, and inline citation markers | M |
| FR-052 | Frontend shall render a numbered bibliography section below the report body | M |
| FR-053 | Each citation number shall be a hyperlink opening the source URL in a new tab | M |
| FR-054 | Frontend shall display the report's quality score prominently | S |
| FR-055 | Frontend shall display a source panel listing all found sources with title and domain | S |

### 6.6 PDF Export

| ID | Requirement | Priority |
|---|---|---|
| FR-060 | System shall generate a PDF from the report content on demand | M |
| FR-061 | Generated PDF shall include: report title, research query, date generated, quality score, all sections, bibliography | M |
| FR-062 | PDF shall include page numbers and a header with the platform name | S |
| FR-063 | PDF generation shall complete within 10 seconds | M |
| FR-064 | PDF shall be served as a file download with filename `report-{session_id}.pdf` | M |

### 6.7 Research History

| ID | Requirement | Priority |
|---|---|---|
| FR-070 | System shall list all research sessions in reverse chronological order | M |
| FR-071 | History list shall display: query text (truncated), status, date, and a link to the report | M |
| FR-072 | History shall support pagination (20 items per page) | M |
| FR-073 | History shall support filtering by status (running / complete / failed) | S |
| FR-074 | User shall be able to delete any session and all its associated data | M |

### 6.8 System Operations

| ID | Requirement | Priority |
|---|---|---|
| FR-080 | System shall expose a `/health` endpoint reporting status of PostgreSQL, Qdrant, Redis, and Groq API | M |
| FR-081 | All services shall be orchestratable via a single `docker compose up` command | M |
| FR-082 | System shall use environment variables for all secrets and configuration | M |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| ID | Requirement | Target | Measurement |
|---|---|---|---|
| NFR-P01 | End-to-end research session (1 iteration) | < 60 seconds | 95th percentile |
| NFR-P02 | SSE first event latency (time to first agent_start event) | < 3 seconds | 95th percentile |
| NFR-P03 | PDF generation time | < 10 seconds | 95th percentile |
| NFR-P04 | Qdrant similarity search latency | < 100ms | 95th percentile |
| NFR-P05 | API endpoint response time (non-streaming) | < 500ms | 95th percentile |
| NFR-P06 | Frontend initial page load | < 2 seconds | LCP on 10Mbps connection |

### 7.2 Reliability

| ID | Requirement | Target |
|---|---|---|
| NFR-R01 | System uptime | 99.5% (development target) |
| NFR-R02 | Research session success rate (no unhandled errors) | > 95% |
| NFR-R03 | Agent failure shall not crash the session — system degrades gracefully with partial output | Always |
| NFR-R04 | Groq API transient failures (rate limits, 5xx) shall be retried with exponential backoff (max 6 attempts, exact retry-after delay parsed from error) | Always |
| NFR-R05 | If LangGraph exceeds max iterations, session shall terminate with a partial report rather than an error | Always |

### 7.3 Scalability

| ID | Requirement | Target |
|---|---|---|
| NFR-S01 | Support concurrent research sessions | 10 (MVP) |
| NFR-S02 | Qdrant collection growth | Supports up to 1M vectors without re-architecture |
| NFR-S03 | PostgreSQL record volume | Up to 100K sessions without query degradation |
| NFR-S04 | System shall be horizontally scalable at the API layer via additional Docker replicas | Design target |

### 7.4 Security

| ID | Requirement |
|---|---|
| NFR-SEC01 | All API keys and secrets shall be stored as environment variables, never hardcoded |
| NFR-SEC02 | API endpoints shall validate and sanitize all user inputs |
| NFR-SEC03 | Rate limiting shall be applied to research start endpoint (max 10 requests/minute/IP) |
| NFR-SEC04 | PDF generation shall sanitize report content to prevent server-side injection |
| NFR-SEC05 | Database queries shall use parameterized statements; no raw string interpolation |

### 7.5 Maintainability

| ID | Requirement |
|---|---|
| NFR-M01 | All agent modules shall be independently unit-testable without running the full graph |
| NFR-M02 | Code coverage shall reach minimum 70% on agent logic and service layer |
| NFR-M03 | All configuration shall be centralized in a single `config.py` using `pydantic-settings` |
| NFR-M04 | Structured logging (JSON format) shall be applied to all agent executions and API requests |
| NFR-M05 | Database schema changes shall use Alembic migration files; no manual schema edits |

### 7.6 Usability

| ID | Requirement |
|---|---|
| NFR-U01 | The research input flow shall require no more than 2 user actions to start a session (type query → click submit) |
| NFR-U02 | Agent progress shall use plain English, not technical agent names or system jargon |
| NFR-U03 | Error states shall always display a user-facing message with suggested next action |
| NFR-U04 | PDF export shall require a single click from the report view |
| NFR-U05 | The UI shall be responsive and usable on screens >= 1024px wide |

---

## 8. Success Metrics

### 8.1 Engagement Metrics (Primary)

| Metric | Definition | MVP Target |
|---|---|---|
| Research Sessions Started | Total sessions initiated per day | 20/day (internal beta) |
| PhD Mode Adoption Rate | Sessions using `mode=phd` / total sessions | > 60% (primary use case) |
| Session Completion Rate | Sessions reaching `complete` status / sessions started | > 90% |
| Report View Rate | Sessions where the user opened the final report | > 85% |
| PDF Export Rate | Reports that result in a PDF download | > 50% (higher for academic users) |
| Return Visit Rate | Users who start a second session within 7 days | > 50% |
| History Access Rate | Users who access their research history at least once per week | > 40% |

### 8.2 Quality Metrics (Trust Signals)

| Metric | Definition | MVP Target |
|---|---|---|
| Average Report Quality Score | Mean CriticAgent quality score across all sessions | > 0.75 |
| Fact Verification Rate | % of findings that pass FactCheckerAgent review | > 80% |
| Citation Coverage | % of factual sentences that carry a citation marker | 100% |
| Source URL Validity | % of citation URLs that resolve to live pages | > 95% |
| Average Findings per Session | Number of unique sources consulted per session | > 8 |

### 8.3 Performance Metrics (System Health)

| Metric | Definition | Target |
|---|---|---|
| P95 Session Duration | 95th percentile time from session start to `graph_complete` | < 60s |
| P95 First SSE Latency | Time from session start to first `agent_start` event | < 3s |
| API Error Rate | HTTP 5xx responses / total requests | < 1% |
| Uptime | System availability as measured by health check | > 99.5% |

### 8.4 Satisfaction Metrics (Qualitative)

| Metric | Method | MVP Target |
|---|---|---|
| User satisfaction with report accuracy | Post-session thumbs up/down | > 80% positive |
| User satisfaction with report structure | Post-session thumbs up/down | > 80% positive |
| PhD user: supervisor acceptance rate | User-reported: "supervisor approved the draft" | > 50% (beta signal) |
| Net Promoter Score | NPS survey after 5 sessions | > 40 |

### 8.5 Leading Indicators of Product-Market Fit

The following behaviors, observed in beta users, will signal PMF:

1. PhD users complete a session and immediately start a second session on an adjacent chapter topic.
2. Users share exported PDFs with their supervisors (tracked via download count).
3. Users return to history to re-read or build on a previous review.
4. PhD users explicitly cite LitReviewer as accelerating their thesis timeline.
5. Users explicitly mention the fact-checking transparency as a reason to trust the output over other AI tools.

---

## 9. MVP Definition

### 9.1 What the MVP Is

The Minimum Viable Product is the smallest version of the platform that delivers the core value proposition: **a user can ask a research question and receive a verified, cited, structured report that they trust enough to act on or share.**

### 9.2 MVP Scope

The following features are in scope for MVP:

| Feature | Description |
|---|---|
| Research query input | Free-text research query submission form |
| 5-agent pipeline | Research → Fact-Check → Critic → Writer → Citation in sequence |
| Quality-gate loop | CriticAgent can trigger up to 2 additional research iterations |
| Real-time agent progress | SSE stream showing live agent steps with plain-English descriptions |
| Structured report view | Report with title, executive summary, sections, inline citations |
| Numbered bibliography | All sources listed with title and URL at the report end |
| PDF export | One-click download of a formatted PDF report |
| Research history | Paginated list of past sessions with links to reports |
| Session deletion | Users can delete any past session |
| RAG pipeline | Source documents embedded and retrievable via Qdrant |
| Full Docker Compose stack | PostgreSQL, Qdrant, Redis, backend, frontend via single command |

### 9.3 What the MVP Is Not

The following are explicitly **excluded** from MVP to maintain focus:

| Feature | Reason for Exclusion |
|---|---|
| User authentication / accounts | Adds scope without proving core value first |
| Session refinement / re-run with edits | Can be approximated by starting a new session |
| Confidence score UI visualization | Backend computes it; UI display deferred to v1.1 |
| Cross-encoder reranking | Minor quality improvement; adds latency and complexity |
| Mobile responsiveness | Target users are desktop-first |
| Multi-language support | English-only for initial market validation |
| Email / Slack delivery of reports | Out of product scope for v1 |
| Collaborative sessions | Requires multi-tenancy architecture |

### 9.4 MVP Exit Criteria

The MVP is complete and ready for beta user testing when all of the following are true:

- [ ] A user can start a research session from the UI and receive a complete report within 90 seconds for simple queries.
- [ ] The report contains at least 3 sections and a bibliography with working URLs.
- [ ] Every factual sentence in the report carries an inline citation marker.
- [ ] The user can download a PDF that matches the on-screen report.
- [ ] Past research sessions appear in the history and their reports are accessible.
- [ ] The system handles an agent failure gracefully without crashing the session.
- [ ] `docker compose up` starts all services cleanly on a fresh machine with only a `.env` file.
- [ ] Unit test coverage is >= 70% on the agents and services layers.

---

## 10. Future Features

Features are organized by release tier based on validated user need.

### 10.1 v1.1 — Trust & Transparency (4–6 weeks post-MVP)

| Feature | User Need It Addresses |
|---|---|
| **Confidence score visualization** | Show per-claim confidence as a colored badge (green/amber/red); addresses Leo's need to distinguish verified from uncertain claims |
| **Source preview on hover** | Hover a citation number to see a snippet from the source page; reduces the friction of clicking through every citation |
| **Counter-source display** | Show the FactChecker's counter-sources for disputed claims; full transparency on conflicting evidence |
| **Session refinement** | Add a follow-up instruction to an existing session ("focus more on the EU regulatory angle") and re-run from CriticAgent onward |
| **Report quality breakdown** | Expand quality score into sub-scores: depth, breadth, source diversity, recency |

### 10.2 v1.2 — Productivity & Power Users (8–10 weeks post-MVP)

| Feature | User Need It Addresses |
|---|---|
| **Research history search** | Keyword search across past session queries and report content; directly addresses Maya's repeated-research problem |
| **Comparative reports** | Run research on the same topic 30 days apart and diff the two reports; addresses Arjun's need to track landscape changes |
| **Saved query templates** | Pre-configure research parameters for recurring query types (e.g., "competitor analysis template") |
| **Keyboard-first navigation** | Full keyboard shortcuts for power users; Arjun's persona explicitly prefers keyboard-heavy UX |
| **Export to Markdown** | Export report as a Markdown file in addition to PDF; integrates with Notion, Obsidian, GitHub |

### 10.3 v2.0 — Collaboration & Scale (3–4 months post-MVP)

| Feature | User Need It Addresses |
|---|---|
| **User accounts & authentication** | Enable per-user history isolation; prerequisite for any team feature |
| **Team workspaces** | Share research sessions and reports within a team; addresses collaborative research use cases |
| **Private document ingestion** | Upload internal PDFs, Word documents, or paste URLs to include in the RAG context; addresses enterprise research needs |
| **Shared report links** | Generate a read-only URL to share a report with external stakeholders without platform access |
| **Scheduled research** | Configure a query to run on a schedule (daily/weekly) and deliver results to email or Slack; addresses news monitoring use cases |

### 10.4 v2.5 — Intelligence Layer (4–6 months post-MVP)

| Feature | User Need It Addresses |
|---|---|
| **Cross-encoder reranking** | Improve RAG relevance for long-tail queries; technical quality improvement |
| **Agent parallelism** | Run ResearchAgent and FactCheckerAgent partially in parallel to reduce total session time |
| **Multi-LLM routing** | Route agents to different models by task (e.g., Groq for Research/FactCheck, Anthropic for Writing); cost vs. quality optimization |
| **Research graph / knowledge map** | Visualize relationships between findings across multiple sessions on the same topic |
| **Evaluation framework** | Automated benchmarking of report quality against curated ground-truth datasets; enables model and prompt regression testing |

### 10.5 v3.0 — Platform (6–12 months post-MVP)

| Feature | User Need It Addresses |
|---|---|
| **Headless API** | Allow third-party applications to trigger research sessions and retrieve reports programmatically; opens a developer ecosystem |
| **Custom agent personas** | Users can configure agent system prompts (e.g., make the Critic adversarial, make the Writer more concise) |
| **Retrieval feedback loop** | User upvotes/downvotes on sources train a personalized reranker over time |
| **Multi-language support** | Research in and output reports in languages beyond English; international market expansion |
| **Enterprise SSO & RBAC** | SAML/OIDC login and role-based access controls; required for enterprise sales |

---

## 11. Assumptions & Dependencies

### Assumptions

1. **Groq API (llama-3.3-70b-versatile)** is the primary LLM provider. It is free-tier accessible and sufficient for all agent tasks. Anthropic (Claude Sonnet) is supported as an alternative via `LLM_PROVIDER=anthropic`.
2. **Tavily Search API** provides sufficient coverage of recent web content, including preprints, blog posts, and conference proceedings relevant to academic research.
3. **BAAI/bge-large-en-v1.5** can run on the development/staging host machine without GPU acceleration and achieve acceptable embedding latency (< 500ms per batch).
4. **Target users are English-language** PhD students and researchers; multi-language is a post-MVP concern.
5. Users understand that LitReviewer produces a first-pass literature review that requires human review before inclusion in a thesis submission. The tool accelerates the process; it does not replace academic judgment.
6. **No authentication** is required for MVP; the platform operates as a single-user local or internal deployment.

### External Dependencies

| Dependency | Type | Risk if Unavailable |
|---|---|---|
| Groq API (llama-3.3-70b-versatile) | External API (primary) | All agent execution fails; switch to Anthropic via `LLM_PROVIDER=anthropic` as fallback |
| Anthropic Claude API | External API (alternative) | Optional; only needed if `LLM_PROVIDER=anthropic` |
| Tavily Search API | External API | ResearchAgent cannot gather real-time web findings |
| BAAI/bge-large-en-v1.5 model weights | HuggingFace model download | RAG pipeline cannot embed or retrieve |
| Qdrant (Docker) | Self-hosted | RAG pipeline unavailable; agents fall back to web-only |
| PostgreSQL (Docker) | Self-hosted | Sessions, reports, and history cannot be persisted |

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM hallucination passes through FactChecker | Medium | High | FactChecker uses independent Tavily queries (not the same sources as ResearchAgent) to cross-validate; confidence scores flag uncertain claims |
| Groq free-tier rate limits degrade session times | Medium | Medium | Retry with exact wait time parsed from error message; daily TPD limit surfaces a clear error rather than looping |
| Tavily search returns irrelevant or low-quality sources | Medium | Medium | Relevance scoring on findings; CriticAgent quality gate loops back for more research if quality is low |
| Infinite loop in quality-gate (CriticAgent always scores below threshold) | Low | High | Hard cap of 3 total iterations enforced in LangGraph edge logic |
| BAAI/bge-large-en-v1.5 embedding too slow on CPU | Low | Medium | Benchmark in Milestone 4; fallback to bge-base-en-v1.5 (smaller, faster) if latency exceeds 1s per batch |
| PDF generation library (WeasyPrint) has complex HTML/CSS support | Medium | Low | Contain PDF template to simple, tested HTML; test PDF generation in Milestone 6 before committing to library |
| Users misuse the platform (spam research queries) | Low | Medium | Rate limiting (10 requests/min/IP) enforced at API layer in Milestone 7 |

---

## 13. Out of Scope

The following are explicitly out of scope for all planned releases and will require a separate product decision to include:

- **Real-time collaboration** (multiple users editing the same report simultaneously)
- **Custom LLM fine-tuning** on research domain data
- **Browser extension** for in-page research triggering
- **Voice input** for research queries
- **Image or video source analysis** (agents are text-only)
- **Legal, medical, or financial advice disclaimers** (legal/compliance review required before launch in regulated domains)
- **GDPR / data residency compliance** (requires separate legal and engineering effort)

---

*Document ends. For technical implementation details, refer to the System Design Document (`docs/system-design.md`) and API Specification (`docs/api-spec.md`).*
