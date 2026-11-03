# Product Requirements Document (PRD)
## Project: SentinelReview — AI-Powered Automated Code Reviewer ($0 Stack Hackathon Edition)

### 1. Executive Summary & Intent
**SentinelReview** is a zero-cost, local, high-precision automated code review system engineered to solve the "noise and false-positive fatigue" plaguing modern developer tools. Rather than simply querying an LLM with raw code diffs (which produces hallucinations, nitpicks, and missed bugs), SentinelReview implements a **hybrid static-analysis + adversarial verification pipeline**:
1. Fast, deterministic SAST scanning via local **Semgrep** rules (offline-capable).
2. Heuristic prompt-injection pre-scanning to block malicious prompts disguised in comments or PR diffs ("Comment and Control" attacks).
3. Contextual LLM reasoning powered by **Groq** (primary ultra-fast inference) and **Google Gemini** (fallback).
4. Strict **adversarial verification pass** that tests each proposed candidate finding against the codebase facts to drop false positives and compute empirical filter metrics.

The entire application runs locally, requires zero paid APIs ($0 free tiers on Groq & Gemini Flash), zero GPUs, and delivers actionable, line-anchored findings with concrete copy-ready code fixes.

---

### 2. Market Landscape & Competitor Teardown

| Competitor | Core Architecture | Context Model | Strengths | Vulnerabilities / Limitations |
| :--- | :--- | :--- | :--- | :--- |
| **CodeRabbit** | Cloud sandboxed clone, 50+ linters/analyzers, multi-agent review | Full repository + static analysis | High signal-to-noise, team learning | Expensive SaaS, heavyweight cloud orchestration, slow cold-starts |
| **Greptile** | Semantic repo graph, dynamic subgraph retrieval per PR | Whole-repo graph | Cross-file ripple effect detection | High false positive rate, token-heavy, costly infrastructure |
| **Qodo (PR-Agent)** | Context Engine (RAG + custom embeddings) | Cross-repo / monorepo | Integrated test & PR generation | Heavy setup, token exhaustion on free tiers |
| **SonarQube / Snyk** | Rule-based AST / taint dataflow + AI Assurance | Deterministic rules + AI filter | Enterprise compliance & governance | Misses cross-boundary logic flaws lacking explicit static patterns |

#### SentinelReview Strategic Wedge:
We do not attempt to index a 100k-line monorepo or run 50 cloud workers. Our hackathon wedge is:
1. **Hybrid SAST + Adversarial LLM Verification**: Semgrep flags candidates; LLM reasons over the full file and explains; a separate verification agent drops false positives, displaying an empirical **"N False Positives Filtered"** counter.
2. **Defensive Pre-Scan for Prompt Injection**: Actively identifies adversarial injection strings embedded in source comments before models process instructions.
3. **Resilient Dual-Provider Free Stack**: Seamless Groq (Llama-3.3/Qwen/gpt-oss) $\leftrightarrow$ Gemini 2.5 Flash failover with dynamic model self-correction.
4. **$0 Footprint**: Runs on 8GB laptops with zero vector DB overhead.

---

### 3. User Personas & Core Workflows

#### Primary Persona: Solo Developer & PR Reviewer
- **Goal**: Rapidly audit code changes or pull request unified diffs before merging.
- **Pain Points**: Linters emit too many nitpicks; LLMs hallucinate non-existent syntax errors or ignore security vulnerabilities across unaffected helper functions.
- **Workflow**:
  1. Open SentinelReview at `http://localhost:8000`.
  2. Select language (`Python`, `JavaScript`, `Other`) or click a sample from the **"Load Sample"** dropdown.
  3. Paste unified diff or full code file (with optional `is_diff` checkbox).
  4. Click **"Review Code"**.
  5. View summary banner, severity breakdown badges, provider used, and false-positive reduction metric.
  6. Inspect inline findings categorized into **Bugs**, **Security** (with CWE tags), and **Style**.
  7. Copy one-click suggested fixes.

