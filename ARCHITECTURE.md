# SentinelReview — System Architecture & Topology

## 1. System Overview & Component Boundaries

SentinelReview employs a layered, pipeline-driven architecture designed to balance deterministic static analysis speed with LLM contextual reasoning. The application runs as a unified FastAPI service hosting both static assets and API endpoints.

```mermaid
flowchart TD
    subgraph Client["Client Tier (Browser)"]
        UI["Vanilla JS / CSS Single Page Application (static/index.html)"]
    end

    subgraph Server["Application Server Tier (FastAPI / Uvicorn)"]
        Router["HTTP Router (app/main.py)"]
        Orchestrator["Pipeline Orchestrator (app/reviewer.py)"]
        
        subgraph Pipeline["Multi-Stage Review Pipeline"]
            DiffEngine["Diff Reconstructor (Unified Diff -> Full New File)"]
            InjectionScanner["Adversarial Prompt-Injection Scanner (app/injection.py)"]
            SASTRunner["Semgrep Subprocess Engine (app/sast.py)"]
            LLMClient["Resilient Dual-Provider LLM Client (app/llm.py)"]
            Verifier["Adversarial Verification Gate"]
            MergeDedup["Merge, Deduplication & Severity Sorter"]
        end
        
        Rules["Offline Rule Definitions (rules/local-rules.yml)"]
        Samples["Seed Samples Repository (app/samples.py)"]
        Contracts["Pydantic Data Contracts (app/models.py)"]
    end

    subgraph External["External Inference Services ($0 Free Tiers)"]
        Groq["Groq Cloud API (LPU Inference Engine)"]
        Gemini["Google Gemini Developer API (Flash Model)"]
    end

    UI -->|POST /api/review| Router
    UI -->|GET /api/samples| Router
    Router --> Orchestrator
    
    Orchestrator --> DiffEngine
    DiffEngine --> InjectionScanner
    DiffEngine --> SASTRunner
    SASTRunner -.-> Rules
    
    InjectionScanner --> Orchestrator
    SASTRunner --> Orchestrator
    
    Orchestrator --> LLMClient
    LLMClient -->|Primary: OpenAI Protocol| Groq
    LLMClient -.->|Fallback on 429/Err| Gemini
    
    LLMClient --> Verifier
    Verifier --> MergeDedup
    MergeDedup --> Router
    Router -->|ReviewResult JSON| UI
```

---

## 2. Pipeline Execution Flow

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / User
    participant Web as Frontend UI
    participant API as FastAPI (main.py)
    participant Pipe as Reviewer Pipeline (reviewer.py)
    participant Semgrep as Semgrep CLI (sast.py)
    participant Inj as Injection Scanner (injection.py)
    participant LLM as LLM Orchestrator (llm.py)

    Dev->>Web: Paste Code / Load Sample & Click "Review"
    Web->>API: POST /api/review {code, language, is_diff}
    API->>Pipe: run_review(code, language, is_diff)
    
    rect rgb(240, 245, 255)
        Note over Pipe: Stage 1: Diff Normalization
        Pipe->>Pipe: Reconstruct full code if diff detected
    end

    par Parallel / Sub-second Pre-Scans
        Pipe->>Inj: scan_prompt_injection(code)
        Inj-->>Pipe: Return injection findings
    and
        Pipe->>Semgrep: execute_semgrep(code, language)
        Semgrep-->>Pipe: Return raw SAST findings (CWE-tagged)
    end

    rect rgb(255, 250, 240)
        Note over Pipe,LLM: Stage 2: Contextual LLM Review
        Pipe->>LLM: review_code(code, sast_candidates, language)
        LLM->>LLM: Call Groq (Failover to Gemini if unavailable)
        LLM-->>Pipe: Candidate LLM findings
    end

    rect rgb(240, 255, 240)
        Note over Pipe,LLM: Stage 3: Adversarial Verification
        Pipe->>LLM: verify_findings(code, candidate_findings)
        LLM-->>Pipe: {index, keep: bool, reason}
        Pipe->>Pipe: Filter false positives & compute dropped count
    end

    Pipe->>Pipe: Merge (Semgrep + Injection + Verified LLM) & Dedupe
    Pipe-->>API: ReviewResult object
    API-->>Web: JSON Response
    Web->>Dev: Render summary bar & finding cards
```

---

## 3. Data Flow & Contract Architecture

### 3.1 Review Request Schema
```python
class ReviewRequest(BaseModel):
    code: str
    language: str = "Python"
    is_diff: bool = False
```

### 3.2 Finding Item Schema
```python
class Finding(BaseModel):
    category: Literal["bug", "security", "style"]
    severity: Literal["high", "medium", "low"]
    confidence: float  # 0.0 to 1.0
    line: Optional[int] = None
    title: str
    explanation: str
    suggested_fix: str
    cwe: Optional[str] = None
    source: Literal["semgrep", "llm", "injection-scan"]
```

### 3.3 Final Output Schema
```python
class ReviewCounts(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    false_positives_filtered: int = 0

class ReviewResult(BaseModel):
    summary: str
    counts: ReviewCounts
    provider_used: Literal["groq", "gemini", "sast-only"]
    findings: List[Finding]
```

---

## 4. Key Architectural Safeguards
1. **Zero External Vector DB Overhead**: Full pasted files fit comfortably in 128k/1M context windows, eliminating embedding drift, vector sync, and memory bloat on 8GB machines.
2. **Ephemeral File Isolation**: Semgrep temp files are generated with randomized unique names and cleaned up in a `finally` block to prevent disk pollution.
3. **Resilient JSON Parser**: Handles markdown fences (` ```json `), regex boundary extraction, and a single self-repair round to eliminate serialization failures.
4. **Idempotent Merge & Deduplication**: Merges Semgrep, injection, and LLM findings by normalizing `(line, title)` signatures, sorting by severity (`high > medium > low`).
