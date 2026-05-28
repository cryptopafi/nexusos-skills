"""
test_advisor_lanes.py -- 9 pytest cases (3 per lane) for advisor lane wrappers.

Tests:
- Module imports cleanly.
- Correct provider_key + max_reasoning_kwargs forwarded (spy assertion).
- Correct advisor_label assigned.

All tests use monkeypatch on lib._providers.call_provider. No live API calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

import lib._providers as providers_mod
import lib._advisor_common as common_mod


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_TASK_ID = "council-test-0000-lanes"

_VALID_JSON = """{
  "verdict": "REVISE",
  "confidence": 0.70,
  "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
  "top_strengths": ["s1", "s2", "s3"],
  "top_risks": ["r1", "r2", "r3"],
  "critical_blockers": [],
  "reasoning_chain": "Reasoning."
}"""


def _make_response(text: str) -> dict[str, Any]:
    return {"text": text, "tokens": {"in": 50, "out": 100}}


# ---------------------------------------------------------------------------
# Gemini lane (Advisor A) — cases 1-3
# ---------------------------------------------------------------------------

class TestGeminiLane:

    def test_gemini_module_exists(self):
        """Case 1: advisor_gemini module imports cleanly and exposes advise()."""
        import lib.advisor_gemini as gemini_mod
        assert callable(gemini_mod.advise)

    def test_gemini_kwargs_propagation(self, monkeypatch: pytest.MonkeyPatch):
        """Case 2: advise() calls run_advisor with provider_key=gemini-3.1-pro and correct max_reasoning_kwargs."""
        import lib.advisor_gemini as gemini_mod

        captured: dict[str, Any] = {}

        def _spy_run_advisor(**kwargs):
            captured.update(kwargs)
            # Return minimal valid result to avoid downstream errors
            return {
                "advisor": kwargs["provider_key"],
                "label": kwargs["advisor_label"],
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": "ok",
                "tokens": {"in": 50, "out": 100},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr(common_mod, "run_advisor", _spy_run_advisor)

        gemini_mod.advise("<council_brief>test</council_brief>", task_id=_TASK_ID)

        assert captured["provider_key"] == "gemini-3.1-pro"
        assert captured["max_reasoning_kwargs"] == {"thinking_config": {"thinking_level": "high"}}

    def test_gemini_advisor_label(self, monkeypatch: pytest.MonkeyPatch):
        """Case 3: Gemini lane sets advisor_label='A'."""
        import lib.advisor_gemini as gemini_mod

        captured: dict[str, Any] = {}

        def _spy_run_advisor(**kwargs):
            captured.update(kwargs)
            return {
                "advisor": kwargs["provider_key"],
                "label": kwargs["advisor_label"],
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": "ok",
                "tokens": {"in": 50, "out": 100},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr(common_mod, "run_advisor", _spy_run_advisor)

        gemini_mod.advise("<council_brief>test</council_brief>", task_id=_TASK_ID)

        assert captured["advisor_label"] == "A"


# ---------------------------------------------------------------------------
# Opus lane (Advisor B) — cases 4-6
# ---------------------------------------------------------------------------

class TestOpusLane:

    def test_opus_module_exists(self):
        """Case 4: advisor_opus module imports cleanly and exposes advise()."""
        import lib.advisor_opus as opus_mod
        assert callable(opus_mod.advise)

    def test_opus_kwargs_propagation(self, monkeypatch: pytest.MonkeyPatch):
        """Case 5: advise() calls run_advisor with provider_key=opus-4-8 and correct max_reasoning_kwargs."""
        import lib.advisor_opus as opus_mod

        captured: dict[str, Any] = {}

        def _spy_run_advisor(**kwargs):
            captured.update(kwargs)
            return {
                "advisor": kwargs["provider_key"],
                "label": kwargs["advisor_label"],
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": "ok",
                "tokens": {"in": 50, "out": 100},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr(common_mod, "run_advisor", _spy_run_advisor)

        opus_mod.advise("<council_brief>test</council_brief>", task_id=_TASK_ID)

        assert captured["provider_key"] == "opus-4-8"
        assert captured["max_reasoning_kwargs"] == {"thinking": {"type": "enabled", "effort": "high"}}

    def test_opus_advisor_label(self, monkeypatch: pytest.MonkeyPatch):
        """Case 6: Opus lane sets advisor_label='B'."""
        import lib.advisor_opus as opus_mod

        captured: dict[str, Any] = {}

        def _spy_run_advisor(**kwargs):
            captured.update(kwargs)
            return {
                "advisor": kwargs["provider_key"],
                "label": kwargs["advisor_label"],
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": "ok",
                "tokens": {"in": 50, "out": 100},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr(common_mod, "run_advisor", _spy_run_advisor)

        opus_mod.advise("<council_brief>test</council_brief>", task_id=_TASK_ID)

        assert captured["advisor_label"] == "B"


# ---------------------------------------------------------------------------
# GPT lane (Advisor C) — cases 7-9
# ---------------------------------------------------------------------------

class TestGptLane:

    def test_gpt_module_exists(self):
        """Case 7: advisor_gpt module imports cleanly and exposes advise()."""
        import lib.advisor_gpt as gpt_mod
        assert callable(gpt_mod.advise)

    def test_gpt_kwargs_propagation(self, monkeypatch: pytest.MonkeyPatch):
        """Case 8: advise() calls run_advisor with provider_key=gpt-5.5 and correct max_reasoning_kwargs."""
        import lib.advisor_gpt as gpt_mod

        captured: dict[str, Any] = {}

        def _spy_run_advisor(**kwargs):
            captured.update(kwargs)
            return {
                "advisor": kwargs["provider_key"],
                "label": kwargs["advisor_label"],
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": "ok",
                "tokens": {"in": 50, "out": 100},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr(common_mod, "run_advisor", _spy_run_advisor)

        gpt_mod.advise("<council_brief>test</council_brief>", task_id=_TASK_ID)

        assert captured["provider_key"] == "gpt-5.5"
        mkw = captured["max_reasoning_kwargs"]
        assert "reasoning" in mkw, f"'reasoning' missing from max_reasoning_kwargs: {mkw}"
        assert "text" in mkw, f"'text' missing from max_reasoning_kwargs: {mkw}"
        assert "_use_responses_api" in mkw, f"'_use_responses_api' missing from max_reasoning_kwargs: {mkw}"
        assert mkw["_use_responses_api"] is True

    def test_gpt_advisor_label(self, monkeypatch: pytest.MonkeyPatch):
        """Case 9: GPT lane sets advisor_label='C'."""
        import lib.advisor_gpt as gpt_mod

        captured: dict[str, Any] = {}

        def _spy_run_advisor(**kwargs):
            captured.update(kwargs)
            return {
                "advisor": kwargs["provider_key"],
                "label": kwargs["advisor_label"],
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {"n": 2.8, "p": 3.1, "l": 2.9, "f": 2.7},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": "ok",
                "tokens": {"in": 50, "out": 100},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr(common_mod, "run_advisor", _spy_run_advisor)

        gpt_mod.advise("<council_brief>test</council_brief>", task_id=_TASK_ID)

        assert captured["advisor_label"] == "C"
