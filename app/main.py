import logging
from pathlib import Path
from fastapi import FastAPI, Response, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.models import ReviewRequest, ReviewResult, SamplesResponse
from app.samples import get_samples
from app.reviewer import CodeReviewOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sentinel.app")

app = FastAPI(
    title="SentinelReview",
    description="Automated AI-Powered Code Reviewer ($0 Free Stack Edition)",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_INDEX = BASE_DIR / "static" / "index.html"

orchestrator = CodeReviewOrchestrator()

# Security Headers & CSP Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response: Response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    if STATIC_INDEX.exists():
        return HTMLResponse(content=STATIC_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>SentinelReview Dashboard</h1><p>UI loading error</p>")

@app.get("/api/samples", response_model=SamplesResponse)
async def list_samples():
    """Returns the 3 pre-seeded demo samples."""
    return SamplesResponse(samples=get_samples())

@app.post("/api/review", response_model=ReviewResult)
async def review_code(req: ReviewRequest):
    """
    Executes the multi-stage code review pipeline:
    Reconstructs diffs, runs local Semgrep SAST, scans for prompt-injection payloads,
    queries LLM with fallback, filters false-positives via adversarial verification,
    and returns deduplicated, severity-ranked findings.
    """
    code_text = req.code.strip()
    if not code_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source code or diff content cannot be empty."
        )

    if len(code_text.encode("utf-8")) > 500_000:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Payload exceeds maximum limit of 500 KB."
        )

    try:
        result = orchestrator.run_review(
            raw_code=code_text,
            language=req.language,
            is_diff=req.is_diff
        )
        return result
    except Exception as exc:
        logger.exception("Review processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review engine error: {str(exc)}"
        )
