"""
_advisor_common.py -- Shared orchestration for /council advisor lanes (Tasks 4-6).

Provides run_advisor() used by all three advisor wrappers (advisor_gemini,
advisor_opus, advisor_gpt). Handles retry logic, schema validation, VK
emission, timeout mapping, and cost calculation.

Exposes:
    run_advisor(...)  -- main entry point, returns structured advisor dict.
    _parse_advisor_response(text)  -- JSON parse + key validation.
    _build_system_prompt()  -- loads prompts/advisor-system.md.
    _build_user_prompt(brief_xml)  -- wraps brief XML in council_brief tags if needed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from . import _providers as providers
from ._providers import (
    PROVIDER_REGISTRY,
    TransientProviderError,
    PermanentProviderError,
)
from . import vk


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_KEYS: frozenset[str] = frozenset({
    "verdict",
    "confidence",
    "nplf",
    "top_strengths",
    "top_risks",
    "critical_blockers",
    "reasoning_chain",
})

_VALID_VERDICTS: frozenset[str] = frozenset({"PASS", "REVISE", "BLOCK"})

_NPLF_KEYS: frozenset[str] = frozenset({"n", "p", "l", "f"})

_DEPTH_TIMEOUTS: dict[str, float] = {
    "quick": 75.0,
    "standard": 200.0,
    "deep": 400.0,
}

# Exponential backoff delays: 4 attempts produce 3 inter-attempt sleeps (1->2->4s).
# The "1->2->4->8s" in the HARD rule implies 4 sleeps which needs 5 attempts;
# we keep _MAX_ATTEMPTS=4 and drop the 8.0 entry (Option A, cheapest fix).
_BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)

_MAX_ATTEMPTS: int = 4


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_advisor(
    *,
    provider_key: str,
    advisor_label: str,
    brief_xml: str,
    task_id: str,
    depth: str = "standard",
    max_reasoning_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """
    Single-advisor orchestration.

    Args:
        provider_key:          Key in PROVIDER_REGISTRY (e.g. "gemini-3.1-pro").
        advisor_label:         Lane label "A"/"B"/"C" for VK and logging.
        brief_xml:             Canonical <council_brief> XML from normalize.py.
        task_id:               Council task identifier for VK emission.
        depth:                 "quick" | "standard" | "deep". Drives timeout.
        max_reasoning_kwargs:  Provider-specific kwargs forwarded to call_provider().

    Returns:
        {
          "advisor": provider_key,
          "label": advisor_label,
          "verdict": "PASS" | "REVISE" | "BLOCK" | "ABSTAIN",
          "confidence": float 0.0-1.0,
          "nplf": {"n": float, "p": float, "l": float, "f": float},
          "top_strengths": list[str] (3 items),
          "top_risks": list[str] (3 items),
          "critical_blockers": list[str] (0+ items),
          "reasoning_chain": str,
          "tokens": {"in": int, "out": int},
          "cost_usd": float,
          "duration_s": float,
          "status": "OK" | "TIMEOUT" | "ABSTAIN" | "SCHEMA_FAIL",
          "error": str | None,
        }
    """
    step_name = f"dispatch_{advisor_label}"
    timeout_s = _DEPTH_TIMEOUTS.get(depth, _DEPTH_TIMEOUTS["standard"])

    # VK: entered
    vk.emit(step_name, "entered", task_id)

    wall_start = time.monotonic()

    # Build prompts
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(brief_xml)

    # Resolve pricing info
    entry = PROVIDER_REGISTRY.get(provider_key, {})
    price_in: float = entry.get("price_in", 0.0)
    price_out: float = entry.get("price_out", 0.0)

    # --- Retry loop with exponential backoff ---
    # FIX-1: schema_fail_count is SEPARATE from attempt so schema retries do not
    #         consume transient retry budget.
    # FIX-4: total_tokens_* accumulate across ALL calls (including schema-fail
    #         calls that charged tokens before the parse error).
    last_text: str | None = None
    last_error: str | None = None
    attempt: int = 0               # transient-retry counter (0..3, max 4 attempts)
    schema_fail_count: int = 0     # schema-retry counter (0..1, max 2 attempts)
    schema_retry_note: str = ""
    total_tokens_in: int = 0
    total_tokens_out: int = 0

    while attempt < _MAX_ATTEMPTS:
        # Build user content (with schema retry note on second schema attempt)
        effective_user = user_prompt
        if schema_retry_note:
            effective_user = f"{user_prompt}\n\n[INSTRUCTION: previous output was malformed: {schema_retry_note}. Return valid JSON this time.]"

        try:
            response = providers.call_provider(
                provider_key,
                system_prompt,
                effective_user,
                max_tokens=4096,
                temperature=0.2,
                timeout_s=timeout_s,
                **max_reasoning_kwargs,
            )
            last_text = response.get("text", "")

            # FIX-4: accumulate BEFORE any parse that might raise ValueError,
            #         so tokens from failed-parse calls are never silently dropped.
            total_tokens_in += response.get("tokens", {}).get("in", 0)
            total_tokens_out += response.get("tokens", {}).get("out", 0)

            # Attempt schema parse
            try:
                parsed = _parse_advisor_response(last_text)
            except ValueError as ve:
                schema_fail_count += 1
                schema_retry_note = str(ve)[:200]
                if schema_fail_count >= 2:
                    # Second schema fail -> SCHEMA_FAIL
                    cost_usd = total_tokens_in * price_in + total_tokens_out * price_out
                    duration_s = time.monotonic() - wall_start
                    result = _make_result(
                        provider_key, advisor_label,
                        verdict="ABSTAIN",
                        status="SCHEMA_FAIL",
                        error=f"schema_fail: {ve}",
                        tokens={"in": total_tokens_in, "out": total_tokens_out},
                        cost_usd=cost_usd,
                        duration_s=duration_s,
                    )
                    vk.emit(step_name, "failed", task_id, error_class="schema")
                    return result
                # FIX-1: First schema fail — do NOT increment attempt; schema retry
                #         is a separate budget from the transient retry budget.
                continue

            # Success
            cost_usd = total_tokens_in * price_in + total_tokens_out * price_out
            duration_s = time.monotonic() - wall_start
            result = _make_result(
                provider_key, advisor_label,
                verdict=parsed["verdict"],
                confidence=parsed.get("confidence", 0.0),
                nplf=parsed.get("nplf", {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0}),
                top_strengths=parsed.get("top_strengths", []),
                top_risks=parsed.get("top_risks", []),
                critical_blockers=parsed.get("critical_blockers", []),
                direct_answer_md=parsed.get("direct_answer_md", ""),
                reasoning_chain=parsed.get("reasoning_chain", ""),
                status="OK",
                tokens={"in": total_tokens_in, "out": total_tokens_out},
                cost_usd=cost_usd,
                duration_s=duration_s,
            )
            vk.emit(step_name, "completed", task_id,
                    verdict=parsed["verdict"],
                    confidence=str(parsed.get("confidence", 0.0)))
            return result

        except PermanentProviderError as exc:
            duration_s = time.monotonic() - wall_start
            result = _make_result(
                provider_key, advisor_label,
                verdict="ABSTAIN",
                status="ABSTAIN",
                error=str(exc),
                duration_s=duration_s,
            )
            vk.emit(step_name, "failed", task_id, error_class="permanent")
            return result

        except TransientProviderError as exc:
            last_error = str(exc)
            attempt += 1
            if attempt < _MAX_ATTEMPTS:
                sleep_s = _BACKOFF_DELAYS[attempt - 1]
                time.sleep(sleep_s)
            continue

    # Exhausted all transient attempts
    duration_s = time.monotonic() - wall_start
    result = _make_result(
        provider_key, advisor_label,
        verdict="ABSTAIN",
        status="ABSTAIN",
        error=f"transient_exhausted: {last_error}",
        duration_s=duration_s,
    )
    vk.emit(step_name, "failed", task_id, error_class="transient")
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` fences if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    # Remove first line (```json or ```)
    lines = lines[1:]
    # Remove last line if it is a closing fence on its own line
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_advisor_response(text: str) -> dict[str, Any]:
    """
    Parse JSON from model response. Validate required keys and value types.
    Raises ValueError on any failure.
    """
    stripped = _strip_markdown_fences(text)

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON decode error: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required keys: {sorted(missing)}")

    # Validate verdict
    verdict = data.get("verdict")
    if verdict not in _VALID_VERDICTS:
        raise ValueError(f"Invalid verdict {verdict!r}. Must be one of {sorted(_VALID_VERDICTS)}")

    # Validate nplf structure
    nplf = data.get("nplf")
    if not isinstance(nplf, dict):
        raise ValueError(f"nplf must be a dict, got {type(nplf).__name__}")
    missing_nplf = _NPLF_KEYS - set(nplf.keys())
    if missing_nplf:
        raise ValueError(f"nplf missing keys: {sorted(missing_nplf)}")

    # Validate top_strengths and top_risks (exactly 3)
    for field in ("top_strengths", "top_risks"):
        val = data.get(field)
        if not isinstance(val, list):
            raise ValueError(f"{field} must be a list")
        if len(val) != 3:
            raise ValueError(f"{field} must have exactly 3 items, got {len(val)}")

    # Validate critical_blockers is a list
    if not isinstance(data.get("critical_blockers"), list):
        raise ValueError("critical_blockers must be a list")

    # Optional public answer channel. This is deliberately separate from the
    # private reasoning_chain so the reconciler can synthesize substantive
    # reports without exposing hidden chain-of-thought.
    direct_answer = data.get("direct_answer_md")
    if direct_answer is not None and not isinstance(direct_answer, str):
        raise ValueError(
            f"direct_answer_md must be a string when present, got {type(direct_answer).__name__}"
        )

    return data


def _build_system_prompt() -> str:
    """Load prompts/advisor-system.md from disk relative to this file's package root."""
    skill_root = Path(__file__).resolve().parent.parent
    prompt_path = skill_root / "prompts" / "advisor-system.md"
    return prompt_path.read_text(encoding="utf-8")


