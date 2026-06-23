"""
advisor_gemini.py -- Ollama Cloud GLM 5.2 advisor lane (Advisor A) for /council skill.

Thin wrapper around _advisor_common.run_advisor().
Max reasoning config: options={"num_ctx": 131072}.
"""

from __future__ import annotations

from . import _advisor_common

# FIX-H2: expose PROVIDER_KEY for vendor-diversity startup check.
# The module name remains advisor_gemini for compatibility with the existing
# orchestrator lane wiring; the actual primary model is now Ollama Cloud GLM 5.2.
PROVIDER_KEY = "ollama-glm-5.2-cloud"


def advise(brief_xml: str, *, task_id: str, depth: str = "standard") -> dict:
    """
    Ollama Cloud GLM 5.2 advisor lane (Advisor A).

    Args:
        brief_xml: Canonical <council_brief> XML from normalize.py.
        task_id:   Council task identifier for VK markers.
        depth:     "quick" | "standard" | "deep". Drives request timeout.

    Returns:
        Structured advisor dict. See _advisor_common.run_advisor() for full schema.
    """
    return _advisor_common.run_advisor(
        provider_key=PROVIDER_KEY,
        advisor_label="A",
        brief_xml=brief_xml,
        task_id=task_id,
        depth=depth,
        max_reasoning_kwargs={"options": {"num_ctx": 131072}},
    )
