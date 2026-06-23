"""Regression tests for /council advisor fallback lanes."""

from __future__ import annotations

from typing import Any

import pytest


class _Meter:
    def __init__(self) -> None:
        self.entries: list[tuple[float, str, str]] = []

    def add_raw(self, *, cost_usd: float, step: str, label: str) -> None:
        self.entries.append((cost_usd, step, label))


def _failed_primary() -> dict[str, Any]:
    return {
        "advisor": "ollama-glm-5.2-cloud",
        "label": "A",
        "verdict": "ABSTAIN",
        "confidence": 0.0,
        "nplf": {"n": 0, "p": 0, "l": 0, "f": 0},
        "top_strengths": [],
        "top_risks": [],
        "critical_blockers": [],
        "direct_answer_md": "",
        "reasoning_chain": "",
        "tokens": {"in": 0, "out": 0},
        "cost_usd": 0.0,
        "duration_s": 0.0,
        "status": "UNAVAILABLE",
        "error": "MODEL_CAPACITY_EXHAUSTED",
    }


def _ok(provider: str, label: str = "A") -> dict[str, Any]:
    return {
        "advisor": provider,
        "label": label,
        "verdict": "PASS",
        "confidence": 0.81,
        "nplf": {"n": 3.2, "p": 3.4, "l": 3.1, "f": 3.3},
        "top_strengths": ["s1", "s2", "s3"],
        "top_risks": ["r1", "r2", "r3"],
        "critical_blockers": [],
        "direct_answer_md": "ok",
        "reasoning_chain": "private",
        "tokens": {"in": 10, "out": 20},
        "cost_usd": 0.01,
        "duration_s": 0.1,
        "status": "OK",
        "error": None,
    }


def test_failed_primary_skips_duplicate_ollama_and_uses_deepseek(monkeypatch):
    from lib import orchestrator

    calls: list[str] = []

    def fake_call(lane_name, lane_letter, *args, **kwargs):
        calls.append(lane_name)
        if lane_name == "advisor_gemini":
            return _failed_primary()
        if lane_name == "advisor_fallback_deepseek_v4_pro":
            return _ok("deepseek-v4-pro", lane_letter)
        return _ok(lane_name, lane_letter)

    monkeypatch.setattr(orchestrator, "_call_advisor_lane_with_timeout", fake_call)

    results = orchestrator._build_advisor_list("<council_brief/>", "task-1", "standard", _Meter())

    assert calls[:2] == ["advisor_gemini", "advisor_fallback_deepseek_v4_pro"]
    assert results[0]["advisor"] == "deepseek-v4-pro"
    assert results[0]["substitute_for"] == "advisor_gemini"
    assert results[0]["primary_failure"] == "MODEL_CAPACITY_EXHAUSTED"
    assert results[0]["fallback_attempts"][0]["provider_key"] == "ollama-glm-5.2-cloud"
    assert results[0]["fallback_attempts"][0]["status"] == "SKIPPED"
    assert results[0]["label"] == "A"


def test_duplicate_ollama_primary_falls_through_to_deepseek(monkeypatch):
    from lib import orchestrator

    calls: list[str] = []

    def fake_call(lane_name, lane_letter, *args, **kwargs):
        calls.append(lane_name)
        if lane_name == "advisor_gemini":
            return _failed_primary()
        if lane_name == "advisor_fallback_deepseek_v4_pro":
            return _ok("deepseek-v4-pro", lane_letter)
        return _ok(lane_name, lane_letter)

    monkeypatch.setattr(orchestrator, "_call_advisor_lane_with_timeout", fake_call)

    results = orchestrator._build_advisor_list("<council_brief/>", "task-2", "standard", _Meter())

    assert calls[:2] == [
        "advisor_gemini",
        "advisor_fallback_deepseek_v4_pro",
    ]
    assert results[0]["advisor"] == "deepseek-v4-pro"
    assert results[0]["fallback_attempts"][0]["provider_key"] == "ollama-glm-5.2-cloud"
    assert results[0]["fallback_attempts"][0]["status"] == "SKIPPED"
    assert results[0]["fallback_attempts"][1]["provider_key"] == "deepseek-v4-pro"


def test_no_fallback_when_primary_succeeds(monkeypatch):
    from lib import orchestrator

    calls: list[str] = []

    def fake_call(lane_name, lane_letter, *args, **kwargs):
        calls.append(lane_name)
        return _ok(lane_name, lane_letter)

    monkeypatch.setattr(orchestrator, "_call_advisor_lane_with_timeout", fake_call)

    results = orchestrator._build_advisor_list("<council_brief/>", "task-3", "standard", _Meter())

    assert calls == ["advisor_gemini", "advisor_opus", "advisor_gpt"]
    assert "substitute_for" not in results[0]


def test_missing_fallbacks_preserve_primary_failure(monkeypatch):
    from lib import orchestrator

    def fake_call(lane_name, lane_letter, *args, **kwargs):
        failed = _failed_primary()
        failed["advisor"] = lane_name
        failed["label"] = lane_letter
        failed["error"] = f"{lane_name} unavailable"
        return failed

    monkeypatch.setattr(orchestrator, "_call_advisor_lane_with_timeout", fake_call)

    results = orchestrator._build_advisor_list("<council_brief/>", "task-4", "standard", _Meter())

    assert results[0]["advisor"] == "advisor_gemini"
    assert results[0]["verdict"] == "ABSTAIN"
    assert [a["provider_key"] for a in results[0]["fallback_attempts"]] == [
        "ollama-glm-5.2-cloud",
        "deepseek-v4-pro",
    ]


@pytest.mark.preflight_unit
def test_preflight_counts_available_fallbacks(monkeypatch):
    from lib import orchestrator

    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setenv("OLLAMA_API_KEY", "test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    warnings = orchestrator._preflight_provider_check("standard", 2)

    assert warnings
    assert "fallback candidate" in warnings[0]
