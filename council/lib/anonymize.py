"""
anonymize.py -- Task 7: 5a/5b/5c anti-collusion gate for the /council skill.

Pipeline:
  5a STRIP  -- remove all identity-leaking keys from each advisor result.
  5b VOICE  -- rewrite every bullet via runtime support-model normalizer; local fallback
               on any failure (no exception bubbles up).
  5c SHUFFLE -- deterministic label shuffle (A/B/C) using a seeded RNG.

Public API
----------
  anonymize(advisor_results, *, task_id, seed=None) -> dict

Exported constants (consumed by Task 8 reconciler)
---------------------------------------------------
  _ALLOWED_OUTPUT_KEYS
  _FORBIDDEN_OUTPUT_KEYS
"""

from __future__ import annotations

import pathlib
import random
import re
import secrets
import sys
from typing import Any

from . import _providers
from . import vk
from .runtime import support_provider_key

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Voice-normalizer provider. Non-advisor support routing uses the host runtime:
# Codex -> GPT-5.5; Claude Code -> Claude runtime model.
_VOICE_PROVIDER = support_provider_key()

# Keys that MAY appear in the anonymized output dicts (letter added by 5c).
_ALLOWED_OUTPUT_KEYS: frozenset[str] = frozenset({
    "verdict",
    "confidence",
    "nplf",
    "top_strengths",
    "top_risks",
    "critical_blockers",
    "direct_answer_md",
    "letter",
})

# Keys that MUST NOT appear in the anonymized output dicts.
_FORBIDDEN_OUTPUT_KEYS: frozenset[str] = frozenset({
    "advisor",
    "provider",
    "reasoning_chain",
    "tokens",
    "cost_usd",
    "duration_s",
    "status",
    "error",
    "label",
})

# Required keys in the advisor result BEFORE stripping.
_REQUIRED_INPUT_KEYS: frozenset[str] = frozenset({
    "verdict",
    "confidence",
    "nplf",
    "top_strengths",
    "top_risks",
    "critical_blockers",
})

# Registry key for voice-normalizer provider
_VOICE_REGISTRY_KEY = _VOICE_PROVIDER

# Price per token for cost accounting (input/output).
# Fallback pricing; actual prices are loaded from provider registry when present.
_VOICE_PRICE_IN = _providers.PROVIDER_REGISTRY.get(_VOICE_REGISTRY_KEY, {}).get("price_in", 5.00 / 1_000_000)
_VOICE_PRICE_OUT = _providers.PROVIDER_REGISTRY.get(_VOICE_REGISTRY_KEY, {}).get("price_out", 20.00 / 1_000_000)

# Load voice-normalizer system prompt once at module import time.
_PROMPT_PATH = (
    pathlib.Path(__file__).parent.parent / "prompts" / "voice-normalizer.md"
)
_VOICE_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Local fingerprint stripper (fallback when runtime support routing is unavailable)
# ---------------------------------------------------------------------------

_OPENING_PHRASES: list[str] = [
    r"^[Ii]n essence,?\s*",
    r"^[Ff]undamentally,?\s*",
    r"^[Aa]t its core,?\s*",
    r"^[Kk]ey insight:\s*",
    r"^[Cc]ritically,?\s*",
    r"^[Nn]otably,?\s*",
]

_CLOSING_TAGS: list[str] = [
    r",?\s*which is critical\.?\s*$",
    r",?\s*as expected\.?\s*$",
]


def _local_fingerprint_strip(bullet: str) -> str:
    """Deterministic regex-based fingerprint removal. No API calls."""
    s = bullet
    s = s.replace("—", ",")          # em-dash -> comma
    s = re.sub(r";\s*", ". ", s)          # semicolons -> period + space
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)   # **bold** -> text
    s = re.sub(r"\*([^*]+)\*", r"\1", s)        # *italic* -> text
    for pat in _OPENING_PHRASES:
        s = re.sub(pat, "", s)
    for pat in _CLOSING_TAGS:
        s = re.sub(pat, ".", s)
    s = re.sub(r",\s*,", ",", s)          # clean double commas from em-dash swap
    s = s.strip().strip(",").strip()
    # Capitalise first letter if we stripped an opening phrase.
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


# ---------------------------------------------------------------------------
# 5a: Strip identity-leaking keys
# ---------------------------------------------------------------------------

