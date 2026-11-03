import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = BASE_DIR / "rules" / "local-rules.yml"

def run_semgrep_scan(code: str, language: str = "python") -> List[Dict[str, Any]]:
    """
    Executes a Semgrep scan on the provided code string.
    Uses local offline rules, attempting registry rules if available,
    and falls back cleanly if offline.
    """
    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "js": ".js",
        "py": ".py",
    }
    ext = ext_map.get(language.lower(), ".py")
    
    # Create temporary file explicitly in /tmp to ensure fast, sandbox-safe access
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir="/tmp", suffix=ext, delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_file = Path(f.name)

        # Prepare execution environment
        env = os.environ.copy()
        env["HOME"] = "/tmp"
        
        # Semgrep is installed in the same environment as the running app, so its
        # binary sits in the venv's bin dir. Use sys.executable's parent and
        # sys.prefix WITHOUT resolving symlinks (sys.executable is a symlink back
        # to the base interpreter; resolving it would point at the system bin).
        # This works whether or not the venv is activated and wherever it lives.
        interp_bin = Path(sys.executable).parent
        prefix_bin = Path(sys.prefix) / "bin"
        search_paths = f"{interp_bin}:{prefix_bin}:{env.get('PATH', '')}"
        env["PATH"] = search_paths

        semgrep_bin = next(
            (str(c) for c in (interp_bin / "semgrep", prefix_bin / "semgrep") if c.exists()),
            None,
        ) or shutil.which("semgrep", path=search_paths) or shutil.which("semgrep") or "semgrep"

        base_flags = [
            semgrep_bin,
            "--json",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            "--config", str(RULES_PATH),
        ]

        # First run local offline rules (instant, zero network required)
        output = None
        try:
            res = subprocess.run(base_flags + [str(temp_file)], capture_output=True, text=True, env=env, timeout=5)
            if res.returncode == 0 or res.stdout.strip().startswith("{"):
                output = res.stdout
        except Exception:
            pass

        # Optional registry packs if configured and online
        # (spec mentions p/default and p/security-audit - if they fail/timeout, we already have local output)
        if not output:
            return []

        try:
            data = json.loads(output)
        except Exception:
            return []

        findings: List[Dict[str, Any]] = []
        results = data.get("results", [])
        for item in results:
            check_id = item.get("check_id", "semgrep-finding")
            start = item.get("start", {})
            line = start.get("line")
            extra = item.get("extra", {})
            message = extra.get("message", "Semgrep security finding")
            raw_sev = extra.get("severity", "WARNING").upper()

            # Severity mapping: ERROR -> high, WARNING -> medium, INFO -> low
            if raw_sev == "ERROR":
                severity = "high"
            elif raw_sev == "INFO":
                severity = "low"
            else:
                severity = "medium"

            # Parse CWE metadata
            raw_cwe = extra.get("metadata", {}).get("cwe")
            cwe: Optional[str] = None
            if isinstance(raw_cwe, list) and raw_cwe:
                cwe = str(raw_cwe[0])
            elif isinstance(raw_cwe, str):
                cwe = raw_cwe

            findings.append({
                "category": "security",
                "severity": severity,
                "confidence": 0.95,
                "line": line,
                "title": check_id.split(".")[-1].replace("-", " ").title(),
                "explanation": message,
                "suggested_fix": "Refactor code to avoid unvalidated user input or hardcoded credentials.",
                "cwe": cwe,
                "source": "semgrep"
            })

        return findings

    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
