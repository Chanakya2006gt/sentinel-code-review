import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI

from app.prompts import REVIEW_SYSTEM, VERIFY_SYSTEM, REPAIR_SYSTEM

load_dotenv()
logger = logging.getLogger("sentinel.llm")

# Model configuration per spec
MODELS_CONFIG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "review_model": "openai/gpt-oss-120b",
        "verify_model": "openai/gpt-oss-20b",
        "default_key_env": "GROQ_API_KEY",
        "fallback_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen-2.5-coder-32b"]
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "review_model": "gemini-2.5-flash",
        "verify_model": "gemini-2.5-flash",
        "default_key_env": "GEMINI_API_KEY",
        "fallback_models": ["gemini-2.0-flash", "gemini-1.5-flash"]
    }
}

# Cache for auto-corrected model identifiers
_CORRECTED_MODELS: Dict[str, str] = {}

def get_api_keys() -> Tuple[Optional[str], Optional[str]]:
    """Returns (groq_key, gemini_key)."""
    groq = os.getenv("GROQ_API_KEY", "").strip() or None
    gemini = os.getenv("GEMINI_API_KEY", "").strip() or None
    return groq, gemini

def extract_json_object(text: str) -> Optional[Any]:
    """
    Robustly extracts the first balanced JSON object or array from LLM text.
    Handles markdown fences and extraneous leading/trailing prose.
    """
    if not text:
        return None
    cleaned = text.strip()
    
    # Strip markdown code blocks
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Find first balanced { ... }
    first_brace = cleaned.find("{")
    if first_brace != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(first_brace, len(cleaned)):
            char = cleaned[i]
            if char == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[first_brace:i+1])
                        except Exception:
                            break
            if char == "\\" and not escape:
                escape = True
            else:
                escape = False

    return None

def self_correct_model(client: OpenAI, provider: str, original_model: str) -> str:
    """
    If a model returns 404/not found, queries /models and picks an active available model.
    """
    cache_key = f"{provider}_{original_model}"
    if cache_key in _CORRECTED_MODELS:
        return _CORRECTED_MODELS[cache_key]

    logger.warning("Attempting model self-correction for provider '%s' and model '%s'...", provider, original_model)
    try:
        models_list = client.models.list()
        avail_ids = [m.id for m in models_list.data]
        logger.info("Provider '%s' available models: %s", provider, avail_ids)

        # Check fallback preference list
        for candidate in MODELS_CONFIG[provider]["fallback_models"]:
            if candidate in avail_ids:
                logger.info("Self-corrected model for '%s' to '%s'", provider, candidate)
                _CORRECTED_MODELS[cache_key] = candidate
                return candidate

        # Fuzzy match for flash or coder or chat
        for m_id in avail_ids:
            lower = m_id.lower()
            if "flash" in lower or "coder" in lower or "versatile" in lower or "8b" in lower:
                logger.info("Self-corrected model (fuzzy) for '%s' to '%s'", provider, m_id)
                _CORRECTED_MODELS[cache_key] = m_id
                return m_id

        if avail_ids:
            chosen = avail_ids[0]
            _CORRECTED_MODELS[cache_key] = chosen
            return chosen
    except Exception as e:
        logger.error("Failed to query models endpoint for provider '%s': %s", provider, e)

    return original_model

