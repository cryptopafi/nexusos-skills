"""
advisor_gemini.py -- Gemini 3.1 Pro advisor lane (Advisor A) for /council skill.

Thin wrapper around _advisor_common.run_advisor().
Max reasoning config: thinking_config={"thinking_level": "high"}.
"""

from __future__ import annotations

from . import _advisor_common

# FIX-H2: expose PROVIDER_KEY for vendor-diversity startup check
PROVIDER_KEY = "gemini-3.1-pro"


def advise(brief_xml: str, *, task_id: str, depth: str = "standard") -> dict:
    """
    Gemini 3.1 Pro advisor lane (Advisor A).

    Args:
        brief_xml: Canonical <council_brief> XML from normalize.py.
        task_id:   Council task identifier for VK markers.
        depth:     "quick" | "standard" | "deep". Drives request timeout.

    Returns:
        Structured advisor dict. See _advisor_common.run_advisor() for full schema.
    """
    return _advisor_common.run_advisor(
        provider_key="gemini-3.1-pro",
        advisor_label="A",
        brief_xml=brief_xml,
        task_id=task_id,
        depth=depth,
        max_reasoning_kwargs={"thinking_config": {"thinking_level": "high"}},
    )
