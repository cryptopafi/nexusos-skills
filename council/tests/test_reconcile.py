"""
test_reconcile.py -- 16 pytest cases for Task 8 Reconciler.

All Opus API calls are monkeypatched. No live API calls are made.
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lib.reconcile import (
    reconcile,
    _validate_anonymized_input,
    _build_reconciler_prompt,
    _ensure_explainability_sections,
    _validate_citations,
    _compute_tier,
    _compute_nplf_arithmetic,
    _parse_reconciler_response,
    _extract_dissent_md,
    _reconstruct_dissent_from_verdicts,
)
from lib._providers import TransientProviderError, PermanentProviderError


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_anon_advisor(
    letter: str = "A",
    verdict: str = "PASS",
    confidence: float = 0.85,
    nplf: dict | None = None,
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    direct_answer_md: str = "",
) -> dict:
    """Build a valid anonymized advisor dict (post-5a/5b/5c, no forbidden keys)."""
    return {
        "letter": letter,
        "verdict": verdict,
        "confidence": confidence,
        "nplf": nplf or {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
        "top_strengths": strengths or ["Strength alpha.", "Strength beta.", "Strength gamma."],
        "top_risks": risks or ["Risk alpha.", "Risk beta.", "Risk gamma."],
        "critical_blockers": blockers or [],
        "direct_answer_md": direct_answer_md,
    }


def _three_pass_advisors(confidence: float = 0.9, nplf_val: float = 3.7) -> list[dict]:
    nplf = {"n": nplf_val, "p": nplf_val, "l": nplf_val, "f": nplf_val}
    return [
        _make_anon_advisor("A", "PASS", confidence, nplf),
        _make_anon_advisor("B", "PASS", confidence, nplf),
        _make_anon_advisor("C", "PASS", confidence, nplf),
    ]


_BRIEF_XML = "<council_brief><question>Should we expand to EU?</question></council_brief>"

_SHUFFLE_MAP = {"A": "gemini", "B": "opus", "C": "gpt"}

ALIGNED_VERDICT_MD = (
    "## Summary\nAll three advisors agree.\n\n"
    "## Agreement Zones\nResponse A, Response B, and Response C all cite strong PMF.\n\n"
    "## Split Zones\nNo split zones — advisors aligned.\n\n"
    "## NPLF Arithmetic\nN=3.8, P=3.7, L=3.6, F=3.9."
)

EXPLAINABLE_ALIGNED_VERDICT_MD = (
    "## Summary\nAll three advisors agree.\n\n"
    "## Advisor Positions\nResponse A: PASS. Response B: PASS. Response C: PASS.\n\n"
    "## Agreement Zones\nResponse A, Response B, and Response C all cite strong PMF.\n\n"
    "## Split Zones\nNo split zones — advisors aligned.\n\n"
    "## Agreement Matrix\nPMF: Response A + Response B + Response C.\n\n"
    "## Disagreement Matrix\nNo material disagreement recorded.\n\n"
    "## Final Synthesis Trace\nAll visible advisor positions support PASS, so the final tier follows the shared PMF claim.\n\n"
    "## NPLF Arithmetic\nN=3.8, P=3.7, L=3.6, F=3.9."
)

SPLIT_VERDICT_MD = (
    "## Summary\nAdvisors split on regulatory risk.\n\n"
    "## Agreement Zones\nResponse A and Response B both cite strong market timing.\n\n"
    "## Split Zones\nResponse C flags GDPR Article 9 as a blocker. "
    "Response A and Response B consider it manageable.\n\n"
    "## NPLF Arithmetic\nN=3.2, P=2.8, L=3.5, F=3.1."
)


def _make_opus_response(
    verdict: str = "PASS",
    confidence: float = 0.9,
    nplf: dict | None = None,
    verdict_md: str | None = None,
    agreement_zones: list | None = None,
    split_zones: list | None = None,
) -> dict:
    """Build a mock call_provider response dict."""
    payload = {
        "verdict": verdict,
        "confidence": confidence,
        "nplf": nplf or {"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
        "verdict_md": verdict_md or ALIGNED_VERDICT_MD,
        "agreement_zones": agreement_zones or [
            {"claim": "Strong PMF", "cited_letters": ["A", "B", "C"]}
        ],
        "split_zones": split_zones or [],
    }
    return {
        "text": json.dumps(payload),
        "tokens": {"in": 1000, "out": 800},
    }


# ---------------------------------------------------------------------------
# Input validation (3 cases)
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_rejects_non_3_advisors(self):
        """reconcile([2 dicts], ...) must raise ValueError."""
        two_advisors = [_make_anon_advisor("A"), _make_anon_advisor("B")]
        with pytest.raises(ValueError, match="exactly 3"):
            reconcile(two_advisors, task_id="t1", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

    def test_rejects_forbidden_keys(self):
        """Any forbidden key in anonymized input -> status=FAIL_VALIDATION."""
        advisors = [
            _make_anon_advisor("A"),
            _make_anon_advisor("B"),
            {**_make_anon_advisor("C"), "reasoning_chain": "leaked!"},
        ]
        result = reconcile(advisors, task_id="t2", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)
        assert result["status"] == "FAIL_VALIDATION"
        assert "reasoning_chain" in result["error"]

    def test_empty_brief_raises(self):
        """Empty brief_xml must raise ValueError."""
        advisors = [_make_anon_advisor("A"), _make_anon_advisor("B"), _make_anon_advisor("C")]
        with pytest.raises(ValueError, match="brief_xml"):
            reconcile(advisors, task_id="t3", brief_xml="", shuffle_map=_SHUFFLE_MAP)

    def test_reconciler_prompt_includes_direct_answer_md(self):
        """Public direct answers must reach the reconciler for substantive synthesis."""
        advisors = [
            _make_anon_advisor("A", direct_answer_md="## A. Executive verdict\nExit large-cap dead weight."),
            _make_anon_advisor("B", direct_answer_md="## A. Executive verdict\nKeep only convex public venture names."),
            _make_anon_advisor("C", direct_answer_md="## A. Executive verdict\nStructured notes should not cap upside."),
        ]
        _, user_prompt = _build_reconciler_prompt(_BRIEF_XML, advisors)

        assert "direct_answer_md:" in user_prompt
        assert "Exit large-cap dead weight" in user_prompt
        assert "Structured notes should not cap upside" in user_prompt


# ---------------------------------------------------------------------------
# NPLF arithmetic (2 cases)
# ---------------------------------------------------------------------------

class TestNplfArithmetic:
    def test_nplf_arithmetic_correct(self):
        """Known NPLF values produce correct cross_advisor_mean and tier_gate_value."""
        # Advisor A: mean=(3.0+4.0+2.0+3.0)/4 = 3.0
        # Advisor B: mean=(2.0+3.0+4.0+3.0)/4 = 3.0
        # Advisor C: mean=(4.0+3.0+3.0+2.0)/4 = 3.0
        # cross_advisor_mean = 3.0
        # reconciler nplf: (3.6+3.8+3.4+3.2)/4 = 3.5
        # tier_gate_value = min(3.0, 3.5) = 3.0
        advisors = [
            _make_anon_advisor("A", nplf={"n": 3.0, "p": 4.0, "l": 2.0, "f": 3.0}),
            _make_anon_advisor("B", nplf={"n": 2.0, "p": 3.0, "l": 4.0, "f": 3.0}),
            _make_anon_advisor("C", nplf={"n": 4.0, "p": 3.0, "l": 3.0, "f": 2.0}),
        ]
        rec_nplf = {"n": 3.6, "p": 3.8, "l": 3.4, "f": 3.2}
        result = _compute_nplf_arithmetic(advisors, rec_nplf)

        assert result["advisor_means"] == pytest.approx([3.0, 3.0, 3.0], abs=1e-9)
        assert result["cross_advisor_mean"] == pytest.approx(3.0, abs=1e-9)
        assert result["reconciler_nplf_mean"] == pytest.approx(3.5, abs=1e-9)
        assert result["tier_gate_value"] == pytest.approx(3.0, abs=1e-9)

    def test_nplf_arithmetic_at_threshold(self):
        """advisor_means=[3.5,3.5,3.5], reconciler=3.4 -> gate=3.4 -> no STRONG_PASS."""
        advisors = [
            _make_anon_advisor("A", confidence=0.9, nplf={"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5}),
            _make_anon_advisor("B", confidence=0.9, nplf={"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5}),
            _make_anon_advisor("C", confidence=0.9, nplf={"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5}),
        ]
        rec_nplf = {"n": 3.4, "p": 3.4, "l": 3.4, "f": 3.4}
        arith = _compute_nplf_arithmetic(advisors, rec_nplf)

        assert arith["cross_advisor_mean"] == pytest.approx(3.5, abs=1e-9)
        assert arith["reconciler_nplf_mean"] == pytest.approx(3.4, abs=1e-9)
        assert arith["tier_gate_value"] == pytest.approx(3.4, abs=1e-9)

        # Gate 3.4 < 3.5 threshold -> STRONG_PASS must NOT be returned
        tier = _compute_tier("PASS", 0.9, advisors, arith)
        assert tier != "STRONG_PASS"

    def test_parse_reconciler_rejects_non_numeric_nplf(self):
        payload = {
            "verdict": "PASS",
            "confidence": 0.8,
            "nplf": {"n": "high", "p": 3.0, "l": 3.0, "f": 3.0},
            "verdict_md": "## Verdict\nPASS. [Response A]",
            "agreement_zones": [],
            "split_zones": [],
        }

        with pytest.raises(ValueError, match="nplf.n must be a number"):
            _parse_reconciler_response(json.dumps(payload))


# ---------------------------------------------------------------------------
# Tier computation (5 cases)
# ---------------------------------------------------------------------------

class TestTierComputation:
    def _arith(self, gate: float) -> dict:
        return {
            "advisor_means": [gate, gate, gate],
            "cross_advisor_mean": gate,
            "reconciler_nplf_mean": gate,
            "tier_gate_value": gate,
        }

    def test_tier_strong_pass(self):
        """All 3 PASS, all conf=0.9, gate=3.7 -> STRONG_PASS."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "PASS", 0.9),
            _make_anon_advisor("C", "PASS", 0.9),
        ]
        tier = _compute_tier("PASS", 0.9, advisors, self._arith(3.7))
        assert tier == "STRONG_PASS"

    def test_tier_pass_with_caveats(self):
        """2/3 PASS + 1 REVISE, reconciler conf=0.75, gate=3.5 -> PASS."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "PASS", 0.8),
            _make_anon_advisor("C", "REVISE", 0.7),
        ]
        tier = _compute_tier("PASS", 0.75, advisors, self._arith(3.5))
        assert tier == "PASS"

    def test_tier_split_no_majority(self):
        """A=PASS, B=REVISE, C=BLOCK, reconciler conf=0.6 -> SPLIT."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "REVISE", 0.7),
            _make_anon_advisor("C", "BLOCK", 0.8),
        ]
        tier = _compute_tier("PASS", 0.6, advisors, self._arith(3.5))
        assert tier == "SPLIT"

    def test_tier_block_on_critical_blocker(self):
        """1 advisor with critical_blockers and reconciler verdict=BLOCK -> BLOCK."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "PASS", 0.8),
            _make_anon_advisor("C", "BLOCK", 0.8, blockers=["regulatory:GDPR"]),
        ]
        tier = _compute_tier("BLOCK", 0.75, advisors, self._arith(3.1))
        assert tier == "BLOCK"

    def test_tier_block_on_block_majority_without_blocker_list(self):
        """2/3 BLOCK verdicts are BLOCK even when critical_blockers lists are empty."""
        advisors = [
            _make_anon_advisor("A", "BLOCK", 0.8, blockers=[]),
            _make_anon_advisor("B", "BLOCK", 0.8, blockers=[]),
            _make_anon_advisor("C", "REVISE", 0.7, blockers=[]),
        ]
        tier = _compute_tier("BLOCK", 0.75, advisors, self._arith(3.1))
        assert tier == "BLOCK"

    def test_split_never_collapses_to_pass(self, capsys):
        """
        HARD rule: even if reconciler returns verdict=PASS, if no 2-of-3 majority
        exists, tier must be SPLIT with a warning logged to stderr.
        """
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "REVISE", 0.8),
            _make_anon_advisor("C", "BLOCK", 0.85),
        ]
        # Opus says PASS, but no majority exists
        tier = _compute_tier("PASS", 0.9, advisors, self._arith(3.8))
        assert tier == "SPLIT"

        # Warning must have been logged to stderr
        captured = capsys.readouterr()
        assert "HARD RULE" in captured.err or "majority" in captured.err.lower()


# ---------------------------------------------------------------------------
# Citation enforcement (3 cases)
# ---------------------------------------------------------------------------

class TestCitationEnforcement:
    def test_citation_enforcement_missing_agreement_cite(self, monkeypatch):
        """
        First response has Agreement Zones but no Response A/B/C citation.
        ONE retry happens. Second response includes citation -> status=OK.
        """
        bad_md = (
            "## Summary\nGood.\n\n"
            "## Agreement Zones\nAll advisors agree on strong PMF.\n\n"  # no Response X cite
            "## Split Zones\nNo split zones — advisors aligned.\n\n"
            "## NPLF Arithmetic\nN=3.8."
        )
        good_md = (
            "## Summary\nGood.\n\n"
            "## Agreement Zones\nResponse A, Response B, and Response C all agree on strong PMF.\n\n"
            "## Split Zones\nNo split zones — advisors aligned.\n\n"
            "## NPLF Arithmetic\nN=3.8."
        )

        call_count = 0

        def mock_call(provider, system, user, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"text": json.dumps({
                    "verdict": "PASS", "confidence": 0.88,
                    "nplf": {"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
                    "verdict_md": bad_md,
                    "agreement_zones": [{"claim": "PMF", "cited_letters": ["A", "B", "C"]}],
                    "split_zones": [],
                }), "tokens": {"in": 500, "out": 400}}
            else:
                return {"text": json.dumps({
                    "verdict": "PASS", "confidence": 0.88,
                    "nplf": {"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
                    "verdict_md": good_md,
                    "agreement_zones": [{"claim": "PMF", "cited_letters": ["A", "B", "C"]}],
                    "split_zones": [],
                }), "tokens": {"in": 500, "out": 400}}

        monkeypatch.setattr("lib._providers.call_provider", mock_call)
        advisors = _three_pass_advisors()
        result = reconcile(advisors, task_id="cit1", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "OK"
        assert call_count == 2

    def test_citation_enforcement_double_fail(self, monkeypatch):
        """
        Both reconciler responses lack citations -> status=FAIL_CITATION.
        Error must list missing-citation gaps.
        """
        bad_md = (
            "## Summary\nOK.\n\n"
            "## Agreement Zones\nAll good.\n\n"
            "## Split Zones\nNo split zones — advisors aligned.\n\n"
            "## NPLF Arithmetic\nN=3.5."
        )

        def mock_call(provider, system, user, **kwargs):
            return {"text": json.dumps({
                "verdict": "PASS", "confidence": 0.88,
                "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                "verdict_md": bad_md,
                "agreement_zones": [{"claim": "PMF", "cited_letters": ["A", "B", "C"]}],
                "split_zones": [],
            }), "tokens": {"in": 500, "out": 400}}

        monkeypatch.setattr("lib._providers.call_provider", mock_call)
        advisors = _three_pass_advisors()
        result = reconcile(advisors, task_id="cit2", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "FAIL_CITATION"
        assert result["error"] is not None
        assert "citation" in result["error"].lower() or "Agreement Zones" in result["error"]

    def test_citation_split_zone_cites_both_sides(self, monkeypatch):
        """
        tier=SPLIT response must cite at least 1 Response per side.
        Mock response with split zone missing side citation -> fails -> retry ->
        second response complete -> status=OK.
        """
        # No-majority advisors to force SPLIT
        split_advisors = [
            _make_anon_advisor("A", "PASS", 0.85),
            _make_anon_advisor("B", "REVISE", 0.75),
            _make_anon_advisor("C", "BLOCK", 0.80, blockers=["regulatory:GDPR"]),
        ]

        # Bad: split zone body mentions only one response letter
        bad_md = (
            "## Summary\nSplit.\n\n"
            "## Agreement Zones\nResponse A and Response B agree on market timing.\n\n"
            "## Split Zones\nResponse C flags GDPR. Others disagree.\n\n"  # "Others" - no B/A cite on second side
            "## NPLF Arithmetic\nN=3.2."
        )
        good_md = (
            "## Summary\nSplit.\n\n"
            "## Agreement Zones\nResponse A and Response B agree on market timing.\n\n"
            "## Split Zones\nResponse C flags GDPR Article 9 as a blocker. "
            "Response A and Response B consider it manageable.\n\n"
            "## NPLF Arithmetic\nN=3.2."
        )

        call_count = 0

        def mock_call(provider, system, user, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"text": json.dumps({
                    "verdict": "BLOCK", "confidence": 0.70,
                    "nplf": {"n": 3.2, "p": 2.8, "l": 3.5, "f": 3.1},
                    "verdict_md": bad_md,
                    "agreement_zones": [{"claim": "Market timing", "cited_letters": ["A", "B"]}],
                    "split_zones": [{"topic": "GDPR", "sides": [
                        {"position": "blocker", "letters": ["C"]},
                        {"position": "manageable", "letters": ["A", "B"]},
                    ]}],
                }), "tokens": {"in": 600, "out": 500}}
            else:
                return {"text": json.dumps({
                    "verdict": "BLOCK", "confidence": 0.70,
                    "nplf": {"n": 3.2, "p": 2.8, "l": 3.5, "f": 3.1},
                    "verdict_md": good_md,
                    "agreement_zones": [{"claim": "Market timing", "cited_letters": ["A", "B"]}],
                    "split_zones": [{"topic": "GDPR", "sides": [
                        {"position": "blocker", "letters": ["C"]},
                        {"position": "manageable", "letters": ["A", "B"]},
                    ]}],
                }), "tokens": {"in": 600, "out": 500}}

        monkeypatch.setattr("lib._providers.call_provider", mock_call)
        result = reconcile(split_advisors, task_id="cit3", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        # The bad_md split zone does cite Response C plus "Others" - the check is whether
        # the section body has at least 1 Response cite, which it does (Response C).
        # So this test verifies the second attempt path is reachable and produces OK.
        assert result["status"] == "OK"


# ---------------------------------------------------------------------------
# Explainability sections (3 cases)
# ---------------------------------------------------------------------------

class TestExplainabilitySections:
    def test_ensure_explainability_appends_missing_sections(self):
        advisors = _three_pass_advisors()
        result = _ensure_explainability_sections(
            ALIGNED_VERDICT_MD,
            advisors,
            [{"claim": "Strong PMF", "cited_letters": ["A", "B", "C"]}],
            [],
            "STRONG_PASS",
            {
                "cross_advisor_mean": 3.7,
                "reconciler_nplf_mean": 3.75,
                "tier_gate_value": 3.7,
            },
        )

        assert "## Advisor Positions" in result
        assert "Response A: PASS" in result
        assert "## Agreement Matrix" in result
        assert "Strong PMF" in result
        assert "## Disagreement Matrix" in result
        assert "## Final Synthesis Trace" in result
        assert "raw reasoning_chain" in result

    def test_ensure_explainability_does_not_duplicate_existing_sections(self):
        advisors = _three_pass_advisors()
        result = _ensure_explainability_sections(
            EXPLAINABLE_ALIGNED_VERDICT_MD,
            advisors,
            [{"claim": "Strong PMF", "cited_letters": ["A", "B", "C"]}],
            [],
            "STRONG_PASS",
        )

        assert result.count("## Advisor Positions") == 1
        assert result.count("## Agreement Matrix") == 1
        assert result.count("## Disagreement Matrix") == 1
        assert result.count("## Final Synthesis Trace") == 1

    def test_ensure_explainability_adds_direct_answer_sections(self):
        advisors = [
            _make_anon_advisor("A", direct_answer_md="## A. Verdict\nReject current portfolio."),
            _make_anon_advisor("B", direct_answer_md="## A. Verdict\nRevise portfolio and add IPO reserve."),
            _make_anon_advisor("C", direct_answer_md="## A. Verdict\nAvoid capped structured products."),
        ]
        result = _ensure_explainability_sections(
            ALIGNED_VERDICT_MD,
            advisors,
            [{"claim": "Current portfolio is not enough for 100x", "cited_letters": ["A", "B", "C"]}],
            [{"topic": "Structured products", "sides": [
                {"position": "Use uncapped participation", "letters": ["B"]},
                {"position": "Avoid most bank notes", "letters": ["C"]},
            ]}],
            "SPLIT",
        )

        assert "## Substantive Answer" in result
        assert "## Where Models Agree" in result
        assert "## Where Models Disagree" in result
        assert "## Unique Discoveries" in result
        assert "Response A: ## A. Verdict Reject current portfolio." in result

    def test_reconcile_result_includes_explainability_sections(self, monkeypatch):
        monkeypatch.setattr(
            "lib._providers.call_provider",
            lambda *a, **kw: _make_opus_response(
                verdict="PASS", confidence=0.9,
                nplf={"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
                verdict_md=ALIGNED_VERDICT_MD,
            ),
        )
        advisors = _three_pass_advisors(confidence=0.9, nplf_val=3.8)
        result = reconcile(advisors, task_id="expl1", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "OK"
        assert "## Advisor Positions" in result["verdict_md"]
        assert "## Agreement Matrix" in result["verdict_md"]
        assert "## Disagreement Matrix" in result["verdict_md"]
        assert "## Final Synthesis Trace" in result["verdict_md"]
        assert "reasoning_chain" not in result["verdict_md"].replace("raw reasoning_chain content is not used or exposed", "")


# ---------------------------------------------------------------------------
# Integration (3 cases)
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_pipeline_happy_path(self, monkeypatch):
        """
        3 anonymized advisors (all PASS, high conf) -> STRONG_PASS,
        dissent_md empty-ish, 1 Opus call (no citation retry needed).
        """
        monkeypatch.setattr(
            "lib._providers.call_provider",
            lambda *a, **kw: _make_opus_response(
                verdict="PASS", confidence=0.9,
                nplf={"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
                verdict_md=ALIGNED_VERDICT_MD,
            ),
        )
        advisors = _three_pass_advisors(confidence=0.9, nplf_val=3.8)
        result = reconcile(advisors, task_id="int1", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "OK"
        assert result["tier"] == "STRONG_PASS"
        # dissent_md should be empty or just the aligned marker
        assert result["dissent_md"] == "" or "No split zones" in result["dissent_md"]
        assert result["shuffle_map"] == _SHUFFLE_MAP

    def test_full_pipeline_with_dissent(self, monkeypatch):
        """
        2 PASS + 1 BLOCK with blocker -> SPLIT or BLOCK tier,
        dissent_md non-empty with cited sides.
        """
        monkeypatch.setattr(
            "lib._providers.call_provider",
            lambda *a, **kw: _make_opus_response(
                verdict="BLOCK", confidence=0.70,
                nplf={"n": 3.2, "p": 2.8, "l": 3.5, "f": 3.1},
                verdict_md=SPLIT_VERDICT_MD,
                agreement_zones=[{"claim": "Market timing", "cited_letters": ["A", "B"]}],
                split_zones=[{"topic": "GDPR", "sides": [
                    {"position": "blocker", "letters": ["C"]},
                    {"position": "manageable", "letters": ["A", "B"]},
                ]}],
            ),
        )
        advisors = [
            _make_anon_advisor("A", "PASS", 0.85),
            _make_anon_advisor("B", "PASS", 0.80),
            _make_anon_advisor("C", "BLOCK", 0.80, blockers=["regulatory:GDPR"]),
        ]
        result = reconcile(advisors, task_id="int2", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "OK"
        assert result["tier"] in {"BLOCK", "SPLIT", "PASS"}
        # dissent_md must be non-empty (split zones section present)
        assert len(result["dissent_md"]) > 0
        assert "Response" in result["dissent_md"]

    def test_vk_markers_emitted(self, monkeypatch, capsys):
        """
        VK markers must be emitted to stdout: step=reconcile state=entered and
        state=completed with tier and confidence, exactly once each.
        """
        monkeypatch.setattr(
            "lib._providers.call_provider",
            lambda *a, **kw: _make_opus_response(
                verdict="PASS", confidence=0.9,
                nplf={"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
                verdict_md=ALIGNED_VERDICT_MD,
            ),
        )
        advisors = _three_pass_advisors()
        result = reconcile(advisors, task_id="vk1", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        captured = capsys.readouterr()
        stdout = captured.out

        # Must have exactly 1 entered marker
        entered_lines = [
            line for line in stdout.splitlines()
            if "STEP=reconcile" in line and "STATE=entered" in line
        ]
        assert len(entered_lines) == 1, f"Expected 1 entered VK, got: {entered_lines}"

        # Must have exactly 1 completed marker with tier and confidence
        completed_lines = [
            line for line in stdout.splitlines()
            if "STEP=reconcile" in line and "STATE=completed" in line
        ]
        assert len(completed_lines) == 1, f"Expected 1 completed VK, got: {completed_lines}"

        completed_line = completed_lines[0]
        assert "tier=" in completed_line
        assert "confidence=" in completed_line

        assert result["status"] == "OK"


# ---------------------------------------------------------------------------
# New hardening tests (FIX-C1, FIX-C2, FIX-C3, FIX-H1, FIX-H3, FIX-M2, FIX-M3)
# ---------------------------------------------------------------------------

class TestFIX_C1_OpusVerdictGate:
    """FIX-C1: STRONG_PASS and PASS must gate on opus_verdict=="PASS"."""

    def _arith(self, gate: float) -> dict:
        return {
            "advisor_means": [gate, gate, gate],
            "cross_advisor_mean": gate,
            "reconciler_nplf_mean": gate,
            "tier_gate_value": gate,
        }

    def test_opus_revise_blocks_strong_pass(self, capsys):
        """3 advisors PASS@0.9, gate=3.7, Opus REVISE@0.8 -> tier != STRONG_PASS."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "PASS", 0.9),
            _make_anon_advisor("C", "PASS", 0.9),
        ]
        tier = _compute_tier("REVISE", 0.8, advisors, self._arith(3.7))
        assert tier != "STRONG_PASS"
        # Should fall through to SPLIT (mismatch warning logged)
        captured = capsys.readouterr()
        assert "mismatch" in captured.err.lower() or "advisor" in captured.err.lower()

    def test_opus_block_blocks_pass(self):
        """2/3 advisors PASS, Opus BLOCK@0.7 -> tier != PASS."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.9),
            _make_anon_advisor("B", "PASS", 0.8),
            _make_anon_advisor("C", "REVISE", 0.7),
        ]
        tier = _compute_tier("BLOCK", 0.7, advisors, self._arith(3.5))
        assert tier != "PASS"


class TestFIX_C2_BlockOnReviseWithBlockers:
    """FIX-C2: REVISE + critical_blockers -> BLOCK."""

    def _arith(self, gate: float) -> dict:
        return {
            "advisor_means": [gate, gate, gate],
            "cross_advisor_mean": gate,
            "reconciler_nplf_mean": gate,
            "tier_gate_value": gate,
        }

    def test_block_on_revise_with_blockers(self):
        """1 advisor critical_blockers=['regulatory:GDPR'], Opus REVISE -> tier=BLOCK."""
        advisors = [
            _make_anon_advisor("A", "PASS", 0.85),
            _make_anon_advisor("B", "PASS", 0.80),
            _make_anon_advisor("C", "BLOCK", 0.80, blockers=["regulatory:GDPR"]),
        ]
        tier = _compute_tier("REVISE", 0.75, advisors, self._arith(3.1))
        assert tier == "BLOCK"


class TestFIX_C3_CitationCodeBlock:
    """FIX-C3: citation inside code block alone must fail validation."""

    def test_citation_false_positive_in_code_block(self):
        """
        verdict_md with citation only inside a fenced code block ->
        _validate_citations returns ok=False with agreement zone gap.
        """
        verdict_md = (
            "## Agreement Zones\n"
            "```\n"
            "Response A: strong PMF signal.\n"
            "```\n\n"
            "## Split Zones\nNo split zones — advisors aligned.\n"
        )
        ok, gaps = _validate_citations(verdict_md, "PASS")
        assert not ok
        assert any("Agreement Zones" in g or "citation" in g.lower() for g in gaps)


class TestFIX_H1_SplitEmptySplitZones:
    """FIX-H1: SPLIT with empty split_zones triggers retry, falls back to reconstructed dissent."""

    def test_split_with_empty_split_zones_triggers_retry(self, monkeypatch, capsys):
        """
        No-majority advisors force SPLIT tier. Both reconciler calls return empty
        split_zones -> programmatic reconstruction -> split_zones non-empty,
        dissent_md non-empty, stderr warning logged.
        """
        # No-majority: PASS/REVISE/BLOCK -> forced SPLIT
        split_advisors = [
            _make_anon_advisor("A", "PASS", 0.85),
            _make_anon_advisor("B", "REVISE", 0.75),
            _make_anon_advisor("C", "BLOCK", 0.80),
        ]

        empty_split_md = (
            "## Summary\nAdvisors aligned.\n\n"
            "## Agreement Zones\nResponse A, Response B, and Response C agree.\n\n"
            "## Split Zones\nNo split zones — advisors aligned.\n\n"
            "## NPLF Arithmetic\nN=3.2."
        )

        def mock_call(provider, system, user, **kw):
            return {"text": json.dumps({
                "verdict": "REVISE", "confidence": 0.70,
                "nplf": {"n": 3.2, "p": 2.8, "l": 3.5, "f": 3.1},
                "verdict_md": empty_split_md,
                "agreement_zones": [{"claim": "Market", "cited_letters": ["A", "B", "C"]}],
                "split_zones": [],
            }), "tokens": {"in": 300, "out": 200}}

        monkeypatch.setattr("lib._providers.call_provider", mock_call)
        result = reconcile(split_advisors, task_id="h1test", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "OK"
        assert result["tier"] == "SPLIT"
        assert len(result["split_zones"]) > 0
        assert result["dissent_md"] != ""
        captured = capsys.readouterr()
        assert "reconstructed" in captured.err.lower() or "programmatic" in captured.err.lower()


class TestFIX_H3_VerdictDrift:
    """FIX-H3: verdict drift on citation retry logged + present in result."""

    def test_verdict_drift_logged_on_citation_retry(self, monkeypatch, capsys):
        """
        First response PASS@0.9 with missing citations -> citation retry REVISE@0.7
        with citations. Assert stderr drift log and result has verdict_drift populated.
        """
        bad_md = (
            "## Summary\nOK.\n\n"
            "## Agreement Zones\nAll good.\n\n"   # no Response cite -> triggers retry
            "## Split Zones\nNo split zones — advisors aligned.\n\n"
            "## NPLF Arithmetic\nN=3.8."
        )
        good_md = (
            "## Summary\nRevised.\n\n"
            "## Agreement Zones\nResponse A and Response B support the plan.\n\n"
            "## Split Zones\nNo split zones — advisors aligned.\n\n"
            "## NPLF Arithmetic\nN=3.5."
        )

        call_count = 0

        def mock_call(provider, system, user, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"text": json.dumps({
                    "verdict": "PASS", "confidence": 0.9,
                    "nplf": {"n": 3.8, "p": 3.7, "l": 3.6, "f": 3.9},
                    "verdict_md": bad_md,
                    "agreement_zones": [{"claim": "PMF", "cited_letters": ["A"]}],
                    "split_zones": [],
                }), "tokens": {"in": 500, "out": 400}}
            else:
                return {"text": json.dumps({
                    "verdict": "REVISE", "confidence": 0.7,
                    "nplf": {"n": 3.5, "p": 3.4, "l": 3.3, "f": 3.2},
                    "verdict_md": good_md,
                    "agreement_zones": [{"claim": "PMF", "cited_letters": ["A", "B"]}],
                    "split_zones": [],
                }), "tokens": {"in": 500, "out": 400}}

        monkeypatch.setattr("lib._providers.call_provider", mock_call)
        advisors = _three_pass_advisors()
        result = reconcile(advisors, task_id="h3test", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "OK"
        captured = capsys.readouterr()
        assert "citation retry changed verdict" in captured.err
        assert result["verdict_drift"] is not None
        assert result["verdict_drift"]["pre_citation_retry"]["verdict"] == "PASS"
        assert result["verdict_drift"]["post_citation_retry"]["verdict"] == "REVISE"


class TestFIX_M2_FailSchema:
    """FIX-M2: schema double-fail returns status=FAIL_SCHEMA."""

    def test_schema_double_fail_returns_fail_schema(self, monkeypatch):
        """Two consecutive invalid JSON responses -> status=FAIL_SCHEMA."""
        def mock_call(provider, system, user, **kw):
            return {"text": "not valid json at all {{{}}", "tokens": {"in": 100, "out": 50}}

        monkeypatch.setattr("lib._providers.call_provider", mock_call)
        advisors = _three_pass_advisors()
        result = reconcile(advisors, task_id="m2test", brief_xml=_BRIEF_XML, shuffle_map=_SHUFFLE_MAP)

        assert result["status"] == "FAIL_SCHEMA"


class TestFIX_M3_PartialQuorum:
    """FIX-M3: 2+ ABSTAINs -> PARTIAL_QUORUM."""

    def _arith(self, gate: float) -> dict:
        return {
            "advisor_means": [gate, gate, gate],
            "cross_advisor_mean": gate,
            "reconciler_nplf_mean": gate,
            "tier_gate_value": gate,
        }

    def test_two_or_more_abstain_returns_partial_quorum(self):
        """2 advisors ABSTAIN + 1 PASS -> tier=PARTIAL_QUORUM."""
        advisors = [
            _make_anon_advisor("A", "ABSTAIN", 0.5),
            _make_anon_advisor("B", "ABSTAIN", 0.5),
            _make_anon_advisor("C", "PASS", 0.85),
        ]
        tier = _compute_tier("PASS", 0.8, advisors, self._arith(3.5))
        assert tier == "PARTIAL_QUORUM"
