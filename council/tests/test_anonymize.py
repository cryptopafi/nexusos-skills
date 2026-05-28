"""
test_anonymize.py -- 14 pytest cases for Task 7 anonymization layer (5a/5b/5c).

All runtime support-model calls are monkeypatched via _providers.call_provider.
No live API calls are made.
"""

from __future__ import annotations

import io
import sys
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from lib import anonymize as anon_mod
from lib.anonymize import (
    _local_fingerprint_strip,
    _strip_5a,
    _voice_normalize_5b,
    _shuffle_5c,
    anonymize,
    _ALLOWED_OUTPUT_KEYS,
    _FORBIDDEN_OUTPUT_KEYS,
)
from lib._providers import PermanentProviderError
from lib.runtime import support_provider_key


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_advisor(
    label: str = "X",
    verdict: str = "PASS",
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    include_reasoning: bool = True,
) -> dict:
    """Build a realistic full advisor result dict."""
    return {
        "advisor": "advisor_gemini",
        "provider": "gemini-3.1-pro",
        "label": label,
        "verdict": verdict,
        "confidence": 0.85,
        "nplf": {"n": 0.7, "p": 0.8, "l": 0.6, "f": 0.9},
        "top_strengths": strengths if strengths is not None else ["Strength one.", "Strength two."],
        "top_risks": risks if risks is not None else ["Risk one.", "Risk two."],
        "critical_blockers": blockers if blockers is not None else ["Blocker one."],
        "reasoning_chain": "hidden chain text" if include_reasoning else None,
        "tokens": {"in": 1000, "out": 500},
        "cost_usd": 0.05,
        "duration_s": 12.3,
        "status": "OK",
        "error": None,
    }


def _three_advisors(
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
) -> list[dict]:
    return [
        _make_advisor("label_1", "PASS", strengths, risks, blockers),
        _make_advisor("label_2", "REVISE", strengths, risks, blockers),
        _make_advisor("label_3", "BLOCK", strengths, risks, blockers),
    ]


def _mock_call_provider(text: str = "NORMALIZED bullet") -> MagicMock:
    """Returns a mock that simulates a successful support-model call."""
    m = MagicMock(return_value={"text": text, "tokens": {"in": 10, "out": 5}})
    return m


# ---------------------------------------------------------------------------
# 5a STRIP — 3 cases
# ---------------------------------------------------------------------------

class TestStrip5a:
    def test_5a_strips_forbidden_keys(self):
        """Full 13-key advisor dict -> output has exactly 6 allowed keys, no reasoning_chain."""
        advisor = _make_advisor()
        result = _strip_5a(advisor)
        allowed_no_letter = _ALLOWED_OUTPUT_KEYS - {"letter"}
        assert set(result.keys()) == allowed_no_letter
        assert "reasoning_chain" not in result
        for key in _FORBIDDEN_OUTPUT_KEYS:
            assert key not in result, f"Forbidden key {key!r} present in stripped output"

    def test_5a_keeps_allowed_keys(self):
        """Strip preserves verdict, confidence, nplf, top_strengths, top_risks, critical_blockers by value."""
        strengths = ["S1", "S2"]
        risks = ["R1"]
        blockers = ["B1", "B2"]
        advisor = _make_advisor(strengths=strengths, risks=risks, blockers=blockers)
        result = _strip_5a(advisor)
        assert result["verdict"] == "PASS"
        assert result["confidence"] == pytest.approx(0.85)
        assert result["nplf"] == {"n": 0.7, "p": 0.8, "l": 0.6, "f": 0.9}
        assert result["top_strengths"] == strengths
        assert result["top_risks"] == risks
        assert result["critical_blockers"] == blockers

    def test_5a_rejects_missing_required(self):
        """Dict missing top_strengths -> ValueError."""
        advisor = _make_advisor()
        del advisor["top_strengths"]
        with pytest.raises(ValueError, match="missing required keys"):
            _strip_5a(advisor)


# ---------------------------------------------------------------------------
# 5b VOICE NORMALIZE — 5 cases
# ---------------------------------------------------------------------------

