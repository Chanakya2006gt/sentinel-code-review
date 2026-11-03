import re
from typing import List, Dict, Any, Tuple
from app.models import Finding, ReviewCounts, ReviewResult
from app.sast import run_semgrep_scan
from app.injection import scan_prompt_injection
from app.llm import LLMReviewEngine

def reconstruct_diff(text: str) -> str:
    """
    Reconstructs the new post-change file from a unified diff.
    Retains context and '+' lines, discarding '-' lines and diff metadata headers.
    """
    lines = text.splitlines()
    reconstructed: List[str] = []
    
    for line in lines:
        if (
            line.startswith("diff --git")
            or line.startswith("index ")
            or line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("@@")
            or line.startswith("\\ No newline at end of file")
        ):
            continue
        elif line.startswith("+"):
            reconstructed.append(line[1:])
        elif line.startswith("-"):
            continue
        elif line.startswith(" "):
            reconstructed.append(line[1:])
        else:
            reconstructed.append(line)

    result = "\n".join(reconstructed).strip()
    return result if result else text

def is_unified_diff(text: str) -> bool:
    """Determines whether the text represents a unified git diff."""
    if "diff --git" in text or "@@" in text:
        return True
    has_plus = bool(re.search(r"^\+[^+]", text, flags=re.MULTILINE))
    has_minus = bool(re.search(r"^-[^-]", text, flags=re.MULTILINE))
    return has_plus and has_minus

class CodeReviewOrchestrator:
    def __init__(self):
        self.llm_engine = LLMReviewEngine()

    def run_review(self, raw_code: str, language: str = "Python", is_diff: bool = False) -> ReviewResult:
        # Step 1: Diff reconstruction
        if is_diff or is_unified_diff(raw_code):
            reviewed_code = reconstruct_diff(raw_code)
        else:
            reviewed_code = raw_code

        # Step 2: SAST scan via Semgrep
        sast_findings = run_semgrep_scan(reviewed_code, language)

        # Step 3: Prompt injection pre-scan
        injection_findings = scan_prompt_injection(reviewed_code)

        # Step 4: LLM Review pass
        llm_findings, provider_used = self.llm_engine.execute_review(
            code=reviewed_code,
            sast_candidates=sast_findings,
            language=language,
            is_diff=is_diff
        )

        # Step 5: Adversarial verification pass
        # Verify LLM-proposed candidates to drop hallucinated findings
        false_positives_filtered = 0
        verified_llm_findings: List[Dict[str, Any]] = []

        if llm_findings and provider_used != "sast-only":
            verify_decisions = self.llm_engine.execute_verify(
                code=reviewed_code,
                findings=llm_findings,
                provider=provider_used
            )
            for idx, finding in enumerate(llm_findings):
                keep, reason = verify_decisions.get(idx, (True, "default"))
                if keep:
                    verified_llm_findings.append(finding)
                else:
                    false_positives_filtered += 1
        else:
            verified_llm_findings = llm_findings

        # Step 6: Merge, Deduplication, and Sorting
        all_raw = injection_findings + sast_findings + verified_llm_findings

        # Deduplication by (line, title_normalized)
        dedup_map: Dict[Tuple[Any, str], Dict[str, Any]] = {}
        for f in all_raw:
            key = (f.get("line"), f.get("title", "").strip().lower())
            if key not in dedup_map:
                dedup_map[key] = f
            else:
                # If duplicate, prefer higher confidence or security source
                existing = dedup_map[key]
                if f.get("source") in ("injection-scan", "semgrep") or f.get("confidence", 0) > existing.get("confidence", 0):
                    dedup_map[key] = f

        final_findings_data = list(dedup_map.values())

        # Severity sort order: high > medium > low
        sev_weights = {"high": 3, "medium": 2, "low": 1}
        final_findings_data.sort(
            key=lambda x: (sev_weights.get(x.get("severity", "low"), 0), x.get("confidence", 0.0)),
            reverse=True
        )

        # Build typed findings
        typed_findings = [Finding(**f) for f in final_findings_data]

        high_count = sum(1 for f in typed_findings if f.severity == "high")
        med_count = sum(1 for f in typed_findings if f.severity == "medium")
        low_count = sum(1 for f in typed_findings if f.severity == "low")

        counts = ReviewCounts(
            high=high_count,
            medium=med_count,
            low=low_count,
            false_positives_filtered=false_positives_filtered
        )

        # Generate PR-style concise summary
        total_issues = len(typed_findings)
        if total_issues == 0:
            summary = "Automated review passed clean with zero critical findings detected."
        else:
            summary = (
                f"Automated review completed with {total_issues} findings "
                f"({high_count} high, {med_count} medium, {low_count} low). "
            )
            if high_count > 0:
                summary += f"Identified {high_count} high-priority risk(s) requiring immediate resolution. "
            if false_positives_filtered > 0:
                summary += f"The adversarial verification filter suppressed {false_positives_filtered} false positive(s)."
            else:
                summary += f"Analyzed using {provider_used.upper()} engine."

        return ReviewResult(
            summary=summary,
            counts=counts,
            provider_used=provider_used,  # type: ignore
            findings=typed_findings
        )