def _strip_5a(advisor_dict: dict) -> dict:
    """
    Remove all identity-leaking keys from an advisor result dict.

    Validates that required input keys are present before stripping.
    Returns a new dict containing only the public payload keys
    (verdict/confidence/nplf/top_strengths/top_risks/critical_blockers plus
    optional direct_answer_md).
    The 'letter' key is NOT added here; that happens in 5c.

    Raises:
        ValueError: if any required input key is missing.
    """
    missing = _REQUIRED_INPUT_KEYS - advisor_dict.keys()
    if missing:
        raise ValueError(
            f"_strip_5a: advisor dict missing required keys: {sorted(missing)}"
        )

    payload_keys = _ALLOWED_OUTPUT_KEYS - {"letter"}
    stripped = {k: advisor_dict[k] for k in payload_keys if k in advisor_dict}
    stripped.setdefault("direct_answer_md", "")
    return stripped


# ---------------------------------------------------------------------------
# 5b: Voice normalization via runtime support model
# ---------------------------------------------------------------------------

def _voice_normalize_5b(
    bullets: list[str],
    *,
    call_provider: Any = None,
) -> tuple[list[str], dict]:
    """
    Rewrite each bullet via the runtime support model (single-bullet-per-call for isolation).

    Args:
        bullets:       List of bullet strings to normalize.
        call_provider: Injectable for tests; defaults to _providers.call_provider.

    Returns:
        (normalized_bullets, {"in": tokens_in, "out": tokens_out, "cost_usd": float})

    Degradation:
        On any support-model failure the local fingerprint stripper is used for that
        bullet. A warning is written to stderr. The call NEVER raises.
    """
    if call_provider is None:
        call_provider = _providers.call_provider

    normalized: list[str] = []
    total_in = 0
    total_out = 0

    for bullet in bullets:
        if not bullet:
            normalized.append(bullet)
            continue
        try:
            result = call_provider(
                _VOICE_REGISTRY_KEY,
                _VOICE_SYSTEM_PROMPT,
                bullet,
                max_tokens=80,
                temperature=0.0,
                reasoning={"effort": "medium"},
                text={"verbosity": "low"},
            )
            text = result.get("text", "").strip()
            tok = result.get("tokens", {})
            total_in += tok.get("in", 0)
            total_out += tok.get("out", 0)
            if not text:
                sys.stderr.write(
                    f"[anonymize] support model returned empty for bullet, using local fingerprint stripper\n"
                )
                text = _local_fingerprint_strip(bullet)
            normalized.append(text)
        except Exception as exc:
            sys.stderr.write(
                "[anonymize] WARNING: support-model voice-normalize failed for bullet "
                + repr(bullet)[:60] + f": {exc}. Using local fallback.\n"
            )
            normalized.append(_local_fingerprint_strip(bullet))

    cost = total_in * _VOICE_PRICE_IN + total_out * _VOICE_PRICE_OUT
    return normalized, {"in": total_in, "out": total_out, "cost_usd": cost}


# ---------------------------------------------------------------------------
# 5c: Shuffle and assign A/B/C labels
# ---------------------------------------------------------------------------

