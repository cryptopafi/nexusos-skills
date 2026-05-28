"""
normalize.py -- Brief normalizer for the /council skill pipeline.

Converts a raw target (file path or raw text) into a canonical
<council_brief> XML structure using the runtime-native support model.

Per provider: 3-attempt exponential backoff (1->2->4s) on transient errors.
Exhausted attempts -> verdict="FAIL_ALL_PROVIDERS".
"""

from __future__ import annotations

import logging
import pathlib
import time
import xml.etree.ElementTree as ET
from typing import Any

from ._providers import (
    PROVIDER_REGISTRY,
    PermanentProviderError,
    TransientProviderError,
    call_provider,
)
from .runtime import support_provider_key

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

_REQUIRED_CHILDREN: tuple[str, ...] = (
    "goal", "context", "constraints", "prior_art",
    "decision_points", "success_criteria", "stakes",
)
from .vk import emit as vk_emit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROVIDER_CHAIN: tuple[str, ...] = (support_provider_key(),)

_BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)  # seconds between attempts
_MAX_ATTEMPTS: int = 3

_PROMPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "brief-normalizer.md"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(target: str | pathlib.Path, *, task_id: str) -> dict[str, Any]:
    """
    Convert raw target into canonical <council_brief> XML.

    Args:
        target:  File path (reads content) OR raw text string. Auto-detect:
                 if the value starts with "/" or "~" AND resolves to an existing
                 file, the file is read. Otherwise treated as raw text.
        task_id: Required for VK emission.

    Returns:
        {
          "brief_xml":       str | None,
          "provider_used":   str | None,
          "provider_chain":  list[tuple[str, str, str | None]],
          "verdict":         "OK" | "FAIL_ALL_PROVIDERS",
          "reason":          str,
          "tokens":          {"in": int, "out": int},
          "cost_usd":        float,
        }

    Raises:
        ValueError: on empty target or unreadable file path.
    """
    # Resolve target text
    raw_text = _resolve_target(target)

    # Load system prompt
    system_prompt = _load_system_prompt()

    # VK: entered
    vk_emit("normalize", "entered", task_id)

    provider_chain: list[tuple[str, str, str | None]] = []
    total_tokens_in = 0
    total_tokens_out = 0

    for provider in _PROVIDER_CHAIN:
        result = _try_provider(
            provider=provider,
            system=system_prompt,
            user=raw_text,
            provider_chain=provider_chain,
        )
        if result is None:
            # provider exhausted or permanent error, continue to next
            continue

        # Success
        brief_xml = result["text"]
        tokens = result["tokens"]
        total_tokens_in += tokens["in"]
        total_tokens_out += tokens["out"]
        cost = _compute_cost(provider, tokens["in"], tokens["out"])

        vk_emit("normalize", "completed", task_id, provider=provider)
        return {
            "brief_xml": brief_xml,
            "provider_used": provider,
            "provider_chain": provider_chain,
            "verdict": "OK",
            "reason": f"Normalized by {provider}.",
            "tokens": {"in": total_tokens_in, "out": total_tokens_out},
            "cost_usd": cost,
        }

    # All providers exhausted
    last_errors = "; ".join(
        f"{p}:{err}" for p, _status, err in provider_chain if err
    )
    vk_emit("normalize", "failed", task_id)
    return {
        "brief_xml": None,
        "provider_used": None,
        "provider_chain": provider_chain,
        "verdict": "FAIL_ALL_PROVIDERS",
        "reason": f"NORMALIZER_UNAVAILABLE: {last_errors}",
        "tokens": {"in": total_tokens_in, "out": total_tokens_out},
        "cost_usd": 0.0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_target(target: str | pathlib.Path) -> str:
    """Return raw text from target, reading file if path-like."""
    target_str = str(target).strip()
    if not target_str:
        raise ValueError("target must not be empty or whitespace-only")

    # Auto-detect path: starts with "/" or "~" and exists as file
    if target_str.startswith("/") or target_str.startswith("~"):
        path = pathlib.Path(target_str).expanduser()
        if path.exists():
            if not path.is_file():
                raise ValueError(f"target path exists but is not a file: {path}")
            try:
                return path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ValueError(f"cannot read file {path}: {exc}") from exc
        else:
            raise ValueError(f"file path does not exist: {path}")

    return target_str


def _load_system_prompt() -> str:
    """Load the brief-normalizer.md system prompt."""
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _try_provider(
    provider: str,
    system: str,
    user: str,
    provider_chain: list[tuple[str, str, str | None]],
) -> dict[str, Any] | None:
    """
    Attempt to call a provider up to _MAX_ATTEMPTS times with exponential backoff.

    On success: validates XML, appends ("provider", "success", None) to chain, returns result dict.
    On permanent error or exhausted attempts: appends failure entry, returns None.
    """
    last_error: str | None = None

    for attempt in range(_MAX_ATTEMPTS):
        logger.debug("[%s] attempt %d/%d", provider, attempt + 1, _MAX_ATTEMPTS)
        try:
            result = call_provider(
                provider,
                system,
                user,
                timeout_s=240.0,
                reasoning={"effort": "high"},
                text={"verbosity": "medium"},
            )
            # Validate XML before accepting
            xml_text: str = result["text"]
            # v1.0.3: strip markdown fences if model wrapped output (common
            # despite system prompt; same issue triage hit).
            try:
                from ._advisor_common import _strip_markdown_fences
                xml_text = _strip_markdown_fences(xml_text)
            except ImportError:
                xml_text = xml_text.strip()
                if xml_text.startswith("```"):
                    lines = xml_text.splitlines()
                    lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    xml_text = "\n".join(lines).strip()
            # v1.0.4: extract <council_brief>...</council_brief> block via regex
            # (handles models prefixing with markdown preamble, e.g. Gemini Flash
            # often says "Here's the council brief:" before the XML). Also escape
            # bare-ampersands inside content that aren't already entities.
            import re as _re
            _m = _re.search(r"<council_brief.*?</council_brief>", xml_text, _re.DOTALL)
            if _m:
                xml_text = _m.group(0)
            # Escape bare ampersands that aren't already part of an entity (handles
            # Sonnet's tendency to write "rate & cost" inside content without escaping).
            xml_text = _re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", xml_text)
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError as parse_exc:
                # Schema fail is permanent — skip to next provider
                logger.warning("[%s] XML parse error: %s", provider, parse_exc)
                provider_chain.append((provider, "fail", f"schema: {parse_exc}"))
                return None

            # Schema-shape validation: root tag + required children
            if root.tag != "council_brief":
                reason = f"schema: root tag is {root.tag!r}, expected 'council_brief'"
                logger.warning("[%s] %s", provider, reason)
                provider_chain.append((provider, "fail", reason))
                return None
            missing = [c for c in _REQUIRED_CHILDREN if root.find(c) is None]
            if missing:
                reason = f"schema: missing required children: {missing}"
                logger.warning("[%s] %s", provider, reason)
                provider_chain.append((provider, "fail", reason))
                return None

            provider_chain.append((provider, "success", None))
            return result

        except PermanentProviderError as exc:
            logger.warning("[%s] permanent error: %s", provider, exc)
            provider_chain.append((provider, "fail", str(exc)))
            return None

        except TransientProviderError as exc:
            last_error = str(exc)
            logger.warning("[%s] transient error (attempt %d): %s", provider, attempt + 1, exc)
            if attempt < _MAX_ATTEMPTS - 1:
                delay = _BACKOFF_DELAYS[attempt]
                logger.debug("[%s] sleeping %.1fs before retry", provider, delay)
                time.sleep(delay)
            # else: fall through to exhaust

    # All attempts exhausted
    provider_chain.append((provider, "fail", last_error))
    return None


def _compute_cost(provider: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate cost in USD using the PROVIDER_REGISTRY price table."""
    entry = PROVIDER_REGISTRY.get(provider, {})
    price_in: float = entry.get("price_in", 0.0)
    price_out: float = entry.get("price_out", 0.0)
    return tokens_in * price_in + tokens_out * price_out