class TestVoiceNormalize5b:
    def test_5b_calls_haiku_per_bullet(self):
        """3 strengths + 3 risks + 1 blocker = 7 bullets -> support model called exactly 7 times."""
        mock_cp = _mock_call_provider()
        bullets = ["S1", "S2", "S3", "R1", "R2", "R3", "B1"]
        _voice_normalize_5b(bullets, call_provider=mock_cp)
        assert mock_cp.call_count == 7
        # Every call should reference the runtime support registry key
        for c in mock_cp.call_args_list:
            assert c.args[0] == support_provider_key()

    def test_5b_returns_normalized_bullets(self):
        """Mock call_provider echoes 'NORMALIZED: <input>' -> all outputs prefixed."""
        def echo_cp(provider, system, user, **kwargs):
            return {"text": f"NORMALIZED: {user}", "tokens": {"in": 5, "out": 5}}

        bullets = ["Alpha", "Beta", "Gamma"]
        result, _ = _voice_normalize_5b(bullets, call_provider=echo_cp)
        assert len(result) == 3
        for b, r in zip(bullets, result):
            assert r.startswith("NORMALIZED:")

    def test_5b_falls_back_to_local_stripper_on_haiku_fail(self, capsys):
        """PermanentProviderError -> local stripper runs, output cleaned, warning in stderr."""
        def fail_cp(provider, system, user, **kwargs):
            raise PermanentProviderError("haiku-4-5", "auth failure")

        bullet = "Fundamentally — the market lacks clarity, which is critical."
        result, tok = _voice_normalize_5b([bullet], call_provider=fail_cp)
        captured = capsys.readouterr()
        assert len(result) == 1
        assert "—" not in result[0]
        assert "Fundamentally" not in result[0]
        assert "which is critical" not in result[0]
        assert "WARNING" in captured.err

    def test_5b_token_accumulation(self):
        """3 bullets each returning in=100, out=50 -> total in=300, out=150, cost > 0."""
        def token_cp(provider, system, user, **kwargs):
            return {"text": "normalized", "tokens": {"in": 100, "out": 50}}

        bullets = ["B1", "B2", "B3"]
        _, tok_info = _voice_normalize_5b(bullets, call_provider=token_cp)
        assert tok_info["in"] == 300
        assert tok_info["out"] == 150
        assert tok_info["cost_usd"] > 0.0

    def test_local_fingerprint_strip_unit(self):
        """Pure unit test of _local_fingerprint_strip with 5 fingerprint patterns."""
        # em-dash
        assert "—" not in _local_fingerprint_strip("Strong team — great execution.")
        # semicolon as conjunction
        result = _local_fingerprint_strip("Great team; they shipped 3 products.")
        assert ";" not in result
        # bold
        assert "**" not in _local_fingerprint_strip("**Strong** execution track record.")
        # italic
        assert "*" not in _local_fingerprint_strip("*Key* risk is market saturation.")
        # opening phrase
        result = _local_fingerprint_strip("In essence, the model is broken.")
        assert not result.startswith("In essence")
        # closing tag
        result = _local_fingerprint_strip("Revenue is unclear, which is critical.")
        assert "which is critical" not in result


# ---------------------------------------------------------------------------
# 5c SHUFFLE — 3 cases
# ---------------------------------------------------------------------------

class TestShuffle5c:
    _LABELS = ["label_1", "label_2", "label_3"]

    def _make_stripped_list(self) -> list[dict]:
        return [
            {
                "verdict": "PASS",
                "confidence": 0.9,
                "nplf": {},
                "top_strengths": [],
                "top_risks": [],
                "critical_blockers": [],
            },
            {
                "verdict": "REVISE",
                "confidence": 0.7,
                "nplf": {},
                "top_strengths": [],
                "top_risks": [],
                "critical_blockers": [],
            },
            {
                "verdict": "BLOCK",
                "confidence": 0.5,
                "nplf": {},
                "top_strengths": [],
                "top_risks": [],
                "critical_blockers": [],
            },
        ]

    def test_5c_shuffles_with_seed(self):
        """Same seed=42 yields identical shuffle on 2 independent calls."""
        result1, map1 = _shuffle_5c(self._make_stripped_list(), self._LABELS, seed=42)
        result2, map2 = _shuffle_5c(self._make_stripped_list(), self._LABELS, seed=42)
        assert [d["letter"] for d in result1] == [d["letter"] for d in result2]
        assert map1 == map2
        # FIX-3: full dict equality, not just letters
        assert result1 == result2

    def test_5c_shuffle_map_invertible(self):
        """shuffle_map[letter] points to the original label of that slot."""
        shuffled, shuffle_map = _shuffle_5c(self._make_stripped_list(), self._LABELS, seed=7)
        assert set(shuffle_map.keys()) == {"A", "B", "C"}
        # Each mapped original label must be one of the input labels.
        original_labels = {"label_1", "label_2", "label_3"}
        assert set(shuffle_map.values()) == original_labels
        # The letter on each dict must match the shuffle_map key.
        for d in shuffled:
            letter = d["letter"]
            assert letter in shuffle_map

    def test_5c_adds_letter_field(self):
        """Shuffled list has exactly letters A, B, C each on a distinct dict."""
        shuffled, _ = _shuffle_5c(self._make_stripped_list(), self._LABELS, seed=99)
        letters = [d["letter"] for d in shuffled]
        assert sorted(letters) == ["A", "B", "C"]
        assert len(set(letters)) == 3  # all distinct

    def test_5c_does_not_mutate_input_dicts(self):
        """_shuffle_5c must not add _original_label or letter to the input dicts."""
        stripped = self._make_stripped_list()
        # Snapshot keys before call
        keys_before = [frozenset(d.keys()) for d in stripped]
        returned, _ = _shuffle_5c(stripped, self._LABELS, seed=42)
        # Input dicts unchanged
        for before, d in zip(keys_before, stripped):
            assert frozenset(d.keys()) == before, "Input dict was mutated"
            assert "_original_label" not in d
            assert "letter" not in d
        # Returned dicts have letter; input dicts do not
        for out_d in returned:
            assert "letter" in out_d


