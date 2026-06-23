"""
test_v101_fixes.py — New tests for v1.0.1 audit fix batch.

Covers all 2 CRITICAL + 6 HIGH + relevant MEDIUM fixes:
  FIX-C1  test_orchestrator_aligns_advisors_to_anonymized_for_debate
  FIX-C2  test_ledger_emits_vk_markers
  FIX-H1  test_nplf_arithmetic_excludes_abstain
  FIX-H2  test_vendor_diversity_enforced
  FIX-H3  test_force_test_exempts_daily_ceiling
  FIX-H4  test_ac12_catches_value_leak
  FIX-H5  test_validator_probes_actual_chains
  FIX-M1  test_minimal_anon_fallback_strict_allowlist
  FIX-M5  (covered via FIX-H3 infrastructure; no dedicated test needed)

All tests are pure-unit with no live API calls.
"""

from __future__ import annotations

import json
import pathlib
import sys
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixture builders shared across tests
# ---------------------------------------------------------------------------

def _make_advisor(
    label: str = "A",
    provider_key: str = "gemini-3.1-pro",
    verdict: str = "PASS",
    confidence: float = 0.85,
    reasoning_chain: str = "",
    nplf: dict | None = None,
) -> dict:
    return {
        "label": label,
        "advisor": provider_key,
        "verdict": verdict,
        "confidence": confidence,
        "nplf": nplf or {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
        "top_strengths": ["Strength 1"],
        "top_risks": ["Risk 1"],
        "critical_blockers": [],
        "verdict_md": f"## Verdict\n{verdict}",
        "reasoning_chain": reasoning_chain,
        "tokens": {"in": 100, "out": 50},
        "cost_usd": 0.01,
        "duration_s": 0.5,
        "status": "OK",
        "error": None,
        "provider_key": provider_key,
    }


def _make_anon(letter: str, verdict: str = "PASS", confidence: float = 0.85,
               nplf: dict | None = None) -> dict:
    return {
        "letter": letter,
        "verdict": verdict,
        "confidence": confidence,
        "nplf": nplf or {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
        "top_strengths": [f"Strength {letter}1"],
        "top_risks": [f"Risk {letter}1"],
        "critical_blockers": [],
    }


# ===========================================================================
# FIX-C1: Orchestrator aligns advisor_results to anonymized order for debate
# ===========================================================================

class TestFIXC1DebateAlignment:
    """
    When anonymize returns a shuffled order (e.g. shuffle_map={"A":"label_2",...}),
    the orchestrator must re-align advisor_results before passing to run_debate,
    so original_advisors[i].label == shuffle_map[anonymized[i].letter].
    """

    def test_orchestrator_aligns_advisors_to_anonymized_for_debate(self, monkeypatch):
        """
        Scenario: anonymize shuffles so that anonymous letter A corresponds to
        the third advisor (label_2 = advisor_gpt / "C"). The debate spy asserts
        original_advisors[0] (the advisor paired with anonymous letter A) is the
        GPT advisor — not the Gemini advisor that was first in call order.
        """
        import pathlib as _pl
        from lib import orchestrator

        # Advisor results in call order: [gemini=label_0, opus=label_1, gpt=label_2]
        gemini_result = _make_advisor("label_0", "gemini-3.1-pro", reasoning_chain="gemini-chain")
        opus_result   = _make_advisor("label_1", "opus-4-8",       reasoning_chain="opus-chain")
        gpt_result    = _make_advisor("label_2", "gpt-5.5",        reasoning_chain="gpt-chain")

        # Anonymize shuffles: A → label_2 (gpt), B → label_0 (gemini), C → label_1 (opus)
        shuffle_map = {"A": "label_2", "B": "label_0", "C": "label_1"}
        anon_list = [
            _make_anon("A"),  # corresponds to label_2 (gpt)
            _make_anon("B"),  # corresponds to label_0 (gemini)
            _make_anon("C"),  # corresponds to label_1 (opus)
        ]

        captured_original_advisors: list[list[dict]] = []

        def _fake_debate(**kw):
            captured_original_advisors.append(kw["original_advisors"])
            return {
                "run1": [], "run2": [],
                "instability_detected": False,
                "instability_reasons": [],
                "drift_metrics": [],
                "tier_downgrade_recommended": False,
                "tokens": {"in": 0, "out": 0},
                "cost_usd": 0.0,
                "duration_s": 0.1,
                "status": "OK",
                "error": None,
            }

        monkeypatch.setattr("lib.triage.triage", lambda *a, **kw: {
            "verdict": "PROCEED", "score": 75, "reason": "ok",
            "haiku_call_count": 1, "haiku_tokens": {"in": 100, "out": 50},
        })
        monkeypatch.setattr("lib.normalize.normalize", lambda *a, **kw: {
            "verdict": "OK",
            "brief_xml": "<council_brief><goal>test</goal></council_brief>",
            "provider_used": "sonnet-4-6",
            "tokens": {"in": 100, "out": 50},
            "cost_usd": 0.001,
            "duration_s": 0.1,
            "error": None,
        })
        monkeypatch.setattr("lib.advisor_gemini.advise", lambda *a, **kw: gemini_result)
        monkeypatch.setattr("lib.advisor_opus.advise",   lambda *a, **kw: opus_result)
        monkeypatch.setattr("lib.advisor_gpt.advise",    lambda *a, **kw: gpt_result)
        monkeypatch.setattr("lib.anonymize.anonymize", lambda *a, **kw: {
            "anonymized": anon_list,
            "shuffle_map": shuffle_map,
            "seed": 99,
            "cost_usd": 0.001,
        })
        monkeypatch.setattr("lib.reconcile.reconcile", lambda *a, **kw: {
            "tier": "PASS",
            "verdict_md": "## Agreement Zones\nAll agreed (Response A, Response B).\n## Split Zones\nNone.",
            "dissent_md": "",
            "confidence": 0.87,
            "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
            "nplf_arithmetic": {"advisor_means": [3.5, 3.5, 3.5],
                                "cross_advisor_mean": 3.5,
                                "reconciler_nplf_mean": 3.5,
                                "tier_gate_value": 3.5},
            "agreement_zones": [], "split_zones": [],
            "tokens": {"in": 200, "out": 100},
            "cost_usd": 0.05, "duration_s": 1.0,
            "status": "OK", "error": None,
            "shuffle_map": shuffle_map, "verdict_drift": None,
        })
        monkeypatch.setattr("lib.debate.run_debate", _fake_debate)
        monkeypatch.setattr("lib.ledger.write_ledger", lambda **kw: {
            "workspace_dir": "/tmp/test",
            "files_written": [],
            "cortex_id": None,
            "notion_url": None,
            "telegram_sent": False,
            "privacy_audit": {"chain_in_local": False, "chain_in_cortex": False,
                              "chain_in_notion": False, "ac12_grep_clean": True},
            "status": "OK",
            "errors": {},
        })
        monkeypatch.setattr("lib.cost_meter.CostMeter.commit_to_daily_ledger", lambda self: None)

        result = orchestrator.run_council("A brief about business strategy.", depth="deep")

        assert result["status"] == "OK", f"Expected OK got {result['status']}: {result.get('error')}"
        assert len(captured_original_advisors) == 1, "debate should have been called once"

        passed_advisors = captured_original_advisors[0]
        # anonymized[0].letter = "A" → shuffle_map["A"] = "label_2" (gpt)
        # So passed_advisors[0] must be the gpt result (label == "label_2")
        assert passed_advisors[0]["label"] == "label_2", (
            f"FIX-C1 FAIL: expected label_2 (gpt) as aligned advisor[0], "
            f"got {passed_advisors[0].get('label')!r}. Shuffle alignment is broken."
        )
        # anonymized[1].letter = "B" → shuffle_map["B"] = "label_0" (gemini)
        assert passed_advisors[1]["label"] == "label_0", (
            f"FIX-C1 FAIL: expected label_0 (gemini) as aligned advisor[1], "
            f"got {passed_advisors[1].get('label')!r}."
        )


# ===========================================================================
# FIX-C2: Ledger emits VK markers at enter + complete/fail
# ===========================================================================

class TestFIXC2LedgerVKMarkers:
    """
    write_ledger() must emit VK:STEP=ledger STATE=entered at entry and
    VK:STEP=ledger STATE=completed (or failed) at every exit path.
    """

    def _make_full_advisor_results(self) -> list[dict]:
        return [
            _make_advisor("A", "gemini-3.1-pro"),
            _make_advisor("B", "opus-4-8"),
            _make_advisor("C", "gpt-5.5"),
        ]

    def _make_reconciler(self) -> dict:
        return {
            "tier": "PASS",
            "verdict_md": "## Agreement Zones\nAll agreed (Response A).\n## Split Zones\nNone.",
            "dissent_md": "",
            "confidence": 0.87,
        }

    def test_ledger_emits_vk_markers(self, tmp_path, monkeypatch, capsys):
        """write_ledger() must emit entered + completed VK markers on success."""
        from lib.ledger import write_ledger
        import lib.ledger as ledger_mod

        # Patch remote sinks to be no-ops
        monkeypatch.setattr(ledger_mod, "_write_cortex",
                            lambda *a, **kw: (None, "skipped"))
        monkeypatch.setattr(ledger_mod, "_send_telegram",
                            lambda *a, **kw: (False, "skipped"))
        monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)

        result = write_ledger(
            task_id="vk-test-001",
            council_task_id="vk-test-001",
            brief_xml="<council_brief><goal>test</goal></council_brief>",
            advisor_results=self._make_full_advisor_results(),
            anonymized=[_make_anon("A"), _make_anon("B"), _make_anon("C")],
            shuffle_map={"A": 0, "B": 1, "C": 2},
            seed=42,
            reconciler_result=self._make_reconciler(),
            debate_result=None,
            cost_meter_total=0.10,
            keep_chains=False,
        )

        captured = capsys.readouterr().out
        assert "VK:STEP=ledger STATE=entered" in captured, (
            f"FIX-C2 FAIL: 'entered' VK marker missing. stdout was:\n{captured}"
        )
        assert "VK:STEP=ledger STATE=completed" in captured, (
            f"FIX-C2 FAIL: 'completed' VK marker missing. stdout was:\n{captured}"
        )

    def test_ledger_emits_vk_failed_on_ac12_leak(self, tmp_path, monkeypatch, capsys):
        """write_ledger() must emit entered + failed VK markers on AC-12 grep fail."""
        from lib.ledger import write_ledger
        import lib.ledger as ledger_mod

        monkeypatch.setattr(ledger_mod, "_write_cortex",
                            lambda *a, **kw: (None, "skipped"))
        monkeypatch.setattr(ledger_mod, "_send_telegram",
                            lambda *a, **kw: (False, "skipped"))
        monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
        # Force AC-12 to fail
        monkeypatch.setattr(ledger_mod, "_ac12_grep_check", lambda *a, **kw: False)

        write_ledger(
            task_id="vk-fail-001",
            council_task_id="vk-fail-001",
            brief_xml="<council_brief><goal>test</goal></council_brief>",
            advisor_results=self._make_full_advisor_results(),
            anonymized=[_make_anon("A"), _make_anon("B"), _make_anon("C")],
            shuffle_map={"A": 0, "B": 1, "C": 2},
            seed=42,
            reconciler_result=self._make_reconciler(),
            debate_result=None,
            cost_meter_total=0.10,
            keep_chains=False,
        )

        captured = capsys.readouterr().out
        assert "VK:STEP=ledger STATE=entered" in captured, \
            "FIX-C2 FAIL: 'entered' VK marker missing on AC-12 fail path"
        assert "VK:STEP=ledger STATE=failed" in captured, (
            f"FIX-C2 FAIL: 'failed' VK marker missing on AC-12 fail path. stdout:\n{captured}"
        )


# ===========================================================================
# FIX-H1: NPLF arithmetic excludes ABSTAIN advisors
# ===========================================================================

class TestFIXH1NPLFArithmeticExcludesAbstain:
    """
    _compute_nplf_arithmetic must skip ABSTAIN advisors.
    With 2 PASS advisors (NPLF=3.5) + 1 ABSTAIN (NPLF=0.0) and reconciler
    NPLF=3.6, cross_mean must be 3.5 (not 2.33 which includes the abstain 0.0).
    """

    def test_nplf_arithmetic_excludes_abstain(self):
        from lib.reconcile import _compute_nplf_arithmetic

        nplf_pass = {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5}
        nplf_zero = {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0}
        reconciler_nplf = {"n": 3.6, "p": 3.6, "l": 3.6, "f": 3.6}

        anonymized = [
            {"letter": "A", "verdict": "PASS",    "nplf": nplf_pass},
            {"letter": "B", "verdict": "PASS",    "nplf": nplf_pass},
            {"letter": "C", "verdict": "ABSTAIN", "nplf": nplf_zero},
        ]

        result = _compute_nplf_arithmetic(anonymized, reconciler_nplf)

        # Bug (pre-fix): (3.5 + 3.5 + 0.0) / 3 = 2.33 → gate fails 3.0
        # Fixed:         (3.5 + 3.5) / 2 = 3.5 → gate passes 3.0
        assert abs(result["cross_advisor_mean"] - 3.5) < 0.01, (
            f"FIX-H1 FAIL: cross_advisor_mean={result['cross_advisor_mean']:.4f}, "
            f"expected 3.5. ABSTAIN is being included in mean."
        )
        assert abs(result["tier_gate_value"] - 3.5) < 0.01, (
            f"FIX-H1 FAIL: tier_gate_value={result['tier_gate_value']:.4f}, expected 3.5"
        )
        # advisor_means should contain exactly 2 entries (not 3)
        assert len(result["advisor_means"]) == 2, (
            f"FIX-H1 FAIL: advisor_means has {len(result['advisor_means'])} entries, "
            f"expected 2 (ABSTAIN must be excluded)"
        )

    def test_nplf_arithmetic_all_abstain_defensive_fallback(self):
        """All-ABSTAIN edge case: cross_mean falls back to 0.0 without ZeroDivisionError."""
        from lib.reconcile import _compute_nplf_arithmetic

        anonymized = [
            {"letter": "A", "verdict": "ABSTAIN", "nplf": {}},
            {"letter": "B", "verdict": "ABSTAIN", "nplf": {}},
            {"letter": "C", "verdict": "ABSTAIN", "nplf": {}},
        ]
        reconciler_nplf = {"n": 2.0, "p": 2.0, "l": 2.0, "f": 2.0}

        result = _compute_nplf_arithmetic(anonymized, reconciler_nplf)
        assert result["cross_advisor_mean"] == 0.0
        assert result["advisor_means"] == []


# ===========================================================================
# FIX-H2: 3-vendor diversity enforced at run_council() entry
# ===========================================================================

class TestFIXH2VendorDiversityEnforced:
    """
    run_council() must raise RuntimeError if fewer than 3 unique vendors
    are present across the 3 advisor PROVIDER_KEYs.
    """

    def test_vendor_diversity_enforced(self, monkeypatch):
        """Patch PROVIDER_REGISTRY so all 3 advisors share 'anthropic' vendor → RuntimeError."""
        from lib import orchestrator
        from lib import _providers

        # Make all 3 advisor PROVIDER_KEYs map to vendor="anthropic"
        fake_registry = dict(_providers.PROVIDER_REGISTRY)
        fake_registry["ollama-glm-5.2-cloud"] = {**fake_registry.get("ollama-glm-5.2-cloud", {}),
                                                  "vendor": "anthropic"}
        fake_registry["gpt-5.5"] = {**fake_registry.get("gpt-5.5", {}),
                                    "vendor": "anthropic"}
        # opus-4-8 is already anthropic

        monkeypatch.setattr(_providers, "PROVIDER_REGISTRY", fake_registry)

        with pytest.raises(RuntimeError, match="3 different vendors"):
            orchestrator.run_council("Some brief text", depth="standard")

    def test_vendor_diversity_passes_with_3_vendors(self, monkeypatch):
        """Default config has ollama + anthropic + openai — must not raise."""
        from lib import orchestrator

        # Use happy-path mocks so the pipeline completes without API calls
        monkeypatch.setattr("lib.triage.triage", lambda *a, **kw: {
            "verdict": "PROCEED", "score": 75, "reason": "ok",
            "haiku_call_count": 1, "haiku_tokens": {"in": 100, "out": 50},
        })
        monkeypatch.setattr("lib.normalize.normalize", lambda *a, **kw: {
            "verdict": "OK",
            "brief_xml": "<council_brief><goal>g</goal></council_brief>",
            "provider_used": "sonnet-4-6",
            "tokens": {"in": 100, "out": 50}, "cost_usd": 0.001,
            "duration_s": 0.1, "error": None,
        })
        monkeypatch.setattr("lib.advisor_gemini.advise",
                            lambda *a, **kw: _make_advisor("A", "ollama-glm-5.2-cloud"))
        monkeypatch.setattr("lib.advisor_opus.advise",
                            lambda *a, **kw: _make_advisor("B", "opus-4-8"))
        monkeypatch.setattr("lib.advisor_gpt.advise",
                            lambda *a, **kw: _make_advisor("C", "gpt-5.5"))
        monkeypatch.setattr("lib.anonymize.anonymize", lambda *a, **kw: {
            "anonymized": [_make_anon("A"), _make_anon("B"), _make_anon("C")],
            "shuffle_map": {"A": 0, "B": 1, "C": 2},
            "seed": 42, "cost_usd": 0.001,
        })
        monkeypatch.setattr("lib.reconcile.reconcile", lambda *a, **kw: {
            "tier": "PASS",
            "verdict_md": "## Agreement Zones\nAll (Response A).\n## Split Zones\nNone.",
            "dissent_md": "", "confidence": 0.87,
            "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
            "nplf_arithmetic": {"advisor_means": [3.5, 3.5, 3.5],
                                "cross_advisor_mean": 3.5,
                                "reconciler_nplf_mean": 3.5,
                                "tier_gate_value": 3.5},
            "agreement_zones": [], "split_zones": [],
            "tokens": {"in": 200, "out": 100},
            "cost_usd": 0.05, "duration_s": 1.0,
            "status": "OK", "error": None,
            "shuffle_map": {"A": 0, "B": 1, "C": 2}, "verdict_drift": None,
        })
        monkeypatch.setattr("lib.ledger.write_ledger", lambda **kw: {
            "workspace_dir": "/tmp/test", "files_written": [],
            "cortex_id": None, "notion_url": None, "telegram_sent": False,
            "privacy_audit": {"chain_in_local": False, "chain_in_cortex": False,
                              "chain_in_notion": False, "ac12_grep_clean": True},
            "status": "OK", "errors": {},
        })
        monkeypatch.setattr("lib.cost_meter.CostMeter.commit_to_daily_ledger",
                            lambda self: None)

        result = orchestrator.run_council("Test brief.", depth="standard")
        assert result["status"] == "OK"


# ===========================================================================
# FIX-H3: force_test exempts daily ceiling check
# ===========================================================================

class TestFIXH3ForceTestExemptsDaily:
    """
    CostMeter.check_daily_ceiling() must return (True, "force_test-bypass")
    when force_test=True, even when projected spend exceeds daily ceiling.
    Without force_test, the same projected spend returns (False, ...).
    """

    def test_force_test_exempts_daily_ceiling(self, tmp_path):
        from lib.cost_meter import CostMeter

        # Write a daily spend file showing $48 already spent today
        import json
        from datetime import datetime, timezone
        spend_path = tmp_path / "daily-spend.json"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        spend_path.write_text(json.dumps({today: [{"cost_usd": 48.0}]}))

        # Without force_test: $48 prior + $5 current = $53 → ceiling breach
        meter_normal = CostMeter(
            "standard", task_id="test-normal",
            daily_ceiling=50.0, force_test=False,
            _spend_path=spend_path,
        )
        meter_normal.add_raw(cost_usd=5.0, step="test", label="test")
        ok, msg = meter_normal.check_daily_ceiling()
        assert ok is False, "Without force_test, $53 projected should breach $50 ceiling"

        # With force_test: same $53 projected → bypass
        meter_ft = CostMeter(
            "standard", task_id="test-ft",
            daily_ceiling=50.0, force_test=True,
            _spend_path=spend_path,
        )
        meter_ft.add_raw(cost_usd=5.0, step="test", label="test")
        ok_ft, msg_ft = meter_ft.check_daily_ceiling()
        assert ok_ft is True, \
            f"force_test=True should bypass daily ceiling, got ok={ok_ft}, msg={msg_ft!r}"
        assert "force_test-bypass" in msg_ft, \
            f"Expected 'force_test-bypass' in message, got: {msg_ft!r}"


# ===========================================================================
# FIX-H4: AC-12 grep catches reasoning_chain VALUE leak (not just key name)
# ===========================================================================

class TestFIXH4AC12CatchesValueLeak:
    """
    _ac12_grep_check must return False when a non-raw file contains the first
    40 chars of an advisor's reasoning_chain VALUE — even if the key name
    "reasoning_chain" is absent from that file.
    """

    def test_ac12_catches_value_leak(self, tmp_path):
        from lib.ledger import _ac12_grep_check

        chain_content = "This is the secret reasoning that should never appear on disk."
        advisor_results = [
            {"reasoning_chain": chain_content},
            {"reasoning_chain": ""},
            {"reasoning_chain": ""},
        ]

        # Write a structured file that contains the first 40 chars of the chain
        # (simulating a future bug that leaks chain VALUE without the key name)
        probe = chain_content[:40]
        structured_file = tmp_path / "advisor-A-structured.json"
        structured_file.write_text(json.dumps({"verdict": "PASS", "note": probe}))

        result = _ac12_grep_check(tmp_path, advisor_results, keep_chains=False)
        assert result is False, (
            "FIX-H4 FAIL: _ac12_grep_check returned True (clean) despite chain "
            "VALUE substring being present in advisor-A-structured.json"
        )

    def test_ac12_clean_when_no_leak(self, tmp_path):
        """Workspace with no chain content → returns True (clean)."""
        from lib.ledger import _ac12_grep_check

        advisor_results = [
            {"reasoning_chain": "The real reasoning chain content here."},
            {"reasoning_chain": ""},
            {"reasoning_chain": ""},
        ]
        # Write a benign file that contains neither the key nor the value
        (tmp_path / "verdict.md").write_text("## Agreement Zones\nAll good.\n## Split Zones\nNone.")

        result = _ac12_grep_check(tmp_path, advisor_results, keep_chains=False)
        assert result is True, "Clean workspace should return True"

    def test_ac12_still_catches_key_string(self, tmp_path):
        """Original key-string check must still work (belt-and-suspenders)."""
        from lib.ledger import _ac12_grep_check

        advisor_results = [{"reasoning_chain": ""}, {"reasoning_chain": ""}, {"reasoning_chain": ""}]
        # Write a file with the key name present (but no chain value)
        (tmp_path / "bad.json").write_text('{"reasoning_chain": "leaked"}')

        result = _ac12_grep_check(tmp_path, advisor_results, keep_chains=False)
        assert result is False, "Key-string 'reasoning_chain' in file should still fail"


# ===========================================================================
# FIX-H5: Validator probes actual chain strings in peer_package
# ===========================================================================

class TestFIXH5ValidatorProbesActualChains:
    """
    _validate_peer_package_no_chain with raw_chains_for_validation must detect
    when a peer_package contains the first 40 chars of a chain string.
    Without raw_chains_for_validation this would be a no-op (chains already stripped).
    """

    def test_validator_probes_actual_chains(self):
        from lib.debate import _validate_peer_package_no_chain

        secret = "SECRET_CHAIN_CONTENT_THAT_MUST_NEVER_APPEAR_IN_PEER_PACKAGE"
        # Build a peer_package that contains the first 40 chars of the secret chain
        leaked_probe = secret[:40]
        peer_package = f"<peer_advisors><advisor>{leaked_probe}</advisor></peer_advisors>"

        # Anonymized dicts have no reasoning_chain (already stripped)
        others = [
            {"letter": "B", "top_strengths": ["S1"], "top_risks": ["R1"],
             "critical_blockers": []},
        ]

        # Without raw_chains_for_validation: validator sees no chain → returns True (no-op bug)
        result_without = _validate_peer_package_no_chain(peer_package, others,
                                                          raw_chains_for_validation=None)
        # This may return True or False depending on confidence/nplf probe — the key point
        # is that WITH raw_chains it correctly returns False

        # With raw_chains_for_validation: validator probes actual chain → detects leak
        result_with = _validate_peer_package_no_chain(
            peer_package, others,
            raw_chains_for_validation=[secret, "", ""],
        )
        assert result_with is False, (
            "FIX-H5 FAIL: validator returned True (clean) despite peer_package "
            "containing the first 40 chars of the raw chain. "
            "raw_chains_for_validation probing is not working."
        )

    def test_validator_clean_when_no_chain_in_package(self):
        """Peer package with no chain content should return True."""
        from lib.debate import _validate_peer_package_no_chain

        peer_package = "<peer_advisors><advisor letter='B'><strengths>Good idea.</strengths></advisor></peer_advisors>"
        others = [
            {"letter": "B", "top_strengths": ["Good idea."], "top_risks": ["Risk."],
             "critical_blockers": []},
        ]
        raw_chains = ["Long chain that is definitely not in the peer package above.", "", ""]

        result = _validate_peer_package_no_chain(peer_package, others,
                                                  raw_chains_for_validation=raw_chains)
        assert result is True, "Clean peer_package should pass validation"


# ===========================================================================
# FIX-M1: _minimal_anon_fallback strict allowlist (no verdict_md)
# ===========================================================================

class TestFIXM1MinimalAnonFallbackStrictAllowlist:
    """
    _minimal_anon_fallback must NOT include verdict_md or any other field
    outside the anonymized output allowlist.
    """

    def test_minimal_anon_fallback_strict_allowlist(self):
        from lib.orchestrator import _minimal_anon_fallback

        advisor_with_verdict_md = _make_advisor(
            "A", "gemini-3.1-pro",
            verdict="PASS",
        )
        # Ensure verdict_md is present in the input
        advisor_with_verdict_md["verdict_md"] = "## Verdict\nPASS — this must not leak"

        result = _minimal_anon_fallback([
            advisor_with_verdict_md,
            _make_advisor("B", "opus-4-8"),
            _make_advisor("C", "gpt-5.5"),
        ])

        assert len(result) == 3
        for entry in result:
            assert "verdict_md" not in entry, (
                f"FIX-M1 FAIL: verdict_md found in anonymized fallback dict for "
                f"letter={entry.get('letter')!r}. It must be excluded."
            )
            # These keys must be present
            assert "letter" in entry
            assert "verdict" in entry
            assert "confidence" in entry
            assert "nplf" in entry
            assert "top_strengths" in entry
            assert "top_risks" in entry
            assert "critical_blockers" in entry

    def test_minimal_anon_fallback_padding_has_no_verdict_md(self):
        """Padding entries (when < 3 advisors supplied) must also lack verdict_md."""
        from lib.orchestrator import _minimal_anon_fallback

        # Supply only 1 advisor — function must pad to 3
        result = _minimal_anon_fallback([_make_advisor("A", "gemini-3.1-pro")])

        assert len(result) == 3
        for entry in result:
            assert "verdict_md" not in entry, \
                "FIX-M1 FAIL: padding entry contains verdict_md"


# ===========================================================================
# v1.0.4 FIX-C1: Preflight provider check
# ===========================================================================

class TestFIXC1PreflightProviderCheck:
    """
    _preflight_provider_check raises ValueError when quorum cannot be met,
    and returns a warning list (not exception) when quorum is still satisfiable.
    """

    @pytest.mark.preflight_unit
    def test_preflight_no_openai_key_warns_not_fails_with_min_quorum_2(self, monkeypatch):
        """OPENAI_API_KEY absent + min_quorum=2 → 1 warning returned, no exception."""
        import shutil
        from lib.orchestrator import _preflight_provider_check

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Ensure claude CLI and Advisor A's Ollama key appear present.
        monkeypatch.setenv("OLLAMA_API_KEY", "fake-ollama-key")
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/claude" if cmd == "claude" else None)

        warnings = _preflight_provider_check("standard", min_quorum=2)

        assert len(warnings) == 1
        assert "openai" in warnings[0].lower() or "OPENAI_API_KEY" in warnings[0]

    @pytest.mark.preflight_unit
    def test_preflight_no_openai_key_fails_with_min_quorum_3(self, monkeypatch):
        """OPENAI_API_KEY absent + min_quorum=3 → ValueError with PREFLIGHT_FAIL."""
        import shutil
        from lib.orchestrator import _preflight_provider_check

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/claude" if cmd == "claude" else None)

        with pytest.raises(ValueError, match="PREFLIGHT_FAIL") as exc_info:
            _preflight_provider_check("standard", min_quorum=3)

        assert "OPENAI_API_KEY" in str(exc_info.value)
        assert "OLLAMA_API_KEY" in str(exc_info.value)


# ===========================================================================
# v1.0.4 FIX-C2: Large brief uses stdin, not argv
# ===========================================================================

class TestFIXC2LargeBriefStdin:
    """
    _call_claude_subprocess passes content via stdin (input=), not argv.
    A 150KB brief must not appear in the args list.
    """

    def test_large_brief_does_not_use_argv(self, monkeypatch):
        """150KB user string → subprocess called with input= kwarg, not argv content."""
        import subprocess
        import lib._providers as providers_mod

        captured: list[dict] = []

        def _mock_run(cmd, **kwargs):
            captured.append({"args": cmd, "kwargs": kwargs})
            # Return a minimal valid JSON response
            import types
            r = types.SimpleNamespace()
            r.returncode = 0
            r.stdout = '{"result": "ok", "usage": {}, "total_cost_usd": 0.001, "duration_ms": 100}'
            r.stderr = ""
            return r

        monkeypatch.setattr(subprocess, "run", _mock_run)
        monkeypatch.setattr(providers_mod.shutil, "which", lambda cmd: "/usr/bin/claude")

        large_user = "x" * 150_000  # 150KB

        providers_mod._call_claude_subprocess(
            model="claude-haiku-4-5",
            system="sys prompt",
            user=large_user,
            timeout_s=10.0,
        )

        assert len(captured) == 1
        call = captured[0]

        # content must NOT be in the args list (no argv injection)
        args_str = " ".join(str(a) for a in call["args"])
        assert large_user not in args_str, "Large brief content must not appear in argv"

        # content MUST be passed via stdin (input= kwarg present)
        assert "input" in call["kwargs"], "Large brief must be passed via stdin (input= kwarg)"


# ===========================================================================
# v1.0.4 FIX-M2: Ledger PARTIAL_NO_CORTEX status
# ===========================================================================

class TestFIXM2LedgerPartialNoCortex:
    """
    When Cortex is the only failing sink, ledger returns status=PARTIAL_NO_CORTEX.
    When other sinks also fail, status remains PARTIAL.
    """

    def test_cortex_only_failure_yields_partial_no_cortex(self, tmp_path, monkeypatch):
        """Cortex failure + all other sinks OK → PARTIAL_NO_CORTEX."""
        import lib.ledger as ledger_mod
        from lib.ledger import write_ledger

        _adv = {
            "verdict": "PASS", "confidence": 0.85,
            "nplf": {"n": 7, "p": 8, "l": 7, "f": 7},
            "top_strengths": ["s1"], "top_risks": ["r1"],
            "critical_blockers": [], "verdict_md": "## v\nPASS",
            "reasoning_chain": "chain", "tokens": {"in": 100, "out": 50},
            "cost_usd": 0.01, "duration_s": 1.0, "status": "OK",
            "error": None, "advisor": "A", "provider_key": "gemini-3.1-pro",
            "label": "A",
        }

        monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
        monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: (None, "connection refused"))
        monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: (None, None))
        monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (True, None))

        result = write_ledger(
            task_id="council-20260520-test-0001",
            council_task_id="council-20260520-test-0001",
            brief_xml="<council_brief><goal>test</goal></council_brief>",
            advisor_results=[_adv.copy(), _adv.copy(), _adv.copy()],
            anonymized=[{"letter": "A", "verdict": "PASS", "confidence": 0.85,
                         "nplf": {}, "top_strengths": [], "top_risks": [],
                         "critical_blockers": []}] * 3,
            shuffle_map={"A": "A", "B": "B", "C": "C"},
            seed=42,
            reconciler_result={"tier": "PASS", "confidence": 0.85,
                                "verdict_md": "## Agreement Zones\n\n## Split Zones\n",
                                "dissent_md": ""},
            debate_result=None,
            cost_meter_total=0.05,
            keep_chains=False,
        )

        assert result["status"] == "PARTIAL_NO_CORTEX"
        assert "cortex" in result["errors"]

    def test_cortex_and_telegram_failure_yields_partial(self, tmp_path, monkeypatch):
        """Cortex + Telegram both fail → status=PARTIAL (not PARTIAL_NO_CORTEX)."""
        import lib.ledger as ledger_mod
        from lib.ledger import write_ledger

        _adv = {
            "verdict": "PASS", "confidence": 0.85,
            "nplf": {"n": 7, "p": 8, "l": 7, "f": 7},
            "top_strengths": ["s1"], "top_risks": ["r1"],
            "critical_blockers": [], "verdict_md": "## v\nPASS",
            "reasoning_chain": "chain2", "tokens": {"in": 100, "out": 50},
            "cost_usd": 0.01, "duration_s": 1.0, "status": "OK",
            "error": None, "advisor": "B", "provider_key": "opus-4-8",
            "label": "B",
        }

        monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
        monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: (None, "refused"))
        monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: (None, None))
        monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (False, "bot blocked"))

        result = write_ledger(
            task_id="council-20260520-test-0002",
            council_task_id="council-20260520-test-0002",
            brief_xml="<council_brief><goal>test</goal></council_brief>",
            advisor_results=[_adv.copy(), _adv.copy(), _adv.copy()],
            anonymized=[{"letter": "A", "verdict": "PASS", "confidence": 0.85,
                         "nplf": {}, "top_strengths": [], "top_risks": [],
                         "critical_blockers": []}] * 3,
            shuffle_map={"A": "A", "B": "B", "C": "C"},
            seed=99,
            reconciler_result={"tier": "PASS", "confidence": 0.85,
                                "verdict_md": "## Agreement Zones\n\n## Split Zones\n",
                                "dissent_md": ""},
            debate_result=None,
            cost_meter_total=0.05,
            keep_chains=False,
        )

        assert result["status"] == "PARTIAL"
        assert "cortex" in result["errors"]
        assert "telegram" in result["errors"]