class LLMReviewEngine:
    def __init__(self):
        self.groq_key, self.gemini_key = get_api_keys()

    def _get_client(self, provider: str) -> Optional[OpenAI]:
        key = self.groq_key if provider == "groq" else self.gemini_key
        if not key:
            return None
        cfg = MODELS_CONFIG[provider]
        return OpenAI(base_url=cfg["base_url"], api_key=key)

    def _call_with_retry_and_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "review"
    ) -> Tuple[Optional[str], str]:
        """
        Executes LLM call with Groq (retry 1x on failure) -> Gemini fallback -> sast-only.
        Returns (raw_content_string, provider_used).
        """
        providers_to_try = []
        if self.groq_key:
            providers_to_try.append("groq")
        if self.gemini_key:
            providers_to_try.append("gemini")

        if not providers_to_try:
            return None, "sast-only"

        for provider in providers_to_try:
            client = self._get_client(provider)
            if not client:
                continue

            cfg = MODELS_CONFIG[provider]
            model_name = cfg["review_model"] if task == "review" else cfg["verify_model"]
            model_to_use = _CORRECTED_MODELS.get(f"{provider}_{model_name}", model_name)

            # Try up to 2 attempts per provider
            for attempt in range(2):
                try:
                    kwargs: Dict[str, Any] = {
                        "model": model_to_use,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.1,
                    }
                    # Groq and Gemini support json_object mode
                    try:
                        kwargs["response_format"] = {"type": "json_object"}
                    except Exception:
                        pass

                    resp = client.chat.completions.create(**kwargs)
                    content = resp.choices[0].message.content
                    if content and content.strip():
                        return content, provider

                except Exception as exc:
                    err_msg = str(exc)
                    logger.warning("Error calling provider '%s' (attempt %d): %s", provider, attempt + 1, err_msg)
                    if "404" in err_msg or "not found" in err_msg.lower() or "does not exist" in err_msg.lower():
                        model_to_use = self_correct_model(client, provider, model_name)
                    if attempt == 1:
                        # break to next provider
                        break

        return None, "sast-only"

    def repair_json(self, invalid_json: str, provider: str) -> Optional[Any]:
        """Runs a single repair call on malformed JSON output."""
        client = self._get_client(provider)
        if not client:
            return None
        cfg = MODELS_CONFIG[provider]
        model = _CORRECTED_MODELS.get(f"{provider}_{cfg['review_model']}", cfg["review_model"])
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": REPAIR_SYSTEM},
                    {"role": "user", "content": f"Fix and return valid JSON:\n{invalid_json}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content or ""
            return extract_json_object(content)
        except Exception as e:
            logger.warning("JSON repair failed: %s", e)
            return None

    def execute_review(
        self,
        code: str,
        sast_candidates: List[Dict[str, Any]],
        language: str = "Python",
        is_diff: bool = False
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Executes the initial LLM review pass.
        Returns (candidate_findings, provider_used).
        """
        user_message = (
            f"Language: {language}\n"
            f"Is Diff: {is_diff}\n\n"
            f"Static Analyzer Candidates (JSON):\n"
            f"{json.dumps(sast_candidates, indent=2)}\n\n"
            f"<SOURCE_CODE_DATA>\n{code}\n</SOURCE_CODE_DATA>\n"
        )

        content, provider_used = self._call_with_retry_and_fallback(
            system_prompt=REVIEW_SYSTEM,
            user_prompt=user_message,
            task="review"
        )

        if not content:
            return [], provider_used

        data = extract_json_object(content)
        if not data:
            # One repair attempt
            data = self.repair_json(content, provider_used)

        if not data or not isinstance(data, dict):
            return [], provider_used

        raw_findings = data.get("findings", [])
        if not isinstance(raw_findings, list):
            return [], provider_used

        formatted_findings: List[Dict[str, Any]] = []
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            cat = str(item.get("category", "bug")).lower()
            if cat not in ("bug", "security", "style"):
                cat = "bug"
            
            sev = str(item.get("severity", "medium")).lower()
            if sev not in ("high", "medium", "low"):
                sev = "medium"

            try:
                conf = float(item.get("confidence", 0.8))
                conf = max(0.0, min(1.0, conf))
            except (ValueError, TypeError):
                conf = 0.8

            line_val = item.get("line")
            try:
                line_val = int(line_val) if line_val is not None else None
            except (ValueError, TypeError):
                line_val = None

            formatted_findings.append({
                "category": cat,
                "severity": sev,
                "confidence": conf,
                "line": line_val,
                "title": str(item.get("title", "Code Issue")),
                "explanation": str(item.get("explanation", "")),
                "suggested_fix": str(item.get("suggested_fix", "")),
                "cwe": item.get("cwe") if item.get("cwe") else None,
                "source": "llm"
            })

        return formatted_findings, provider_used

    def execute_verify(
        self,
        code: str,
        findings: List[Dict[str, Any]],
        provider: str
    ) -> Dict[int, Tuple[bool, str]]:
        """
        Runs adversarial verification pass over candidate findings.
        Returns dict: index -> (keep: bool, reason: str).
        """
        if not findings or provider == "sast-only":
            # If no provider or no findings, keep all by default
            return {idx: (True, "default keep") for idx in range(len(findings))}

        numbered_findings = [
            {
                "index": idx,
                "category": f.get("category"),
                "severity": f.get("severity"),
                "line": f.get("line"),
                "title": f.get("title"),
                "explanation": f.get("explanation"),
                "cwe": f.get("cwe")
            }
            for idx, f in enumerate(findings)
        ]

        user_message = (
            f"Candidate Findings List:\n{json.dumps(numbered_findings, indent=2)}\n\n"
            f"<SOURCE_CODE_DATA>\n{code}\n</SOURCE_CODE_DATA>\n"
        )

        content, _ = self._call_with_retry_and_fallback(
            system_prompt=VERIFY_SYSTEM,
            user_prompt=user_message,
            task="verify"
        )

        if not content:
            return {idx: (True, "fallback keep") for idx in range(len(findings))}

        data = extract_json_object(content)
        if not data or not isinstance(data, dict):
            return {idx: (True, "fallback keep") for idx in range(len(findings))}

        results_list = data.get("results", [])
        decisions: Dict[int, Tuple[bool, str]] = {}
        for r in results_list:
            if isinstance(r, dict) and "index" in r and "keep" in r:
                decisions[int(r["index"])] = (bool(r["keep"]), str(r.get("reason", "")))

        # Default any missing to keep
        for idx in range(len(findings)):
            if idx not in decisions:
                decisions[idx] = (True, "unverified keep")

        return decisions