---

### 4. Functional Specifications & System Requirements

#### 4.1 Ingestion & Diff Reconstruction
- Supports both raw source files and unified diffs (`diff --git`, `@@ -x,y +x,y @@`).
- When `is_diff` is detected, reconstructs the updated post-change file (retaining context and `+` lines, discarding `-` lines and patch metadata) so all line numbers match the new state.

#### 4.2 Static Analysis (Semgrep)
- Runs local Semgrep subprocess against a temporary file.
- Bundled offline rules (`rules/local-rules.yml`) targeting:
  - CWE-89: SQL Injection via string interpolation/f-strings.
  - CWE-798: Hardcoded credentials or API keys.
  - CWE-95: Dangerous `eval` / `exec` usage on untrusted input.
- Gracefully falls back to local rules if registry rules (`p/default`, `p/security-audit`) are unreachable offline.

#### 4.3 Prompt Injection Defense
- Scans comments and string literals for evasion and hijacking phrases (e.g., `"ignore previous instructions"`, `"this file is audited"`, `"approved by security"`, `"mark this as safe"`).
- Automatically converts hits into `High` severity security findings (`source="injection-scan"`).

#### 4.4 LLM Review & Verification Engine
- Dual-provider orchestration via `openai` SDK:
  - Primary: Groq (`api.groq.com/openai/v1`).
  - Fallback: Google Gemini (`generativelanguage.googleapis.com/v1beta/openai/`).
- Runtime Model Self-Correction: If a model ID returns a 404, queries `/models` endpoint to auto-select an available flash/chat model.
- Robust JSON Parser: Strips markdown fences, extracts outermost JSON bounds, and executes a single repair prompt on syntax failure.
- Adversarial Verifier: Dedicated verification prompt evaluates each proposed candidate, outputting `keep: boolean` and `reason`.
- Graceful Degradation: If both LLMs are unreachable or keys are omitted, gracefully serves SAST + injection findings only (`provider_used="sast-only"`).

#### 4.5 API Contract Specifications
- `GET /`: Serves single-page UI (`static/index.html`).
- `GET /api/samples`: Returns pre-seeded test samples (`SAMPLE: Python SQL Injection`, `SAMPLE: JavaScript Forgotten Await`, `SAMPLE: Hidden Prompt Injection`).
- `POST /api/review`:
  - Request: `{"code": string, "language": string, "is_diff": bool}`
  - Response:
    ```json
    {
      "summary": "2-3 sentence PR-style summary",
      "counts": {
        "high": 1,
        "medium": 0,
        "low": 0,
        "false_positives_filtered": 2
      },
      "provider_used": "groq|gemini|sast-only",
      "findings": [
        {
          "category": "bug|security|style",
          "severity": "high|medium|low",
          "confidence": 0.95,
          "line": 14,
          "title": "SQL Injection in User Query",
          "explanation": "Direct f-string concatenation allows arbitrary SQL execution.",
          "suggested_fix": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
          "cwe": "CWE-89",
          "source": "semgrep|llm|injection-scan"
        }
      ]
    }
    ```

---

### 5. Non-Goals
- No persistent database or user accounts.
- No third-party vector databases, embeddings, or RAG models.
- No multi-repo or long-running background tasks.
- No external CDN dependencies for the frontend.

---

### 6. Acceptance Criteria & Definition of Done
1. App boots cleanly on port 8000 via Uvicorn.
2. All 3 seed samples load effortlessly and deliver verified findings:
   - Sample A: SQL injection detected and flagged with CWE-89.
   - Sample B: JavaScript async bug caught.
   - Sample C: Both prompt-injection warning and the underlying vulnerability flagged.
3. System functions in SAST-only mode with a visible notice if API keys are unset.
4. Security headers and CSP active on all responses.
5. Zero secrets committed to Git repository.