def _shuffle_5c(
    stripped_results: list[dict],
    original_labels: list[str],
    seed: int,
) -> tuple[list[dict], dict]:
    """
    Shuffle stripped_results with a seeded RNG and assign letter labels A/B/C.

    Does NOT mutate input dicts.

    Args:
        stripped_results: List of 3 stripped dicts (no _original_label key).
        original_labels:  Parallel list of 3 original label strings.
        seed:             RNG seed for deterministic replay.

    Returns:
        (shuffled_dicts_with_letter, shuffle_map)
        shuffle_map = {"A": original_label, "B": ..., "C": ...}
    """
    assert len(stripped_results) == 3, (
        f"_shuffle_5c expects 3 results, got {len(stripped_results)}"
    )
    assert len(original_labels) == 3

    letters = ["A", "B", "C"]
    indices = list(range(3))
    random.Random(seed).shuffle(indices)

    shuffled: list[dict] = []
    shuffle_map: dict[str, str] = {}

    for new_idx, original_idx in enumerate(indices):
        out = dict(stripped_results[original_idx])  # shallow copy, no mutation
        out["letter"] = letters[new_idx]
        shuffled.append(out)
        shuffle_map[letters[new_idx]] = original_labels[original_idx]

    return shuffled, shuffle_map


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def anonymize(
    advisor_results: list[dict],
    *,
    task_id: str,
    seed: int | None = None,
) -> dict:
    """
    Run 5a -> 5b -> 5c anti-collusion gate on advisor results.

    Args:
        advisor_results: Exactly 3 dicts from advisor lanes (Tasks 4-6).
        task_id:         Pipeline task identifier for VK emission.
        seed:            Optional RNG seed for deterministic replay.

    Returns:
        {
          "anonymized": list[dict],   # 3 sanitized dicts, labelled A/B/C
          "shuffle_map": dict,
          "seed": int,
          "voice_norm_tokens": dict,  # {"in": int, "out": int}
          "voice_norm_cost_usd": float,
          "status": "OK" | "FAIL_5A" | "FAIL_5B" | "FAIL_5C",
          "error": str | None,
        }

    Raises:
        ValueError: if advisor_results is not exactly 3 dicts.
    """
    if not isinstance(advisor_results, list) or len(advisor_results) != 3:
        raise ValueError(
            f"anonymize: expected exactly 3 advisor results, got "
            f"{len(advisor_results) if isinstance(advisor_results, list) else type(advisor_results)}"
        )

    # Generate seed now so it is always present in the return dict even on failure.
    if seed is None:
        seed = secrets.randbits(32)

    vk.emit("anonymize", "entered", task_id)

    total_tokens: dict[str, int] = {"in": 0, "out": 0}
    total_cost: float = 0.0

    # -----------------------------------------------------------------------
    # 5a: Strip
    # -----------------------------------------------------------------------
    stripped: list[dict] = []
    original_labels: list[str] = []
    try:
        for i, adv in enumerate(advisor_results):
            s = _strip_5a(adv)
            stripped.append(s)
            original_labels.append(adv.get("label", f"label_{i}"))
    except (ValueError, KeyError, TypeError) as exc:
        return {
            "anonymized": [],
            "shuffle_map": {},
            "seed": seed,
            "voice_norm_tokens": total_tokens,
            "voice_norm_cost_usd": total_cost,
            "status": "FAIL_5A",
            "error": str(exc),
        }

    # -----------------------------------------------------------------------
    # 5b: Voice normalize
    # -----------------------------------------------------------------------
    try:
        for s in stripped:
            for field in ("top_strengths", "top_risks", "critical_blockers"):
                bullets: list[str] = s.get(field) or []
                if not bullets:
                    continue
                normalized, tok_info = _voice_normalize_5b(bullets)
                s[field] = normalized
                total_tokens["in"] += tok_info["in"]
                total_tokens["out"] += tok_info["out"]
                total_cost += tok_info["cost_usd"]
    except Exception as exc:
        return {
            "anonymized": [],
            "shuffle_map": {},
            "seed": seed,
            "voice_norm_tokens": total_tokens,
            "voice_norm_cost_usd": total_cost,
            "status": "FAIL_5B",
            "error": str(exc),
        }

    # -----------------------------------------------------------------------
    # 5c: Shuffle
    # -----------------------------------------------------------------------
    try:
        anonymized, shuffle_map = _shuffle_5c(stripped, original_labels, seed)
    except Exception as exc:
        return {
            "anonymized": [],
            "shuffle_map": {},
            "seed": seed,
            "voice_norm_tokens": total_tokens,
            "voice_norm_cost_usd": total_cost,
            "status": "FAIL_5C",
            "error": str(exc),
        }

    # -----------------------------------------------------------------------
    # Verify: NO forbidden key must survive 5a/5b/5c (defense-in-depth).
    # -----------------------------------------------------------------------
    for d in anonymized:
        leaked = _FORBIDDEN_OUTPUT_KEYS & d.keys()
        if leaked:
            return {
                "anonymized": None,
                "shuffle_map": shuffle_map,
                "seed": seed,
                "voice_norm_tokens": total_tokens,
                "voice_norm_cost_usd": total_cost,
                "status": "FAIL_5A",
                "error": f"forbidden key(s) leaked through pipeline: {sorted(leaked)}",
            }

    vk.emit("anonymize", "completed", task_id, seed=seed)

    return {
        "anonymized": anonymized,
        "shuffle_map": shuffle_map,
        "seed": seed,
        "voice_norm_tokens": total_tokens,
        "voice_norm_cost_usd": total_cost,
        "status": "OK",
        "error": None,
    }
