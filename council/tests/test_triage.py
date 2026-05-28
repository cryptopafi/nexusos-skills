"""
test_triage.py -- 10 pytest cases for lib/triage.py.

All tests use monkeypatch on the legacy lib.triage._call_haiku provider boundary
to avoid live GPT-5.5/Codex OAuth calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

import lib.triage as triage_mod
from lib.triage import triage, _TransientError, _PermanentError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TASK_ID = "council-20260519-0000-test"

def _axes_response(reversibility, blast_radius, cost_of_error, normative_vs_technical, evidence_availability, reason="Test reason."):
    total = reversibility + blast_radius + cost_of_error + normative_vs_technical + evidence_availability
    content = (
        f'{{"reversibility": {reversibility}, "blast_radius": {blast_radius}, '
        f'"cost_of_error": {cost_of_error}, "normative_vs_technical": {normative_vs_technical}, '
        f'"evidence_availability": {evidence_availability}, "reason": "{reason}"}}'
    )
    return {"content": content, "tokens_in": 50, "tokens_out": 30}


def _mock_call(response: dict):
    """Returns a function that always returns the given response dict."""
    def _fake(system_prompt, user_prompt):
        return response
    return _fake


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestTriage:

    def test_case1_low_score_refuse(self, monkeypatch: pytest.MonkeyPatch, capsys):
        """Case 1: sum=12, below threshold=40 -> verdict=REFUSE, reason mentions 'below threshold'."""
        # 3+2+2+2+3 = 12
        monkeypatch.setattr(triage_mod, "_call_haiku", _mock_call(
            _axes_response(3, 2, 2, 2, 3, "Trivial rename.")
        ))
        result = triage("simple naming rename foo->bar", threshold=40, task_id=_TASK_ID)
        assert result["verdict"] == "REFUSE"
        assert "below threshold" in result["reason"].lower()
        assert result["score"] == 12

    def test_case2_high_score_proceed(self, monkeypatch: pytest.MonkeyPatch):
        """Case 2: sum=72, above threshold=40 -> verdict=PROCEED, axes filled."""
        # 15+14+13+15+15 = 72
        monkeypatch.setattr(triage_mod, "_call_haiku", _mock_call(
            _axes_response(15, 14, 13, 15, 15, "Major budget decision.")
        ))
        result = triage("EU expansion 100K budget decision", threshold=40, task_id=_TASK_ID)
        assert result["verdict"] == "PROCEED"
        assert result["score"] == 72
        assert set(result["axes"].keys()) == {"reversibility", "blast_radius", "cost_of_error", "normative_vs_technical", "evidence_availability"}

    def test_case3_force_overrides_low_score(self, monkeypatch: pytest.MonkeyPatch):
        """Case 3: force=True with sum=12 -> verdict=PROCEED_FORCED."""
        monkeypatch.setattr(triage_mod, "_call_haiku", _mock_call(
            _axes_response(3, 2, 2, 2, 3, "Trivial rename.")
        ))
        result = triage("simple rename", threshold=40, force=True, task_id=_TASK_ID)
        assert result["verdict"] == "PROCEED_FORCED"

    def test_case4_permanent_error_refuse(self, monkeypatch: pytest.MonkeyPatch):
        """Case 4: permanent 4xx error -> verdict=REFUSE, reason starts with 'TRIAGE_UNAVAILABLE'."""
        def _raise_permanent(system_prompt, user_prompt):
            raise _PermanentError("api_error_400: Bad request")
        monkeypatch.setattr(triage_mod, "_call_haiku", _raise_permanent)
        result = triage("some decision", task_id=_TASK_ID)
        assert result["verdict"] == "REFUSE"
        assert result["reason"].startswith("TRIAGE_UNAVAILABLE")

    def test_case5_permanent_error_with_force(self, monkeypatch: pytest.MonkeyPatch):
        """Case 5: permanent error + force=True -> verdict=PROCEED_FORCED, reason contains 'TRIAGE_BYPASSED'."""
        def _raise_permanent(system_prompt, user_prompt):
            raise _PermanentError("api_error_400: Bad request")
        monkeypatch.setattr(triage_mod, "_call_haiku", _raise_permanent)
        result = triage("some decision", force=True, task_id=_TASK_ID)
        assert result["verdict"] == "PROCEED_FORCED"
        assert "TRIAGE_BYPASSED" in result["reason"]

    def test_case6_transient_retries_then_success(self, monkeypatch: pytest.MonkeyPatch):
        """Case 6: 2 transient failures then success -> support_call_count=1, verdict from mocked sum."""
        call_log = []

        def _flaky(system_prompt, user_prompt):
            call_log.append(1)
            if len(call_log) < 3:
                raise _TransientError("timeout on attempt")
            # 3rd call succeeds: 15+14+13+15+15 = 72
            return _axes_response(15, 14, 13, 15, 15, "Success on third attempt.")

        monkeypatch.setattr(triage_mod, "_call_haiku", _flaky)
        # Patch sleep to avoid real delays in tests
        monkeypatch.setattr(triage_mod.time, "sleep", lambda s: None)
        result = triage("some decision", threshold=40, task_id=_TASK_ID)
        assert result["support_call_count"] == 1
        assert result["haiku_call_count"] == 1
        assert result["verdict"] == "PROCEED"
        assert result["score"] == 72

    def test_case7_malformed_json_schema_error(self, monkeypatch: pytest.MonkeyPatch):
        """Case 7: support model returns 'not json' -> verdict=REFUSE, reason contains 'schema'."""
        monkeypatch.setattr(triage_mod, "_call_haiku", _mock_call(
            {"content": "not json at all", "tokens_in": 50, "tokens_out": 5}
        ))
        result = triage("some decision", task_id=_TASK_ID)
        assert result["verdict"] == "REFUSE"
        assert "schema" in result["reason"].lower()

    def test_case8_empty_target_raises_value_error(self):
        """Case 8: empty target_text -> raises ValueError."""
        with pytest.raises(ValueError):
            triage("", task_id=_TASK_ID)

    def test_case9_threshold_out_of_bounds_raises(self):
        """Case 9: threshold=-1 or threshold=101 -> raises ValueError."""
        with pytest.raises(ValueError):
            triage("some text", threshold=-1, task_id=_TASK_ID)
        with pytest.raises(ValueError):
            triage("some text", threshold=101, task_id=_TASK_ID)

    def test_missing_support_credentials_fail_closed(self, monkeypatch: pytest.MonkeyPatch):
        """Fail-closed: missing runtime support-provider credentials -> verdict=REFUSE."""
        def _raise_missing(system_prompt, user_prompt):
            raise _PermanentError("support provider credentials unavailable")

        monkeypatch.setattr(triage_mod, "_call_haiku", _raise_missing)
        result = triage("real target text that is not empty", task_id=_TASK_ID)
        assert result["verdict"] == "REFUSE"
        assert "TRIAGE_UNAVAILABLE" in result["reason"]

    def test_whitespace_only_target_raises(self):
        """FIX-4: whitespace-only target_text -> raises ValueError."""
        with pytest.raises(ValueError):
            triage("   ", task_id=_TASK_ID)

    def test_case10_vk_markers_emitted(self, monkeypatch: pytest.MonkeyPatch, capsys):
        """Case 10: VK markers for entered and completed|failed are both emitted to stdout."""
        monkeypatch.setattr(triage_mod, "_call_haiku", _mock_call(
            _axes_response(15, 14, 13, 15, 15, "High-stakes decision.")
        ))
        triage("EU expansion", threshold=40, task_id=_TASK_ID)
        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        entered_lines = [l for l in lines if "VK:STEP=triage" in l and "STATE=entered" in l]
        terminal_lines = [l for l in lines if "VK:STEP=triage" in l and ("STATE=completed" in l or "STATE=failed" in l)]
        assert len(entered_lines) >= 1, f"No VK entered marker found in: {lines}"
        assert len(terminal_lines) >= 1, f"No VK completed/failed marker found in: {lines}"