def _build_user_prompt(brief_xml: str) -> str:
    """Wrap brief XML in <council_brief> tags if not already wrapped."""
    stripped = brief_xml.strip()
    if stripped.startswith("<council_brief>"):
        return stripped
    return f"<council_brief>\n{stripped}\n</council_brief>"


def _make_result(
    provider_key: str,
    advisor_label: str,
    *,
    verdict: str = "ABSTAIN",
    confidence: float = 0.0,
    nplf: dict[str, float] | None = None,
    top_strengths: list[str] | None = None,
    top_risks: list[str] | None = None,
    critical_blockers: list[str] | None = None,
    direct_answer_md: str = "",
    reasoning_chain: str = "",
    status: str = "ABSTAIN",
    error: str | None = None,
    tokens: dict[str, int] | None = None,
    cost_usd: float = 0.0,
    duration_s: float = 0.0,
) -> dict[str, Any]:
    """Build a complete advisor result dict with all required keys."""
    return {
        "advisor": provider_key,
        "label": advisor_label,
        "verdict": verdict,
        "confidence": confidence,
        "nplf": nplf if nplf is not None else {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0},
        "top_strengths": top_strengths if top_strengths is not None else [],
        "top_risks": top_risks if top_risks is not None else [],
        "critical_blockers": critical_blockers if critical_blockers is not None else [],
        "direct_answer_md": direct_answer_md,
        "reasoning_chain": reasoning_chain,
        "tokens": tokens if tokens is not None else {"in": 0, "out": 0},
        "cost_usd": cost_usd,
        "duration_s": duration_s,
        "status": status,
        "error": error,
    }
