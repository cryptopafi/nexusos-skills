"""
test_normalize.py -- 12 pytest cases for lib/normalize.py.

All tests use monkeypatch on lib._providers.call_provider.
No live API calls are made.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

import lib.normalize as normalize_mod
from lib.normalize import normalize
from lib._providers import PermanentProviderError, TransientProviderError
from lib.runtime import support_provider_key


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TASK_ID = "council-20260519-0001-test"

_VALID_XML = """\
<council_brief>
  <goal>Decide whether to expand operations to the EU market.</goal>
  <context>The company currently operates in North America with $10M ARR.</context>
  <constraints>
    <constraint>Budget cap of $500K for expansion.</constraint>
  </constraints>
  <prior_art>
    <item>Previous LATAM expansion succeeded in 18 months.</item>
  </prior_art>
  <decision_points>
    <point>Which EU country to enter first.</point>
  </decision_points>
  <success_criteria>
    <criterion>Achieve 100 paying customers in 12 months.</criterion>
  </success_criteria>
  <stakes>$500K irreversible spend; regulatory compliance risk; 18-month commitment.</stakes>
</council_brief>"""

_VALID_RESPONSE = {
    "text": _VALID_XML,
    "tokens": {"in": 120, "out": 80},
}

_RAW_TARGET = "We need to decide whether to expand our SaaS business to the EU market this year."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(xml_text: str = _VALID_XML, tokens_in: int = 120, tokens_out: int = 80) -> dict:
    return {"text": xml_text, "tokens": {"in": tokens_in, "out": tokens_out}}


def _always_returns(response: dict):
    def _fake(provider, system, user, **kwargs):
        return response
    return _fake


def _raises_permanent(provider_val: str | None = None):
    def _fake(provider, system, user, **kwargs):
        p = provider_val or provider
        raise PermanentProviderError(p, "auth: 401 Unauthorized")
    return _fake


def _raises_transient(provider_val: str | None = None):
    def _fake(provider, system, user, **kwargs):
        p = provider_val or provider
        raise TransientProviderError(p, "timeout: connection timed out")
    return _fake


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestNormalize:

    # Case 1: Happy path runtime support provider
    def test_case1_happy_path_gpt55(self, monkeypatch: pytest.MonkeyPatch):
        """Support provider returns valid XML -> verdict=OK, provider_used=support provider, chain has 1 success."""
        monkeypatch.setattr(normalize_mod, "call_provider", _always_returns(_VALID_RESPONSE))
        result = normalize(_RAW_TARGET, task_id=_TASK_ID)
        expected_provider = support_provider_key()

        assert result["verdict"] == "OK"
        assert result["provider_used"] == expected_provider
        assert len(result["provider_chain"]) == 1
        assert result["provider_chain"][0] == (expected_provider, "success", None)
        assert result["brief_xml"] == _VALID_XML
        assert result["tokens"]["in"] == 120
        assert result["tokens"]["out"] == 80
        assert result["cost_usd"] > 0.0

    # Case 2: legacy fallback removed; support provider succeeds directly
    def test_case2_gpt55_direct_success(self, monkeypatch: pytest.MonkeyPatch):
        """Support routing uses runtime provider directly, not legacy fallbacks."""
        call_log: list[str] = []

        def _selective(provider, system, user, **kwargs):
            call_log.append(provider)
            return _VALID_RESPONSE

        monkeypatch.setattr(normalize_mod, "call_provider", _selective)
        result = normalize(_RAW_TARGET, task_id=_TASK_ID)
        expected_provider = support_provider_key()

        assert result["verdict"] == "OK"
        assert result["provider_used"] == expected_provider
        assert call_log == [expected_provider]
        assert result["provider_chain"] == [(expected_provider, "success", None)]

    # Case 3: support provider transient retry succeeds
    def test_case3_gpt55_transient_retry_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        """Support provider transient error retries before succeeding."""
        call_log: list[str] = []

        def _selective(provider, system, user, **kwargs):
            call_log.append(provider)
            if len(call_log) < 3:
                raise TransientProviderError(provider, "timeout")
            return _VALID_RESPONSE

        monkeypatch.setattr(normalize_mod, "call_provider", _selective)
        monkeypatch.setattr(normalize_mod.time, "sleep", lambda s: None)

        result = normalize(_RAW_TARGET, task_id=_TASK_ID)
        expected_provider = support_provider_key()

        assert result["verdict"] == "OK"
        assert result["provider_used"] == expected_provider
        assert call_log == [expected_provider, expected_provider, expected_provider]

    # Case 4: support provider is the only normalizer provider
    def test_case4_no_gemini_fallback(self, monkeypatch: pytest.MonkeyPatch):
        """Gemini is not used as a support fallback."""
        def _selective(provider, system, user, **kwargs):
            return _VALID_RESPONSE

        monkeypatch.setattr(normalize_mod, "call_provider", _selective)
        result = normalize(_RAW_TARGET, task_id=_TASK_ID)

        assert result["verdict"] == "OK"
        assert result["provider_used"] == support_provider_key()
        assert len(result["provider_chain"]) == 1

    # Case 5: All three fail
    def test_case5_all_providers_fail(self, monkeypatch: pytest.MonkeyPatch):
        """All providers raise PermanentProviderError -> FAIL_ALL_PROVIDERS."""
        monkeypatch.setattr(normalize_mod, "call_provider", _raises_permanent())
        result = normalize(_RAW_TARGET, task_id=_TASK_ID)

        assert result["verdict"] == "FAIL_ALL_PROVIDERS"
        assert result["brief_xml"] is None
        assert "NORMALIZER_UNAVAILABLE" in result["reason"]
        assert len(result["provider_chain"]) == 1
        for entry in result["provider_chain"]:
            assert entry[1] == "fail"

    # Case 6: Target as file path
    def test_case6_target_as_file_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """normalize('/tmp/test.md', ...) reads file content and calls provider."""
        target_file = tmp_path / "test-target.md"
        target_file.write_text("Decide whether to open a new office in Berlin.", encoding="utf-8")

        received_user: list[str] = []

        def _capture(provider, system, user, **kwargs):
            received_user.append(user)
            return _VALID_RESPONSE

        monkeypatch.setattr(normalize_mod, "call_provider", _capture)
        result = normalize(str(target_file), task_id=_TASK_ID)

        assert result["verdict"] == "OK"
        assert len(received_user) == 1
        assert "Berlin" in received_user[0]

    # Case 7: Target as raw text
    def test_case7_target_as_raw_text(self, monkeypatch: pytest.MonkeyPatch):
        """normalize('raw text...', ...) passes string directly."""
        raw = "This is a business proposal about expanding to EU markets next year."
        received_user: list[str] = []

        def _capture(provider, system, user, **kwargs):
            received_user.append(user)
            return _VALID_RESPONSE

        monkeypatch.setattr(normalize_mod, "call_provider", _capture)
        result = normalize(raw, task_id=_TASK_ID)

        assert result["verdict"] == "OK"
        assert len(received_user) == 1
        assert received_user[0] == raw

    # Case 8: Empty target raises ValueError
    def test_case8_empty_target_raises(self):
        """normalize('', ...) raises ValueError."""
        with pytest.raises(ValueError):
            normalize("", task_id=_TASK_ID)

    # Case 9: Unreadable file path raises ValueError
    def test_case9_nonexistent_file_raises(self):
        """normalize('/nonexistent/file.md', ...) raises ValueError mentioning the file."""
        with pytest.raises(ValueError, match="file path does not exist"):
            normalize("/nonexistent/file.md", task_id=_TASK_ID)

    # Case 10: Provider returns invalid XML -> schema fail
    def test_case10_invalid_xml_fails_gpt55(self, monkeypatch: pytest.MonkeyPatch):
        """GPT-5.5 returns invalid XML -> FAIL_ALL_PROVIDERS."""
        def _selective(provider, system, user, **kwargs):
            return {"text": "not xml at all", "tokens": {"in": 50, "out": 10}}

        monkeypatch.setattr(normalize_mod, "call_provider", _selective)
        result = normalize(_RAW_TARGET, task_id=_TASK_ID)

        assert result["verdict"] == "FAIL_ALL_PROVIDERS"
        assert result["provider_chain"][0][1] == "fail"
        assert "schema" in (result["provider_chain"][0][2] or "")

    # Case 11: VK markers emitted
    def test_case11_vk_markers_emitted(self, monkeypatch: pytest.MonkeyPatch, capsys):
        """VK:STEP=normalize STATE=entered and STATE=completed|failed emitted exactly once each."""
        monkeypatch.setattr(normalize_mod, "call_provider", _always_returns(_VALID_RESPONSE))
        normalize(_RAW_TARGET, task_id=_TASK_ID)

        captured = capsys.readouterr()
        lines = captured.out.splitlines()

        entered_lines = [l for l in lines if "VK:STEP=normalize" in l and "STATE=entered" in l]
        terminal_lines = [
            l for l in lines
            if "VK:STEP=normalize" in l and ("STATE=completed" in l or "STATE=failed" in l)
        ]

        assert len(entered_lines) == 1, f"Expected exactly 1 VK entered; got: {entered_lines}"
        assert len(terminal_lines) == 1, f"Expected exactly 1 VK terminal; got: {terminal_lines}"

    # Case 12: Exponential backoff timing
    def test_case12_exp_backoff_timing(self, monkeypatch: pytest.MonkeyPatch):
        """Transient errors trigger sleep(1) then sleep(2) between attempts."""
        sleep_calls: list[float] = []

        def _fake_sleep(s: float) -> None:
            sleep_calls.append(s)

        def _always_transient(provider, system, user, **kwargs):
            raise TransientProviderError(provider, "timeout")

        monkeypatch.setattr(normalize_mod.time, "sleep", _fake_sleep)
        monkeypatch.setattr(normalize_mod, "call_provider", _always_transient)

        result = normalize(_RAW_TARGET, task_id=_TASK_ID)

        # All 3 providers x 3 attempts each, but sleep only between attempts (not after last)
        # Per provider: attempt0->sleep(1), attempt1->sleep(2), attempt2->no sleep
        # 3 providers * 2 sleeps each = 6 sleeps total
        assert 1.0 in sleep_calls, f"Expected sleep(1) in calls: {sleep_calls}"
        assert 2.0 in sleep_calls, f"Expected sleep(2) in calls: {sleep_calls}"
        # Verify ordering: first sleep per provider is 1.0, second is 2.0
        one_idx = sleep_calls.index(1.0)
        two_idx = sleep_calls.index(2.0)
        assert one_idx < two_idx

        assert result["verdict"] == "FAIL_ALL_PROVIDERS"
