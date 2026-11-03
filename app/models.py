from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class ReviewRequest(BaseModel):
    code: str
    language: str = "Python"
    is_diff: bool = False

class Finding(BaseModel):
    category: Literal["bug", "security", "style"]
    severity: Literal["high", "medium", "low"]
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    line: Optional[int] = None
    title: str
    explanation: str
    suggested_fix: str
    cwe: Optional[str] = None
    source: Literal["semgrep", "llm", "injection-scan"]

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

class SampleItem(BaseModel):
    id: str
    label: str
    language: str
    code: str

class SamplesResponse(BaseModel):
    samples: List[SampleItem]