# ---------------------------------------------------------------------------
# Integration — 3 cases
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_pipeline_happy_path(self):
        """3 mocked advisor results -> full pipeline returns sanitized output."""
        mock_cp = _mock_call_provider("Clean bullet.")
        advisors = _three_advisors(
            strengths=["S1", "S2"],
            risks=["R1"],
            blockers=["B1"],
        )

        with patch.object(anon_mod._providers, "call_provider", mock_cp):
            result = anonymize(advisors, task_id="test-task-001", seed=42)

        assert result["status"] == "OK"
        assert result["error"] is None
        assert result["seed"] == 42
        assert len(result["anonymized"]) == 3
        letters = {d["letter"] for d in result["anonymized"]}
        assert letters == {"A", "B", "C"}
        assert set(result["shuffle_map"].keys()) == {"A", "B", "C"}

        # No identity keys in any output dict.
        for d in result["anonymized"]:
            for forbidden in _FORBIDDEN_OUTPUT_KEYS:
                assert forbidden not in d, f"Forbidden key {forbidden!r} leaked into output"

    def test_vk_markers_emitted(self, capsys):
        """VK entered and completed markers each emitted exactly once, seed in completed line."""
        mock_cp = _mock_call_provider()
        advisors = _three_advisors(strengths=["S1"], risks=["R1"], blockers=[])

        with patch.object(anon_mod._providers, "call_provider", mock_cp):
            result = anonymize(advisors, task_id="test-task-002", seed=77)

        captured = capsys.readouterr()
        lines = captured.out.splitlines()

        entered_lines = [l for l in lines if "STEP=anonymize" in l and "STATE=entered" in l]
        completed_lines = [l for l in lines if "STEP=anonymize" in l and "STATE=completed" in l]

        assert len(entered_lines) == 1, f"Expected 1 entered line, got: {entered_lines}"
        assert len(completed_lines) == 1, f"Expected 1 completed line, got: {completed_lines}"
        assert "seed=77" in completed_lines[0]

    def test_abstain_advisor_passes_through(self):
        """Advisor with ABSTAIN verdict and empty bullets passes through; 0 GPT-5.5 calls for empties."""
        call_count = 0

        def counting_cp(provider, system, user, **kwargs):
            nonlocal call_count
            call_count += 1
            return {"text": "normalized", "tokens": {"in": 10, "out": 5}}

        advisors = [
            _make_advisor("label_1", "PASS", strengths=["S1"], risks=["R1"], blockers=["B1"]),
            _make_advisor("label_2", "REVISE", strengths=["S2"], risks=["R2"], blockers=[]),
            {
                "advisor": "advisor_opus",
                "provider": "opus-4-8",
                "label": "label_3",
                "verdict": "ABSTAIN",
                "confidence": 0.0,
                "nplf": {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0},
                "top_strengths": [],
                "top_risks": [],
                "critical_blockers": [],
                "reasoning_chain": None,
                "tokens": {"in": 0, "out": 0},
                "cost_usd": 0.0,
                "duration_s": 0.0,
                "status": "ABSTAIN",
                "error": None,
            },
        ]

        with patch.object(anon_mod._providers, "call_provider", counting_cp):
            result = anonymize(advisors, task_id="test-task-003", seed=11)

        assert result["status"] == "OK"
        # Abstain advisor should be in output with verdict preserved.
        verdicts = {d["verdict"] for d in result["anonymized"]}
        assert "ABSTAIN" in verdicts
        # Empty bullet lists must not trigger GPT-5.5 calls (label_3 has 0 bullets).
        # label_1 has 3 bullets, label_2 has 2 bullets -> 5 calls total.
        assert call_count == 5


# ---------------------------------------------------------------------------
# FIX-1: Post-shuffle leak check covers ALL 9 forbidden keys
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("leaked_key", sorted(_FORBIDDEN_OUTPUT_KEYS))
def test_post_shuffle_leak_check_catches_all_forbidden_keys(leaked_key, monkeypatch):
    """
    Simulate a refactor bug where _strip_5a accidentally preserves a forbidden
    key. anonymize() must return status="FAIL_5A" with the key named in error.

    One sub-case per forbidden key (9 total via parametrize).
    """
    original_strip = anon_mod._strip_5a

    def patched_strip(advisor_dict: dict) -> dict:
        result = original_strip(advisor_dict)
        # Inject the forbidden key back to simulate a pipeline bug.
        result[leaked_key] = "injected_value"
        return result

    monkeypatch.setattr(anon_mod, "_strip_5a", patched_strip)

    mock_cp = _mock_call_provider("Clean bullet.")
    advisors = _three_advisors(strengths=["S1"], risks=["R1"], blockers=["B1"])

    with patch.object(anon_mod._providers, "call_provider", mock_cp):
        result = anonymize(advisors, task_id="leak-test", seed=42)

    assert result["status"] == "FAIL_5A", (
        f"Expected FAIL_5A when '{leaked_key}' leaks, got {result['status']}"
    )
    assert leaked_key in result["error"], (
        f"Expected '{leaked_key}' mentioned in error, got: {result['error']}"
    )
