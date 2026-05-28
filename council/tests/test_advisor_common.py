"""
test_advisor_common.py -- 8 pytest cases for lib/_advisor_common.py.

All tests use monkeypatch on lib._providers.call_provider. No live API calls.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

import lib._advisor_common as common_mod
import lib._providers as providers_mod
from lib._providers import TransientProviderError, PermanentProviderError


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_TASK_ID = "council-test-0000-advisor"

_VALID_JSON = """{
  "verdict": "PASS",
  "confidence": 0.85,
  "nplf": {"n": 3.5, "p": 3.2, "l": 3.8, "f": 3.1},
  "top_strengths": ["strength_one", "strength_two", "strength_three"],
  "top_risks": ["risk_one", "risk_two", "risk_three"],
  "critical_blockers": [],
  "reasoning_chain": "Full reasoning here."
}"""

_REVISE_JSON = """{
  "verdict": "REVISE",
  "confidence": 0.60,
  "nplf": {"n": 2.5, "p": 2.8, "l": 3.0, "f": 2.2},
  "top_strengths": ["s1", "s2", "s3"],
  "top_risks": ["r1", "r2", "r3"],
  "critical_blockers": [],
  "reasoning_chain": "Some concerns."
}"""


def _make_response(text: str, tokens_in: int = 100, tokens_out: int = 200) -> dict[str, Any]:
    return {"text": text, "tokens": {"in": tokens_in, "out": tokens_out}}


def _run(monkeypatch, call_fn, label: str = "A", depth: str = "standard",
         provider_key: str = "gemini-3.1-pro") -> dict[str, Any]:
    monkeypatch.setattr(providers_mod, "call_provider", call_fn)
    return common_mod.run_advisor(
        provider_key=provider_key,
        advisor_label=label,
        brief_xml="<council_brief>Test brief.</council_brief>",
        task_id=_TASK_ID,
        depth=depth,
        max_reasoning_kwargs={"thinking_config": {"thinking_level": "high"}},
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestAdvisorCommon:

    def test_case1_happy_path(self, monkeypatch: pytest.MonkeyPatch):
        """Case 1: call_provider returns valid advisor JSON -> status=OK, verdict=PASS, all keys populated."""

        def _mock_call(provider, system, user, **kwargs):
            return _make_response(_VALID_JSON)

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "OK"
        assert result["verdict"] == "PASS"
        assert result["confidence"] == pytest.approx(0.85)
        assert result["nplf"] == {"n": 3.5, "p": 3.2, "l": 3.8, "f": 3.1}
        assert len(result["top_strengths"]) == 3
        assert len(result["top_risks"]) == 3
        assert result["critical_blockers"] == []
        assert result["reasoning_chain"] == "Full reasoning here."
        assert result["tokens"]["in"] == 100
        assert result["tokens"]["out"] == 200
        assert result["cost_usd"] >= 0.0
        assert result["duration_s"] >= 0.0
        assert result["error"] is None
        assert result["advisor"] == "gemini-3.1-pro"
        assert result["label"] == "A"
        assert result["direct_answer_md"] == ""

    def test_case1b_direct_answer_md_survives_public_channel(self, monkeypatch: pytest.MonkeyPatch):
        """Advisor direct_answer_md is parsed and returned separately from private reasoning_chain."""
        payload = {
            "verdict": "REVISE",
            "confidence": 0.74,
            "nplf": {"n": 3.0, "p": 2.8, "l": 3.4, "f": 2.6},
            "top_strengths": ["answers mandate", "cites assumptions", "gives actions"],
            "top_risks": ["missing data", "market risk", "execution risk"],
            "critical_blockers": [],
            "direct_answer_md": "## A. Executive verdict\nReject current portfolio; rebuild around smaller convex names.",
            "reasoning_chain": "Private reasoning here.",
        }

        def _mock_call(provider, system, user, **kwargs):
            return _make_response(json.dumps(payload))

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "OK"
        assert result["direct_answer_md"].startswith("## A. Executive verdict")
        assert result["reasoning_chain"] == "Private reasoning here."

    def test_case2_schema_fail_then_retry_success(self, monkeypatch: pytest.MonkeyPatch):
        """Case 2: first call returns 'not json', second call returns valid JSON -> status=OK, call_count=2."""
        call_log: list[int] = []

        def _mock_call(provider, system, user, **kwargs):
            call_log.append(1)
            if len(call_log) == 1:
                return _make_response("not json at all")
            return _make_response(_VALID_JSON)

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "OK"
        assert result["verdict"] == "PASS"
        assert len(call_log) == 2

    def test_case3_two_schema_fails_schema_fail(self, monkeypatch: pytest.MonkeyPatch):
        """Case 3: both calls return malformed -> status=SCHEMA_FAIL, verdict=ABSTAIN."""
        call_log: list[int] = []

        def _mock_call(provider, system, user, **kwargs):
            call_log.append(1)
            return _make_response("not json at all")

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "SCHEMA_FAIL"
        assert result["verdict"] == "ABSTAIN"
        assert len(call_log) == 2

    def test_case4_transient_retries_then_success(self, monkeypatch: pytest.MonkeyPatch):
        """Case 4: 3 transient errors then 4th call success -> status=OK, exp-backoff sleep called."""
        call_log: list[int] = []
        sleep_calls: list[float] = []

        monkeypatch.setattr(common_mod.time, "sleep", lambda s: sleep_calls.append(s))

        def _mock_call(provider, system, user, **kwargs):
            call_log.append(1)
            if len(call_log) < 4:
                raise TransientProviderError(provider, "timeout")
            return _make_response(_VALID_JSON)

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "OK"
        assert result["verdict"] == "PASS"
        assert len(call_log) == 4
        # 3 transient failures => 3 backoff sleeps: 1, 2, 4
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_case5_all_transient_exhausted(self, monkeypatch: pytest.MonkeyPatch):
        """Case 5: all 4 attempts transient fail -> status=ABSTAIN, error contains 'exhausted'."""
        call_log: list[int] = []

        monkeypatch.setattr(common_mod.time, "sleep", lambda s: None)

        def _mock_call(provider, system, user, **kwargs):
            call_log.append(1)
            raise TransientProviderError(provider, "rate_limit")

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "ABSTAIN"
        assert result["verdict"] == "ABSTAIN"
        assert len(call_log) == 4
        assert "exhausted" in result["error"].lower()

    def test_case6_permanent_error_abstain(self, monkeypatch: pytest.MonkeyPatch):
        """Case 6: PermanentProviderError on first call -> status=ABSTAIN, only 1 attempt made."""
        call_log: list[int] = []

        def _mock_call(provider, system, user, **kwargs):
            call_log.append(1)
            raise PermanentProviderError(provider, "invalid api key")

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "ABSTAIN"
        assert result["verdict"] == "ABSTAIN"
        assert len(call_log) == 1
        assert "invalid api key" in result["error"]

    def test_case7_vk_markers_emitted(self, monkeypatch: pytest.MonkeyPatch, capsys):
        """Case 7: VK markers step=dispatch_A state=entered and state=completed|failed emitted."""

        def _mock_call(provider, system, user, **kwargs):
            return _make_response(_VALID_JSON)

        _run(monkeypatch, _mock_call, label="A")

        captured = capsys.readouterr()
        lines = captured.out.splitlines()

        entered = [l for l in lines if "VK:STEP=dispatch_A" in l and "STATE=entered" in l]
        terminal = [l for l in lines if "VK:STEP=dispatch_A" in l and
                    ("STATE=completed" in l or "STATE=failed" in l)]

        assert len(entered) >= 1, f"No VK entered marker found in: {lines}"
        assert len(terminal) >= 1, f"No VK completed/failed marker found in: {lines}"

    def test_case8_depth_timeout_mapping(self, monkeypatch: pytest.MonkeyPatch):
        """Case 8: depth drives timeout_s -> quick=75, standard=200, deep=400."""
        captured_timeouts: list[float] = []

        def _mock_call(provider, system, user, *, timeout_s: float = 0.0, **kwargs):
            captured_timeouts.append(timeout_s)
            return _make_response(_VALID_JSON)

        monkeypatch.setattr(providers_mod, "call_provider", _mock_call)

        for depth, expected in [("quick", 75.0), ("standard", 200.0), ("deep", 400.0)]:
            captured_timeouts.clear()
            common_mod.run_advisor(
                provider_key="gemini-3.1-pro",
                advisor_label="A",
                brief_xml="<council_brief>brief</council_brief>",
                task_id=_TASK_ID,
                depth=depth,
                max_reasoning_kwargs={},
            )
            assert captured_timeouts[0] == expected, (
                f"depth={depth}: expected timeout_s={expected}, got {captured_timeouts[0]}"
            )


# ---------------------------------------------------------------------------
# FIX-1: schema fail does not consume transient retry budget
# ---------------------------------------------------------------------------

class TestFix1SchemaFailDoesNotEatTransientBudget:

    def test_schema_fail_does_not_eat_transient_budget(self, monkeypatch: pytest.MonkeyPatch):
        """FIX-1: schema_fail on call 1, transient×3 on calls 2-4, success on call 5.
        Pre-fix: attempt counter reaches 4 after schema_fail+3transient → exhausted.
        Post-fix: schema_fail uses its own counter; all 4 transient slots still
        available → succeeds on the 4th transient attempt (5th total call).
        """
        call_log: list[str] = []
        monkeypatch.setattr(common_mod.time, "sleep", lambda s: None)

        def _mock_call(provider, system, user, **kwargs):
            n = len(call_log) + 1
            call_log.append(str(n))
            if n == 1:
                # Schema fail on first call
                return _make_response("not json at all")
            if n < 5:
                # Transient errors on calls 2, 3, 4
                raise TransientProviderError(provider, "timeout")
            # Success on call 5
            return _make_response(_VALID_JSON)

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "OK", f"expected OK, got {result['status']} (error={result['error']})"
        assert result["verdict"] == "PASS"
        assert len(call_log) == 5, f"expected 5 calls, got {len(call_log)}"


# ---------------------------------------------------------------------------
# FIX-2: markdown fence stripper
# ---------------------------------------------------------------------------

class TestFix2MarkdownFenceStripper:

    def test_fence_with_json_lang_tag(self):
        """Input ```json\\n{...}\\n``` -> stripped JSON string."""
        text = '```json\n{"a":1}\n```'
        assert common_mod._strip_markdown_fences(text) == '{"a":1}'

    def test_fence_without_lang_tag(self):
        """Input ```\\n{...}\\n``` (no lang tag) -> stripped JSON string."""
        text = '```\n{"a":1}\n```'
        assert common_mod._strip_markdown_fences(text) == '{"a":1}'

    def test_no_fence_passthrough(self):
        """Input without fences -> returned unchanged (stripped)."""
        text = '{"a":1}'
        assert common_mod._strip_markdown_fences(text) == '{"a":1}'

    def test_fence_missing_closing(self):
        """Input ```json\\n{...} (no closing fence) -> inner content returned."""
        text = '```json\n{"a":1}'
        assert common_mod._strip_markdown_fences(text) == '{"a":1}'

    def test_fence_integration_run_advisor(self, monkeypatch: pytest.MonkeyPatch):
        """Integration: call_provider returns full advisor JSON wrapped in ```json...```.
        run_advisor must parse it correctly and return status=OK.
        """
        fenced = f"```json\n{_VALID_JSON}\n```"

        def _mock_call(provider, system, user, **kwargs):
            return _make_response(fenced)

        result = _run(monkeypatch, _mock_call)
        assert result["status"] == "OK"
        assert result["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# FIX-3: backoff sequence — exactly 3 sleeps (1, 2, 4), no 8.0
# ---------------------------------------------------------------------------

class TestFix3BackoffSequenceMax3Sleeps:

    def test_backoff_sequence_max_3_sleeps(self, monkeypatch: pytest.MonkeyPatch):
        """FIX-3: 4 transient errors → exactly 3 sleeps with values [1.0, 2.0, 4.0].
        No 8.0 sleep. Final status is ABSTAIN with error containing 'exhausted'.
        """
        sleep_calls: list[float] = []
        monkeypatch.setattr(common_mod.time, "sleep", lambda s: sleep_calls.append(s))

        def _mock_call(provider, system, user, **kwargs):
            raise TransientProviderError(provider, "timeout")

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "ABSTAIN"
        assert "exhausted" in result["error"].lower()
        assert sleep_calls == [1.0, 2.0, 4.0], (
            f"expected [1.0, 2.0, 4.0] sleeps, got {sleep_calls}"
        )
        assert 8.0 not in sleep_calls


# ---------------------------------------------------------------------------
# FIX-4: schema retry accumulates tokens + cost
# ---------------------------------------------------------------------------

class TestFix4SchemaRetryAccumulatesCost:

    def test_schema_retry_accumulates_cost(self, monkeypatch: pytest.MonkeyPatch):
        """FIX-4: schema fail on call 1 (1000 in, 500 out), success on call 2 (800 in, 400 out).
        Returned tokens must be sum: in=1800, out=900. cost_usd must reflect both calls.
        """
        call_log: list[int] = []

        def _mock_call(provider, system, user, **kwargs):
            call_log.append(1)
            if len(call_log) == 1:
                return _make_response("not json at all", tokens_in=1000, tokens_out=500)
            return _make_response(_VALID_JSON, tokens_in=800, tokens_out=400)

        result = _run(monkeypatch, _mock_call)

        assert result["status"] == "OK"
        assert result["tokens"] == {"in": 1800, "out": 900}, (
            f"expected tokens={{in:1800, out:900}}, got {result['tokens']}"
        )
        # cost_usd must be positive and reflect both calls (price_in/out non-zero for gemini-3.1-pro)
        assert result["cost_usd"] > 0.0, "cost_usd should be non-zero when tokens > 0"
        # Verify two calls were made
        assert len(call_log) == 2
