"""
triage.py -- runtime-native complexity-stakes classifier for the /council skill.

Scores a target 0-100 on five axes and decides whether council deliberation
should proceed. Fail-closed: any unrecoverable error yields verdict=REFUSE.
"""

from __future__ import annotations

import functools
import json
import os
import time
from pathlib import Path
from typing import Any

from . import vk as vk_mod
from .runtime import support_provider_key

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Support steps use the host runtime's native model:
# Codex -> GPT-5.5; Claude Code -> Claude runtime model.
_MODEL = support_provider_key()
_MAX_TOKENS = 400
_TEMPERATURE = 0.0
_AXES = ("reversibility", "blast_radius", "cost_of_error", "normative_vs_technical", "evidence_availability")
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "triage-classifier.md"

# Retry delays (seconds) for transient errors: attempt 1 fails -> wait 1s,
# attempt 2 fails -> wait 2s, then final attempt 3. Total: 3 attempts.
_BACKOFF_DELAYS = (1, 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def triage(target_text: str, threshold: int = 40, force: bool = False, task_id: str = "council-unknown") -> dict:
    """
    Score target_text 0-100 on five axes; return verdict dict.

    Args:
        target_text: raw content of target (plan, proposal, idea text).
        threshold:   triage score threshold; score >= threshold -> PROCEED.
        force:       if True, bypass threshold gate (--force flag).
        task_id:     council task identifier for VK markers.

    Returns:
        {
          "score": int 0-100,
          "axes": {"reversibility": int, ...},
          "verdict": "PROCEED" | "REFUSE" | "PROCEED_FORCED",
          "reason": str,
          "support_call_count": int,
          "support_tokens": {"in": int, "out": int},
          "haiku_call_count": int,  # legacy alias; counts successful GPT-5.5 responses
          "haiku_tokens": {"in": int, "out": int},  # legacy alias
        }

    Raises:
        ValueError: on empty target_text or threshold outside [0, 100].
    """
    if not target_text or not target_text.strip():
        raise ValueError("target_text must not be empty")
    if not (0 <= threshold <= 100):
        raise ValueError(f"threshold must be in [0, 100], got {threshold!r}")

    vk_mod.emit("triage", "entered", task_id)

    system_prompt, user_prompt = build_prompt(target_text)
    support_call_count = 0
    tokens_in = 0
    tokens_out = 0

    raw_result: dict[str, Any] | None = None
    last_error: str = ""
    is_transient_error = False

    for attempt in range(3):
        try:
            response = _call_support_model(system_prompt, user_prompt)
            support_call_count += 1
            tokens_in += response["tokens_in"]
            tokens_out += response["tokens_out"]
            raw_text = response["content"]

            # Strip markdown code fences if present.
            try:
                from ._advisor_common import _strip_markdown_fences
                raw_text_stripped = _strip_markdown_fences(raw_text)
            except ImportError:
                raw_text_stripped = raw_text.strip()
                if raw_text_stripped.startswith("```"):
                    lines = raw_text_stripped.splitlines()
                    lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    raw_text_stripped = "\n".join(lines).strip()

            try:
                parsed = json.loads(raw_text_stripped)
            except json.JSONDecodeError as exc:
                last_error = f"schema: JSON parse error: {exc}"
                # Schema errors are permanent -- stop retrying
                vk_mod.emit("triage", "failed", task_id, error="schema_error")
                return _refuse_result(
                    reason=f"TRIAGE_UNAVAILABLE: {last_error}",
                    support_call_count=support_call_count,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    force=force,
                )

            axes, validate_err = _validate_axes(parsed)
            if validate_err:
                last_error = f"schema: {validate_err}"
                vk_mod.emit("triage", "failed", task_id, error="schema_error")
                return _refuse_result(
                    reason=f"TRIAGE_UNAVAILABLE: {last_error}",
                    support_call_count=support_call_count,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    force=force,
                )

            score = sum(axes.values())
            reason = str(parsed.get("reason", ""))

            if force:
                verdict = "PROCEED_FORCED"
                vk_mod.emit("triage", "completed", task_id, score=score, verdict=verdict)
            elif score >= threshold:
                verdict = "PROCEED"
                vk_mod.emit("triage", "completed", task_id, score=score, verdict=verdict)
            else:
                verdict = "REFUSE"
                reason = f"Score {score} is below threshold {threshold}. {reason}".strip()
                vk_mod.emit("triage", "completed", task_id, score=score, verdict=verdict)

            return {
                "score": score,
                "axes": axes,
                "verdict": verdict,
                "reason": reason,
                "support_call_count": support_call_count,
                "support_tokens": {"in": tokens_in, "out": tokens_out},
                "haiku_call_count": support_call_count,
                "haiku_tokens": {"in": tokens_in, "out": tokens_out},
            }

        except _TransientError as exc:
            last_error = str(exc)
            is_transient_error = True
            if attempt < len(_BACKOFF_DELAYS):
                time.sleep(_BACKOFF_DELAYS[attempt])
            # else: last attempt exhausted, fall through to REFUSE

        except _PermanentError as exc:
            last_error = str(exc)
            is_transient_error = False
            break

    # All attempts exhausted or permanent error
    vk_mod.emit("triage", "failed", task_id, error="api_error")
    return _refuse_result(
        reason=f"TRIAGE_UNAVAILABLE: {last_error}",
        support_call_count=support_call_count,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        force=force,
    )


def build_prompt(target_text: str) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for the runtime support-model triage call.
    system_prompt is loaded from prompts/triage-classifier.md.
    user_prompt wraps the target in an XML <target> tag.
    """
    system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    user_prompt = f"<target>\n{target_text}\n</target>"
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _TransientError(Exception):
    """Raised for timeout, 5xx, or rate-limit errors that warrant a retry."""


class _PermanentError(Exception):
    """Raised for 4xx and other non-retriable errors."""


@functools.lru_cache(maxsize=1)
def _get_client():
    """
    v1.0.8+: triage routes through the runtime support model. This function is a
    thin pre-flight check kept for backwards compatibility with tests that
    monkeypatch _get_client. Returns None (no client object).

    Verifies codex CLI/auth are available; raises _PermanentError if not.
    """
    import shutil
    from ._oauth import codex_auth_present
    if not shutil.which("codex"):
        raise _PermanentError(
            "codex CLI not installed; Codex support routing requires Codex OAuth"
        )
    if not codex_auth_present():
        raise _PermanentError("codex auth.json missing or empty")
    return None


def _call_support_model(system_prompt: str, user_prompt: str) -> dict:
    """
    Calls the runtime support model through the legacy provider boundary.

    The indirection keeps older tests and integrations that monkeypatch
    _call_haiku working while the runtime path is explicitly support-model
    oriented.
    """
    return _call_haiku(system_prompt, user_prompt)


def _call_haiku(system_prompt: str, user_prompt: str) -> dict:
    """
    Calls the triage model via lib._providers.call_provider.
    Returns {"content": str, "tokens_in": int, "tokens_out": int}.
    Raises _TransientError or _PermanentError as appropriate.

    v1.0.8+: routes through the runtime support provider.
    """
    try:
        from ._providers import (
            call_provider,
            TransientProviderError,
            PermanentProviderError,
        )
    except ImportError as exc:
        raise _PermanentError(f"_providers import failure: {exc}") from exc

    try:
        result = call_provider(
            _MODEL,
            system=system_prompt,
            user=user_prompt,
            max_tokens=_MAX_TOKENS,
            temperature=_TEMPERATURE,
            timeout_s=60.0,
        )
        return {
            "content": result.get("text", ""),
            "tokens_in": int(result.get("tokens", {}).get("in", 0)),
            "tokens_out": int(result.get("tokens", {}).get("out", 0)),
        }
    except TransientProviderError as exc:
        raise _TransientError(str(exc)) from exc
    except PermanentProviderError as exc:
        raise _PermanentError(str(exc)) from exc


def _validate_axes(parsed: dict) -> tuple[dict, str]:
    """
    Validates that all five axes are present and integers in [0, 20].
    Returns (axes_dict, error_str). error_str is empty string on success.
    """
    axes = {}
    for axis in _AXES:
        val = parsed.get(axis)
        if val is None:
            return {}, f"missing axis {axis!r}"
        if not isinstance(val, int):
            return {}, f"axis {axis!r} is not an int: {val!r}"
        if not (0 <= val <= 20):
            return {}, f"axis {axis!r} value {val} out of range [0, 20]"
        axes[axis] = val
    return axes, ""


def _refuse_result(
    reason: str,
    support_call_count: int,
    tokens_in: int,
    tokens_out: int,
    force: bool,
) -> dict:
    """Builds a REFUSE or PROCEED_FORCED result dict for error/unavailability cases."""
    if force:
        verdict = "PROCEED_FORCED"
        reason = "TRIAGE_BYPASSED via --force"
    else:
        verdict = "REFUSE"

    return {
        "score": 0,
        "axes": {ax: 0 for ax in _AXES},
        "verdict": verdict,
        "reason": reason,
        "support_call_count": support_call_count,
        "support_tokens": {"in": tokens_in, "out": tokens_out},
        "haiku_call_count": support_call_count,
        "haiku_tokens": {"in": tokens_in, "out": tokens_out},
    }
