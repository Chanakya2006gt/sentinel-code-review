# SentinelReview — Implementation Plan & Verification Milestones

## Overview
This implementation plan outlines the sequential milestones required to construct, test, and verify SentinelReview according to the user specification and project Definition of Done.

---

## Milestone 1: Project Scaffolding & Environment Setup
- **Tasks**:
  1. Freeze installed package versions into `requirements.txt`.
  2. Create `.env.example` with placeholder keys (`GROQ_API_KEY=`, `GEMINI_API_KEY=`).
  3. Create `.gitignore` to enforce zero secret leaks (`.env`, `__pycache__/`, `.venv/`, `*.pyc`).
  4. Scaffold `app/__init__.py`, `app/main.py`, `static/index.html`.
- **Verification**:
  - Run `uvicorn app.main:app` and verify `GET /` returns status 200 with the basic HTML page.

---

## Milestone 2: Static Analysis (Semgrep) & Offline Rule Bundling
- **Tasks**:
  1. Write `rules/local-rules.yml` covering:
     - CWE-89: Python SQL injection via string formatting/f-strings.
     - CWE-798: Hardcoded credentials or API keys.
     - CWE-95: Dangerous `eval` / `exec` usage on untrusted inputs.
  2. Implement `app/sast.py`:
     - Creates isolated temp file with proper extension (`.py`, `.js`).
     - Invokes `semgrep` with offline rule set and optional registry packs.
     - Parses JSON output into standardized finding schema with CWE mapping.
     - Guarantees temp file cleanup in `finally` block.
- **Verification**:
  - Run `app/sast.py` against a test Python SQL-injection snippet and verify CWE-89 is emitted.

---

## Milestone 3: Prompt-Injection Pre-Scanner
- **Tasks**:
  1. Implement `app/injection.py`:
     - Case-insensitive regex/keyword search for adversarial triggers (`ignore previous instructions`, `this file is audited`, `approved by security`, `mark this as safe`, `you are now`, `system prompt`, etc.).
     - Generates High-severity security findings with source `injection-scan` and quotes the offending line.
- **Verification**:
  - Run `app/injection.py` against sample comment strings and assert findings are generated.

---

## Milestone 4: Dual-Provider LLM Engine & Resilient JSON Parser
- **Tasks**:
  1. Implement `app/prompts.py` using the exact prompt strings from the specification.
  2. Implement `app/models.py` with Pydantic contracts for `Finding`, `ReviewCounts`, `ReviewResult`, `ReviewRequest`.
  3. Implement `app/llm.py`:
     - Dual-provider orchestration (Groq primary, Gemini fallback).
     - Model self-correction on 404/not found errors by querying `/models`.
     - Robust JSON extractor and single repair call fallback.
     - Graceful degradation to `sast-only` if no keys or all providers fail.
- **Verification**:
  - Test `app/llm.py` with mock / live inputs and assert valid JSON parsing.

---

## Milestone 5: Pipeline Orchestrator & Diff Reconstruction
- **Tasks**:
  1. Implement `app/reviewer.py`:
     - Unified diff detection and reconstruction into new file content.
     - Coordinated execution of Semgrep, injection pre-scan, LLM review, and adversarial verification.
     - False-positive filtering and metric calculation (`counts.false_positives_filtered`).
     - Merge, deduplication by `(line, title)`, and severity sorting.
- **Verification**:
  - Execute `reviewer.py` on unified diff inputs and verify line numbering and output consistency.

---

## Milestone 6: API Endpoints & Seed Samples
- **Tasks**:
  1. Implement `app/samples.py` with 3 pre-seeded samples (`SAMPLE: Python SQL Injection`, `SAMPLE: JavaScript Forgotten Await`, `SAMPLE: Hidden Prompt Injection`).
  2. Implement API routes in `app/main.py`:
     - `GET /api/samples`
     - `POST /api/review`
     - Security headers and CORS middleware.
- **Verification**:
  - Test endpoints via `httpx` or curl and verify exact JSON schema compliance.

---

## Milestone 7: Frontend Interface (`static/index.html`)
- **Tasks**:
  1. Build self-contained `static/index.html` with dark-mode aesthetic.
  2. Implement sample loader dropdown, language picker, diff checkbox, and code editor.
  3. Implement metrics bar, provider status badge, and dynamic finding cards with one-click fix copy.
  4. Ensure zero external dependencies/CDNs.
- **Verification**:
  - Load UI in browser and test end-to-end review interaction across all 3 samples.

---

## Milestone 8: Automated Verification & Definition of Done
- **Tasks**:
  1. Write automated test suite (`tests/test_api.py`) verifying all endpoints, samples, and graceful degradation.
  2. Run Playwright smoke tests testing UI interactions and route rendering.
  3. Log all commands and URLs into `DECISION_LOG.md`.
- **Verification**:
  - 100% test pass rate with clean build.
