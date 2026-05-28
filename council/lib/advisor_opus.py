"""
advisor_opus.py -- Claude Opus 4.8 advisor lane (Advisor B) for /council skill.

Thin wrapper around _advisor_common.run_advisor().
Max reasoning config: thinking={"type": "enabled", "effort": "high"}.

Drift-guard: if the Anthropic API returns HTTP 400 with a message referencing
"thinking" and "effort" (indicating the effort field was deprecated), _call_anthropic
in _providers.py automatically retries once with {"type": "enabled",
"budget_tokens": 16000} and logs ANTHROPIC_API_REGRESSION to stderr.
No action required in this wrapper.
"""

from __future__ import annotations

from . import _advisor_common

# FIX-H2: expose PROVIDER_KEY for vendor-diversity startup check
PROVIDER_KEY = "opus-4-8"


def advise(brief_xml: str, *, task_id: str, depth: str = "standard") -> dict:
    """
    Claude Opus 4.8 advisor lane (Advisor B).

    Args:
        brief_xml: Canonical <council_brief> XML from normalize.py.
        task_id:   Council task identifier for VK markers.
        depth:     "quick" | "standard" | "deep". Drives request timeout.

    Returns:
        Structured advisor dict. See _advisor_common.run_advisor() for full schema.
    """
    return _advisor_common.run_advisor(
        provider_key="opus-4-8",
        advisor_label="B",
        brief_xml=brief_xml,
        task_id=task_id,
        depth=depth,
        max_reasoning_kwargs={"thinking": {"type": "enabled", "effort": "high"}},
    )
