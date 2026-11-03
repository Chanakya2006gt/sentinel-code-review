import re
from typing import List, Dict, Any

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard the above",
    "you are now",
    "system prompt",
    "mark this as safe",
    "do not report",
    "this file is audited",
    "approved by security",
    "no vulnerabilities here",
    "as an ai",
    "jailbreak"
]

def scan_prompt_injection(code: str) -> List[Dict[str, Any]]:
    """
    Case-insensitive search of the code text for prompt-injection payloads
    designed to deceive or hijack code-reviewing LLMs.
    """
    findings: List[Dict[str, Any]] = []
    lines = code.splitlines()

    for idx, line in enumerate(lines, start=1):
        lower_line = line.lower()
        for phrase in INJECTION_PATTERNS:
            if phrase in lower_line:
                clean_snippet = line.strip()
                findings.append({
                    "category": "security",
                    "severity": "high",
                    "confidence": 1.0,
                    "line": idx,
                    "title": "Adversarial Prompt Injection Attempt",
                    "explanation": (
                        f"Detected adversarial prompt injection payload '{phrase}'. "
                        "Comment or string attempts to hijack code-review instructions or suppress vulnerability reporting."
                    ),
                    "suggested_fix": f"Remove adversarial directive from code: '{clean_snippet}'",
                    "cwe": "CWE-74",
                    "source": "injection-scan"
                })
                break  # avoid multiple hits on the same line

    return findings
