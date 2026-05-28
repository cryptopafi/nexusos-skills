"""
advisor_gpt.py -- GPT-5.5 advisor lane (Advisor C) for /council skill.

Thin wrapper around _advisor_common.run_advisor().
Max reasoning config: reasoning={"effort": "xhigh"}, text={"verbosity": "high"}.
Uses Responses API endpoint (/v1/responses) via the _use_responses_api internal signal.

The _use_responses_api=True key in max_reasoning_kwargs is an internal signal
consumed by _providers._call_openai to route to client.responses.create()
instead of client.chat.completions.create(). The key is stripped before
the kwargs reach the OpenAI SDK.
"""

from __future__ import annotations

from . import _advisor_common

# FIX-H2: expose PROVIDER_KEY for vendor-diversity startup check
PROVIDER_KEY = "gpt-5.5"


def advise(brief_xml: str, *, task_id: str, depth: str = "standard") -> dict:
    """
    GPT-5.5 advisor lane (Advisor C).

    Args:
        brief_xml: Canonical <council_brief> XML from normalize.py.
        task_id:   Council task identifier for VK markers.
        depth:     "quick" | "standard" | "deep". Drives request timeout.

    Returns:
        Structured advisor dict. See _advisor_common.run_advisor() for full schema.
    """
    return _advisor_common.run_advisor(
        provider_key="gpt-5.5",
        advisor_label="C",
        brief_xml=brief_xml,
        task_id=task_id,
        depth=depth,
        max_reasoning_kwargs={
            "reasoning": {"effort": "xhigh"},
            "text": {"verbosity": "high"},
            "_use_responses_api": True,
        },
    )
