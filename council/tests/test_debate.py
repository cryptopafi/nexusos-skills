"""
test_debate.py -- pytest cases for Task 9 Debate Round.

All advisor API calls are monkeypatched. No live API calls are made.
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from lib.debate import (
    run_debate,
    _build_peer_package,
    _detect_instability,
    _validate_peer_package_no_chain,
    _validate_revision_consistency,
    _call_advisor_with_revision,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_anon(
    letter: str = "A",
    verdict: str = "PASS",
    confidence: float = 0.85,
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
) -> dict:
    """Build a valid anonymized advisor dict (post-5b, no reasoning_chain)."""
    return {
        "letter": letter,
        "verdict": verdict,
        "confidence": confidence,
        "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
        "top_strengths": strengths or [f"Strength {letter}1.", f"Strength {letter}2.", f"Strength {letter}3."],
        "top_risks": risks or [f"Risk {letter}1.", f"Risk {letter}2.", f"Risk {letter}3."],
        "critical_blockers": blockers or [],
    }


def _make_original_advisor(
    provider_key: str = "gemini-3.1-pro",
    label: str = "A",
    verdict: str = "PASS",
    confidence: float = 0.85,
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    reasoning_chain: str = "Original reasoning here.",
) -> dict:
    """Build a valid original advisor result dict (full schema with reasoning_chain)."""
    return {
        "advisor": provider_key,
        "label": label,
        "verdict": verdict,
        "confidence": confidence,
        "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
        "top_strengths": strengths or [f"Strength {label}1.", f"Strength {label}2.", f"Strength {label}3."],
        "top_risks": risks or [f"Risk {label}1.", f"Risk {label}2.", f"Risk {label}3."],
        "critical_blockers": blockers or [],
        "reasoning_chain": reasoning_chain,
        "tokens": {"in": 500, "out": 300},
        "cost_usd": 0.01,
        "duration_s": 2.5,
        "status": "OK",
        "error": None,
    }


def _make_three_anons(
    verdicts: list[str] | None = None,
    confidences: list[float] | None = None,
) -> list[dict]:
    verdicts = verdicts or ["PASS", "PASS", "PASS"]
    confidences = confidences or [0.85, 0.80, 0.75]
    return [
        _make_anon("A", verdicts[0], confidences[0]),
        _make_anon("B", verdicts[1], confidences[1]),
        _make_anon("C", verdicts[2], confidences[2]),
    ]


def _make_three_originals(
    providers: list[str] | None = None,
    verdicts: list[str] | None = None,
    confidences: list[float] | None = None,
) -> list[dict]:
    providers = providers or ["gemini-3.1-pro", "opus-4-8", "gpt-5.5"]
    verdicts = verdicts or ["PASS", "PASS", "PASS"]
    confidences = confidences or [0.85, 0.80, 0.75]
    labels = ["A", "B", "C"]
    return [
        _make_original_advisor(providers[i], labels[i], verdicts[i], confidences[i])
        for i in range(3)
    ]


def _revised_response_json(
    verdict: str = "PASS",
    confidence: float = 0.85,
    label: str = "A",
) -> str:
    """Return JSON string matching advisor schema."""
    return json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
        "top_strengths": [f"Revised {label}1.", f"Revised {label}2.", f"Revised {label}3."],
        "top_risks": [f"Risk {label}1.", f"Risk {label}2.", f"Risk {label}3."],
        "critical_blockers": [],
        "reasoning_chain": "Revised reasoning.",
        "revision_rationale": "Held position because no new evidence.",
    })


_BRIEF_XML = "<council_brief><question>Should we expand to EU?</question></council_brief>"
_TASK_ID = "council-test-debate-001"


def _make_call_provider_mock(
    verdicts: list[str] | None = None,
    confidences: list[float] | None = None,
    side_effect_per_call: list | None = None,
) -> MagicMock:
    """
    Build a call_provider mock that cycles through 6 calls (3 Run1 + 3 Run2).
    Each returns a valid advisor JSON response.
    """
    verdicts = verdicts or ["PASS"] * 6
    confidences = confidences or [0.85] * 6

    responses = []
    labels = ["A", "B", "C", "C", "B", "A"]  # Run1 A/B/C then Run2 C/B/A
    for i in range(6):
        responses.append({
            "text": json.dumps({
                "verdict": verdicts[i] if i < len(verdicts) else "PASS",
                "confidence": confidences[i] if i < len(confidences) else 0.85,
                "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                "top_strengths": [f"S{i}1.", f"S{i}2.", f"S{i}3."],
                "top_risks": [f"R{i}1.", f"R{i}2.", f"R{i}3."],
                "critical_blockers": [],
                "reasoning_chain": f"Reasoning call {i}.",
                "revision_rationale": "Held position.",
            }),
            "tokens": {"in": 400, "out": 200},
        })
    if side_effect_per_call:
        mock = MagicMock(side_effect=side_effect_per_call)
    else:
        mock = MagicMock(side_effect=responses)
    return mock


# ---------------------------------------------------------------------------
# 1. Input validation (2 cases)
# ---------------------------------------------------------------------------

class TestInputValidation:

    def test_rejects_non_3_anonymized(self):
        """run_debate with 2 anonymized dicts raises ValueError."""
        with pytest.raises(ValueError, match="anonymized must have exactly 3"):
            run_debate(
                anonymized=[_make_anon("A"), _make_anon("B")],
                original_advisors=_make_three_originals(),
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

    def test_rejects_non_3_original_advisors(self):
        """run_debate with 3 anonymized but 2 original_advisors raises ValueError."""
        with pytest.raises(ValueError, match="original_advisors must have exactly 3"):
            run_debate(
                anonymized=_make_three_anons(),
                original_advisors=_make_three_originals()[:2],
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )


# ---------------------------------------------------------------------------
# 2. Peer-package construction (3 cases)
# ---------------------------------------------------------------------------

class TestPeerPackageConstruction:

    def test_peer_package_excludes_self(self):
        """For letter A, peer_package contains only B and C advisors."""
        b = _make_anon("B", strengths=["B strength 1.", "B strength 2.", "B strength 3."])
        c = _make_anon("C", strengths=["C strength 1.", "C strength 2.", "C strength 3."])
        pkg = _build_peer_package("A", [b, c])
        assert 'letter="B"' in pkg
        assert 'letter="C"' in pkg
        assert 'letter="A"' not in pkg
        assert "B strength 1." in pkg
        assert "C strength 1." in pkg

    def test_peer_package_excludes_reasoning_chain(self):
        """
        FIX-C2 REWRITE: _validate_peer_package_no_chain checks actual chain VALUES.
        Build an others list with a DISTINCTIVE_CHAIN_MARKER — verify it never
        appears in the constructed package, and that the validator returns True.
        """
        # Others have reasoning_chain with a distinctive marker that would be
        # obvious if leaked into the peer package.
        others = [
            {
                "letter": "B",
                "verdict": "PASS",
                "confidence": 0.9,
                "nplf": {"n": 3, "p": 3, "l": 3, "f": 3},
                "top_strengths": ["B strength 1.", "B strength 2.", "B strength 3."],
                "top_risks": ["B risk 1.", "B risk 2.", "B risk 3."],
                "critical_blockers": [],
                "reasoning_chain": "DISTINCTIVE_CHAIN_MARKER_42_should_never_appear in peer package",
            },
            {
                "letter": "C",
                "verdict": "PASS",
                "confidence": 0.8,
                "nplf": {"n": 3, "p": 3, "l": 3, "f": 3},
                "top_strengths": ["C strength 1.", "C strength 2.", "C strength 3."],
                "top_risks": ["C risk 1.", "C risk 2.", "C risk 3."],
                "critical_blockers": [],
                "reasoning_chain": "ANOTHER_CHAIN_MARKER_99_must_not_leak into output",
            },
        ]
        pkg = _build_peer_package("A", others)
        # The distinctive marker MUST NOT appear in the constructed package
        assert "DISTINCTIVE_CHAIN_MARKER_42" not in pkg
        assert "ANOTHER_CHAIN_MARKER_99" not in pkg
        # And the validator must return True (no leak detected)
        assert _validate_peer_package_no_chain(pkg, others) is True

    def test_peer_package_excludes_confidence_and_nplf(self):
        """Peer package contains only strengths/risks/blockers — no confidence or nplf."""
        anons = _make_three_anons()
        others = [anons[1], anons[2]]
        pkg = _build_peer_package("A", others)
        # Must have structural elements
        assert "<strengths>" in pkg
        assert "<risks>" in pkg
        assert "<critical_blockers>" in pkg
        # Must NOT have fingerprint-leaking fields
        assert "confidence" not in pkg
        assert "nplf" not in pkg
        assert '"n":' not in pkg
        assert '"p":' not in pkg

    def test_validator_catches_synthetic_chain_leak(self):
        """
        FIX-C2 NEW: validator returns False when chain content is synthetically
        injected into the peer package (simulates a future _build bug).
        """
        chain_content = "LEAK_CONTENT_should_be_caught_by_validator_xqz99 " * 3
        others = [
            {
                "letter": "B",
                "verdict": "PASS",
                "confidence": 0.9,
                "nplf": {"n": 3, "p": 3, "l": 3, "f": 3},
                "top_strengths": ["s1", "s2", "s3"],
                "top_risks": ["r1", "r2", "r3"],
                "critical_blockers": [],
                "reasoning_chain": chain_content,
            }
        ]
        # Simulate a leaky package that accidentally includes the chain content
        leaky_pkg = (
            f"<peer_advisors>\n"
            f"  <advisor letter=\"B\">\n"
            f"    <strengths>\n  - s1\n    </strengths>\n"
            f"    <reasoning_chain_leaked>{chain_content[:60]}</reasoning_chain_leaked>\n"
            f"  </advisor>\n"
            f"</peer_advisors>"
        )
        assert _validate_peer_package_no_chain(leaky_pkg, others) is False


# ---------------------------------------------------------------------------
# 3. Run mechanics (3 cases)
# ---------------------------------------------------------------------------

class TestRunMechanics:

    def test_run1_uses_anonymized_bullets(self):
        """
        Run 1 peer-packages are built from ANONYMIZED (voice-normalized) bullets.
        Verify by checking that anonymized strength text appears in the peer
        packages fed to each advisor call.
        """
        anons = [
            _make_anon("A", strengths=["ANON_BULLET_A1.", "ANON_BULLET_A2.", "ANON_BULLET_A3."]),
            _make_anon("B", strengths=["ANON_BULLET_B1.", "ANON_BULLET_B2.", "ANON_BULLET_B3."]),
            _make_anon("C", strengths=["ANON_BULLET_C1.", "ANON_BULLET_C2.", "ANON_BULLET_C3."]),
        ]
        originals = _make_three_originals()

        captured_user_prompts: list[str] = []

        def mock_call_provider(provider, system, user, **kwargs):
            captured_user_prompts.append(user)
            return {
                "text": _revised_response_json(),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "OK"
        # Run 1 calls are first 3 captured prompts
        # Advisor A (index 0) sees B and C bullets
        assert "ANON_BULLET_B1." in captured_user_prompts[0]
        assert "ANON_BULLET_C1." in captured_user_prompts[0]
        # Advisor A should NOT see its own bullets in peer package
        assert "ANON_BULLET_A1." not in captured_user_prompts[0]

    def test_run2_uses_run1_originals_not_revised(self):
        """
        FIX-C1 REWRITE: Run 2's peer packages MUST use the anonymized (voice-normalized)
        bullets — the same source as Run 1 — NOT the pre-anonymization original_advisors
        data. The order-bias test requires identical INPUT bullets, just reversed order.

        We verify by checking that Run 2 call prompts contain ANON_BULLET_X text
        (from the anonymized dicts), and do NOT contain any pre-anonymization text
        that only lived in original_advisors.
        """
        # Anonymized dicts have distinctly identifiable ANON bullet text.
        anons = [
            _make_anon("A", strengths=["ANON_BULLET_A1.", "ANON_BULLET_A2.", "ANON_BULLET_A3."]),
            _make_anon("B", strengths=["ANON_BULLET_B1.", "ANON_BULLET_B2.", "ANON_BULLET_B3."]),
            _make_anon("C", strengths=["ANON_BULLET_C1.", "ANON_BULLET_C2.", "ANON_BULLET_C3."]),
        ]
        # Original advisors have PRE-ANON text that must NEVER appear in Run 2 peer packages.
        originals = [
            _make_original_advisor(
                "gemini-3.1-pro", "A",
                strengths=["PREANON_ORIG_A_S1.", "PREANON_ORIG_A_S2.", "PREANON_ORIG_A_S3."]
            ),
            _make_original_advisor(
                "opus-4-8", "B",
                strengths=["PREANON_ORIG_B_S1.", "PREANON_ORIG_B_S2.", "PREANON_ORIG_B_S3."]
            ),
            _make_original_advisor(
                "gpt-5.5", "C",
                strengths=["PREANON_ORIG_C_S1.", "PREANON_ORIG_C_S2.", "PREANON_ORIG_C_S3."]
            ),
        ]

        captured_user_prompts: list[str] = []

        def mock_call_provider(provider, system, user, **kwargs):
            captured_user_prompts.append(user)
            return {
                "text": _revised_response_json("PASS", 0.80),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "OK"
        assert len(captured_user_prompts) == 6

        # Run 2 calls are prompts at indices 3, 4, 5.
        # The peer_package is injected under the "## Peer Advisor Analyses" section.
        # We extract that section and verify:
        #   - ANON_BULLET text appears (anonymized bullets used as input)
        #   - PREANON_ORIG text does NOT appear (pre-anonymization voice-fingerprinted data absent)
        # NOTE: PREANON_ORIG text CAN appear in the advisor's OWN "Previous Verdict" section
        # (that's the advisor seeing their own original state, which is allowed). We only
        # care that PREANON_ORIG is absent from the PEER PACKAGE section.
        for i in range(3, 6):
            prompt = captured_user_prompts[i]
            # Extract only the peer-package portion of the prompt
            if "## Peer Advisor Analyses" in prompt:
                peer_section = prompt.split("## Peer Advisor Analyses", 1)[1]
            else:
                peer_section = prompt  # fallback: check full prompt

            # Peer package MUST NOT contain pre-anonymization voice-fingerprinted bullets
            assert "PREANON_ORIG" not in peer_section, (
                f"Run 2 call {i} peer-package section contains pre-anonymization bullet text — "
                f"this re-leaks voice fingerprints that anonymization deliberately stripped"
            )
            # Peer package MUST contain anonymized bullet text
            found_anon = any(
                f"ANON_BULLET_{lbl}1." in peer_section
                for lbl in ["A", "B", "C"]
            )
            assert found_anon, (
                f"Run 2 call {i} peer-package section does not contain any ANON_BULLET_X1. text — "
                f"Run 2 must use the same anonymized input as Run 1 (reversed order only)"
            )

    def test_run2_order_reversed(self):
        """Run 2 iterates C->B->A. Capture provider call order in Run 2."""
        # original_advisors[0]=gemini(A), [1]=opus(B), [2]=gpt(C)
        originals = _make_three_originals()
        anons = _make_three_anons()

        provider_call_order: list[str] = []
        call_count = [0]

        def mock_call_provider(provider, system, user, **kwargs):
            provider_call_order.append(provider)
            call_count[0] += 1
            return {
                "text": _revised_response_json(),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "OK"
        assert len(provider_call_order) == 6
        # Run 1: calls 0,1,2 should be A->B->C = gemini, opus, gpt
        assert provider_call_order[0] == "gemini-3.1-pro"
        assert provider_call_order[1] == "opus-4-8"
        assert provider_call_order[2] == "gpt-5.5"
        # Run 2: calls 3,4,5 should be C->B->A = gpt, opus, gemini
        assert provider_call_order[3] == "gpt-5.5"
        assert provider_call_order[4] == "opus-4-8"
        assert provider_call_order[5] == "gemini-3.1-pro"


# ---------------------------------------------------------------------------
# 4. Instability detection (3 cases)
# ---------------------------------------------------------------------------

class TestInstabilityDetection:

    def test_confidence_drift_above_threshold_flags_instability(self):
        """Run 1 A=0.85, Run 2 A=0.55 (delta 0.30) -> instability=True, tier_downgrade=True."""
        originals = _make_three_originals()
        anons = _make_three_anons()

        # 6 calls: Run1 A,B,C then Run2 C,B,A
        # Run1 advisor A (call 0): confidence 0.85
        # Run2 advisor A (call 5): confidence 0.55
        call_idx = [0]
        confidences = [0.85, 0.80, 0.75, 0.75, 0.80, 0.55]  # Run2 last call = A at 0.55

        def mock_call_provider(provider, system, user, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            return {
                "text": json.dumps({
                    "verdict": "PASS",
                    "confidence": confidences[idx],
                    "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                    "top_strengths": ["S1.", "S2.", "S3."],
                    "top_risks": ["R1.", "R2.", "R3."],
                    "critical_blockers": [],
                    "reasoning_chain": "Reasoning.",
                    "revision_rationale": "Held.",
                }),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "OK"
        assert result["instability_detected"] is True
        assert result["tier_downgrade_recommended"] is True
        # Find the drift metric for advisor A
        a_metric = next(
            m for m in result["drift_metrics"] if m["advisor_label"] == "A"
        )
        assert a_metric["confidence_delta"] > 0.20
        assert len(result["instability_reasons"]) >= 1

    def test_verdict_change_flags_instability(self):
        """Run 1 A=PASS, Run 2 A=BLOCK -> instability=True even if confidence stable."""
        originals = _make_three_originals()
        anons = _make_three_anons()

        call_idx = [0]
        # Run1: A=PASS, B=PASS, C=PASS; Run2: C=PASS, B=PASS, A=BLOCK
        verdicts_seq = ["PASS", "PASS", "PASS", "PASS", "PASS", "BLOCK"]
        # Keep confidence stable (delta <= 0.05)
        confidences_seq = [0.85, 0.80, 0.75, 0.75, 0.80, 0.83]

        def mock_call_provider(provider, system, user, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            return {
                "text": json.dumps({
                    "verdict": verdicts_seq[idx],
                    "confidence": confidences_seq[idx],
                    "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                    "top_strengths": ["S1.", "S2.", "S3."],
                    "top_risks": ["R1.", "R2.", "R3."],
                    "critical_blockers": [],
                    "reasoning_chain": "Reasoning.",
                    "revision_rationale": "Changed due to new evidence.",
                }),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "OK"
        assert result["instability_detected"] is True
        assert result["tier_downgrade_recommended"] is True
        # Find A metric and verify verdict_changed
        a_metric = next(
            m for m in result["drift_metrics"] if m["advisor_label"] == "A"
        )
        assert a_metric["verdict_changed"] is True
        assert a_metric["verdict_run1"] == "PASS"
        assert a_metric["verdict_run2"] == "BLOCK"

    def test_stable_runs_no_instability(self):
        """All advisors hold within 0.10 confidence + same verdicts -> instability=False."""
        originals = _make_three_originals()
        anons = _make_three_anons()

        call_idx = [0]
        # All PASS, confidence delta well within 0.10
        confidences_seq = [0.85, 0.80, 0.75, 0.74, 0.79, 0.84]

        def mock_call_provider(provider, system, user, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            return {
                "text": json.dumps({
                    "verdict": "PASS",
                    "confidence": confidences_seq[idx],
                    "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                    "top_strengths": ["S1.", "S2.", "S3."],
                    "top_risks": ["R1.", "R2.", "R3."],
                    "critical_blockers": [],
                    "reasoning_chain": "Stable reasoning.",
                    "revision_rationale": "Held.",
                }),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "OK"
        assert result["instability_detected"] is False
        assert result["tier_downgrade_recommended"] is False
        assert result["instability_reasons"] == []
        for metric in result["drift_metrics"]:
            assert metric["confidence_delta"] <= 0.20
            assert metric["verdict_changed"] is False


# ---------------------------------------------------------------------------
# 5. VK + cost (1 case)
# ---------------------------------------------------------------------------

class TestVKAndCost:

    def test_vk_markers_and_cost(self, capsys):
        """
        stdout contains VK:STEP=debate STATE=entered and STATE=completed instability=<bool>.
        cost_usd accumulates across all 6 revise calls (3 Run1 + 3 Run2).
        """
        originals = _make_three_originals()
        anons = _make_three_anons()

        def mock_call_provider(provider, system, user, **kwargs):
            return {
                "text": _revised_response_json(),
                "tokens": {"in": 400, "out": 200},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        captured = capsys.readouterr()
        stdout = captured.out

        # VK entered marker
        assert "VK:STEP=debate" in stdout
        assert "STATE=entered" in stdout
        # VK completed marker with instability bool
        assert "STATE=completed" in stdout
        assert "instability=" in stdout

        # Cost should be sum across 6 calls
        # Each mock call: tokens in=400, out=200
        # gemini-3.1-pro: price_in=3.5/1e6, price_out=14.0/1e6
        # opus-4-8: price_in=5.0/1e6, price_out=25.0/1e6
        # gpt-5.5: price_in=5.0/1e6, price_out=20.0/1e6
        # Call order: gemini(A), opus(B), gpt(C), gpt(C), opus(B), gemini(A)
        # Cost = 2 * (400*3.5/1e6 + 200*14.0/1e6)   # gemini x2
        #      + 2 * (400*5.0/1e6 + 200*25.0/1e6)  # opus x2
        #      + 2 * (400*5.0/1e6 + 200*20.0/1e6)   # gpt x2
        expected_gemini = 2 * (400 * 3.5 / 1e6 + 200 * 14.0 / 1e6)
        expected_opus = 2 * (400 * 5.0 / 1e6 + 200 * 25.0 / 1e6)
        expected_gpt = 2 * (400 * 5.0 / 1e6 + 200 * 20.0 / 1e6)
        expected_total = expected_gemini + expected_opus + expected_gpt

        assert result["cost_usd"] > 0.0
        assert abs(result["cost_usd"] - expected_total) < 0.001, (
            f"cost_usd {result['cost_usd']:.6f} != expected {expected_total:.6f}"
        )

        # Verify 6 calls total (3 Run1 + 3 Run2)
        assert result["tokens"]["in"] == 400 * 6
        assert result["tokens"]["out"] == 200 * 6


# ---------------------------------------------------------------------------
# 6. FIX-H1: Run-2 partial failure preserves Run-1 results (1 case)
# ---------------------------------------------------------------------------

class TestRun2PartialFailure:

    def test_run2_failure_preserves_run1(self):
        """
        FIX-H1: When Run 2 raises an exception, run_debate returns status=PARTIAL
        with run1 containing 3 valid results, run2=[], instability_detected=True
        (precautionary), and tier_downgrade_recommended=True.
        Run 1 results must NOT be discarded.

        We patch _call_advisor_with_revision directly so the exception escapes
        the Run-2 loop (call_provider exceptions are swallowed inside
        _call_advisor_with_revision's own try/except).
        """
        originals = _make_three_originals()
        anons = _make_three_anons()

        call_idx = [0]

        # Build 3 valid Run-1 return values
        run1_returns = [
            {
                "advisor": p, "label": lbl, "verdict": "PASS", "confidence": 0.85,
                "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                "top_strengths": ["S1.", "S2.", "S3."],
                "top_risks": ["R1.", "R2.", "R3."],
                "critical_blockers": [],
                "reasoning_chain": "ok", "revision_rationale": "Held.",
                "tokens": {"in": 300, "out": 150}, "cost_usd": 0.001,
                "duration_s": 0.1, "status": "OK", "error": None,
            }
            for p, lbl in [("gemini-3.1-pro", "A"), ("opus-4-8", "B"), ("gpt-5.5", "C")]
        ]

        def mock_call_advisor(original_advisor_result, peer_package, brief_xml, task_id, debate_round):
            idx = call_idx[0]
            call_idx[0] += 1
            if debate_round == 2:
                raise RuntimeError("Simulated Run 2 API failure")
            return run1_returns[idx]

        with patch("lib.debate._call_advisor_with_revision", side_effect=mock_call_advisor):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "PARTIAL"
        assert len(result["run1"]) == 3, "Run 1 results must be preserved on Run 2 failure"
        assert result["run2"] == []
        assert result["instability_detected"] is True
        assert result["tier_downgrade_recommended"] is True
        assert result["error"] is not None
        assert "Simulated Run 2 API failure" in result["error"]


# ---------------------------------------------------------------------------
# 7. FIX-H2: Revision rationale consistency (1 case)
# ---------------------------------------------------------------------------

class TestRevisionRationaleConsistency:

    def test_revision_rationale_inconsistency_flagged(self, capsys):
        """
        FIX-H2: When a revised result has verdict changed (PASS→BLOCK) but
        revision_rationale says "Held position because nothing new" — the
        status must be downgraded to SCHEMA_INCONSISTENT and a stderr warning
        must be logged. The revised verdict is preserved but marked untrusted.
        """
        originals = _make_three_originals(verdicts=["PASS", "PASS", "PASS"])
        anons = _make_three_anons(verdicts=["PASS", "PASS", "PASS"])

        call_idx = [0]

        def mock_call_provider(provider, system, user, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            # Run 1: all PASS with held rationale
            if idx < 3:
                return {
                    "text": json.dumps({
                        "verdict": "PASS",
                        "confidence": 0.85,
                        "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                        "top_strengths": ["S1.", "S2.", "S3."],
                        "top_risks": ["R1.", "R2.", "R3."],
                        "critical_blockers": [],
                        "reasoning_chain": "Stable reasoning.",
                        "revision_rationale": "Held position because no new evidence.",
                    }),
                    "tokens": {"in": 300, "out": 150},
                }
            # Run 2, first call (idx=3 = advisor C): verdict CHANGED PASS→BLOCK
            # but rationale says "Held position" — pure inconsistency with no
            # revised_signals words present.
            if idx == 3:
                return {
                    "text": json.dumps({
                        "verdict": "BLOCK",
                        "confidence": 0.70,
                        "nplf": {"n": 2.0, "p": 2.0, "l": 2.0, "f": 2.0},
                        "top_strengths": ["S1.", "S2.", "S3."],
                        "top_risks": ["R1.", "R2.", "R3."],
                        "critical_blockers": ["New blocker."],
                        "reasoning_chain": "Flipped verdict.",
                        "revision_rationale": "Held position — no substantial new information presented.",
                    }),
                    "tokens": {"in": 300, "out": 150},
                }
            # Remaining Run 2 calls: stable
            return {
                "text": json.dumps({
                    "verdict": "PASS",
                    "confidence": 0.80,
                    "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                    "top_strengths": ["S1.", "S2.", "S3."],
                    "top_risks": ["R1.", "R2.", "R3."],
                    "critical_blockers": [],
                    "reasoning_chain": "Stable.",
                    "revision_rationale": "Held position.",
                }),
                "tokens": {"in": 300, "out": 150},
            }

        with patch("lib._providers.call_provider", side_effect=mock_call_provider):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        captured = capsys.readouterr()

        # Overall run can still succeed (inconsistency doesn't abort)
        assert result["status"] in ("OK", "PARTIAL")

        # The inconsistent revised result (advisor C, which is run2[0] = C in C->B->A order)
        # must be flagged as SCHEMA_INCONSISTENT
        inconsistent_results = [
            r for r in result["run2"]
            if r.get("status") == "SCHEMA_INCONSISTENT"
        ]
        assert len(inconsistent_results) >= 1, (
            "Expected at least one run2 result with status=SCHEMA_INCONSISTENT "
            f"for verdict-changed-but-says-held inconsistency. run2={result['run2']}"
        )

        # A stderr warning must have been logged
        assert "WARNING" in captured.err or "inconsistency" in captured.err.lower(), (
            f"Expected stderr warning for revision_rationale inconsistency. "
            f"stderr={captured.err!r}"
        )


# ---------------------------------------------------------------------------
# 8. FIX-H3: VK state for partial run uses completed, not failed (1 case)
# ---------------------------------------------------------------------------

class TestVKStatePartial:

    def test_vk_state_partial_uses_completed_not_failed(self, capsys):
        """
        FIX-H3: When Run 2 fails (PARTIAL), VK must emit STATE=completed (not failed).
        state="failed" is reserved for catastrophic Run-1 failure only.
        PARTIAL result must carry instability=true in the VK line extras.

        We patch _call_advisor_with_revision directly so the Run-2 exception
        escapes the loop (call_provider exceptions are swallowed internally).
        """
        originals = _make_three_originals()
        anons = _make_three_anons()

        run1_returns = [
            {
                "advisor": p, "label": lbl, "verdict": "PASS", "confidence": 0.85,
                "nplf": {"n": 3.5, "p": 3.5, "l": 3.5, "f": 3.5},
                "top_strengths": ["S1.", "S2.", "S3."],
                "top_risks": ["R1.", "R2.", "R3."],
                "critical_blockers": [],
                "reasoning_chain": "ok", "revision_rationale": "Held.",
                "tokens": {"in": 300, "out": 150}, "cost_usd": 0.001,
                "duration_s": 0.1, "status": "OK", "error": None,
            }
            for p, lbl in [("gemini-3.1-pro", "A"), ("opus-4-8", "B"), ("gpt-5.5", "C")]
        ]

        def mock_call_advisor(original_advisor_result, peer_package, brief_xml, task_id, debate_round):
            if debate_round == 2:
                raise RuntimeError("Simulated Run 2 failure for VK test")
            provider = original_advisor_result.get("advisor", "gemini-3.1-pro")
            lbl = original_advisor_result.get("label", "A")
            return next(r for r in run1_returns if r["advisor"] == provider)

        with patch("lib.debate._call_advisor_with_revision", side_effect=mock_call_advisor):
            result = run_debate(
                anonymized=anons,
                original_advisors=originals,
                brief_xml=_BRIEF_XML,
                task_id=_TASK_ID,
            )

        assert result["status"] == "PARTIAL"

        captured = capsys.readouterr()
        stdout_lines = captured.out.splitlines()

        # Must have a "completed" VK line (not "failed") for the partial case
        completed_lines = [
            l for l in stdout_lines
            if "STATE=completed" in l and "VK:STEP=debate" in l
        ]
        failed_lines = [
            l for l in stdout_lines
            if "STATE=failed" in l and "VK:STEP=debate" in l
        ]

        assert len(completed_lines) >= 1, (
            "Expected VK STATE=completed for PARTIAL result, got none. "
            f"stdout={captured.out!r}"
        )
        assert len(failed_lines) == 0, (
            "VK STATE=failed must NOT be emitted for PARTIAL (Run-2-only failure). "
            f"stdout={captured.out!r}"
        )

        # The completed VK line should carry instability=true
        assert any("instability=true" in l for l in completed_lines), (
            f"Expected instability=true in completed VK line. lines={completed_lines}"
        )
