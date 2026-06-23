"""
debate.py -- Task 9: Optional debate round for /council skill (--deep only).

Two-run order-reversed mechanics with conformism-instability detection.

Public API
----------
  run_debate(*, anonymized, original_advisors, brief_xml, task_id) -> dict

Design
------
This is the INVERSE of anonymization: advisors intentionally see each
other's voice-normalized bullets. The two-run order reversal (A→B→C then
C→B→A) is the safeguard against conformism documented by Sachdeva 2025
(Claude+Gemini revise 28-41% from peer pressure, not evidence).

HARD invariant: reasoning_chain NEVER appears in peer_packages. Only
voice-normalized bullets (top_strengths, top_risks, critical_blockers)
are shared. Confidence/nplf are also excluded as they can leak provider
fingerprints across advisors.

VK state contract (FIX-H3):
  - state="failed"    — only on catastrophic Run-1 failure (no results preserved).
  - state="completed" — on full success AND on partial success (Run-2 failed).
                        Partial success signals instability=True, status=PARTIAL
                        in the returned dict. Downstream consumers check "status"
                        for nuance; "completed" always means debate was attempted
                        and Run-1 results are available.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from . import vk
from . import advisor_gemini
from . import advisor_opus
from . import advisor_gpt
from ._providers import PROVIDER_REGISTRY


# ---------------------------------------------------------------------------
# Provider-to-module dispatch
# ---------------------------------------------------------------------------

_ADVISOR_MODULES: dict[str, Any] = {
    "gemini-3.1-pro": advisor_gemini,
    "opus-4-8": advisor_opus,
    "gpt-5.5": advisor_gpt,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_debate(
    *,
    anonymized: list[dict],
    original_advisors: list[dict],
    brief_xml: str,
    task_id: str,
    raw_chains_for_validation: list[str] | None = None,
) -> dict:
    """
    Two-run debate with order reversal.

    Args:
        anonymized: 3 anonymized dicts from anonymize() output with letter A/B/C.
                    Used to build peer-input packages for each advisor.
        original_advisors: 3 raw advisor result dicts from advisor_*.advise().
                    Needed so we can issue the REVISE call back to the same
                    advisor lane (by `advisor` key).
        brief_xml: Original canonical brief.
        task_id: VK emission (step="debate").
        raw_chains_for_validation: Optional list of reasoning_chain strings from
            pre-anonymization advisor outputs (one per advisor, same order as
            advisor_results). If provided, _validate_peer_package_no_chain uses
            these actual chain substrings as probes instead of relying only on
            the stripped anonymized dicts (which have no chain content to probe).
            FIX-H5: makes the validator meaningful — previously a no-op because
            anonymized dicts already had chains stripped.

    Returns:
        {
          "run1": [3 revised dicts in A->B->C order],
          "run2": [3 revised dicts in C->B->A order],
          "instability_detected": bool,
          "instability_reasons": list[str],
          "drift_metrics": [
              {"advisor_label": str, "confidence_delta": float,
               "verdict_changed": bool, "verdict_run1": str, "verdict_run2": str},
              ...
          ],
          "tier_downgrade_recommended": bool,
          "tokens": {"in": int, "out": int},
          "cost_usd": float,
          "duration_s": float,
          "status": "OK" | "PARTIAL" | "FAIL_VALIDATION" | "FAIL_API",
          "error": str | None,
        }

    CRITICAL caller contract:
        original_advisors[i] MUST correspond to anonymized[i]. That is, the caller
        is responsible for aligning the two lists via the shuffle_map returned by
        anonymize(). If anonymized was produced with shuffle_map = {"A": "label_2", ...},
        then original_advisors[0] (corresponding to anonymized[0].letter="A") MUST be
        the advisor whose label was "label_2" pre-shuffle.

        Misalignment will deliver the wrong peer-package to the wrong advisor and
        silently corrupt the order-bias measurement.

    Raises:
        ValueError: if anonymized != 3 or original_advisors != 3.
    """
    # --- Input validation ---
    if len(anonymized) != 3:
        raise ValueError(
            f"anonymized must have exactly 3 entries, got {len(anonymized)}"
        )
    if len(original_advisors) != 3:
        raise ValueError(
            f"original_advisors must have exactly 3 entries, got {len(original_advisors)}"
        )

    vk.emit("debate", "entered", task_id)
    wall_start = time.monotonic()

    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost: float = 0.0

    # --- RUN 1: A -> B -> C order ---
    # Peer packages built from anonymized (voice-normalized) bullets.
    run1_order = list(range(3))  # [0, 1, 2] = A, B, C
    run1_results: list[dict] = []

    try:
        for i in run1_order:
            others = [anonymized[j] for j in run1_order if j != i]
            self_letter = anonymized[i].get("letter", str(i))
            peer_pkg = _build_peer_package(self_letter, others)

            # HARD: validate no reasoning_chain leaked into peer_package.
            # FIX-H5: pass raw_chains_for_validation so the validator probes
            # actual chain content, not the already-stripped anonymized dicts.
            if not _validate_peer_package_no_chain(
                peer_pkg, others, raw_chains_for_validation=raw_chains_for_validation
            ):
                return _fail_result(
                    "FAIL_VALIDATION",
                    "reasoning_chain leaked into peer_package",
                    wall_start,
                    total_tokens_in,
                    total_tokens_out,
                    total_cost,
                )

            revised = _call_advisor_with_revision(
                original_advisor_result=original_advisors[i],
                peer_package=peer_pkg,
                brief_xml=brief_xml,
                task_id=task_id,
                debate_round=1,
            )
            tokens_in = revised.get("tokens", {}).get("in", 0)
            tokens_out = revised.get("tokens", {}).get("out", 0)
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out
            total_cost += revised.get("cost_usd", 0.0)
            run1_results.append(revised)

    except Exception as exc:
        duration_s = time.monotonic() - wall_start
        vk.emit("debate", "failed", task_id)
        return {
            "run1": [],
            "run2": [],
            "instability_detected": False,
            "instability_reasons": [],
            "drift_metrics": [],
            "tier_downgrade_recommended": False,
            "tokens": {"in": total_tokens_in, "out": total_tokens_out},
            "cost_usd": total_cost,
            "duration_s": duration_s,
            "status": "FAIL_API",
            "error": str(exc),
        }

    # --- RUN 2: C -> B -> A reversed order ---
    # FIX-C1: Peer packages built from ANONYMIZED bullets (same source as Run 1).
    # "Run 1's originals" = the anonymized voice-normalized input bullets, NOT
    # the raw pre-anonymization advisor output. Reversed iteration order is the
    # order-bias test; the input content must stay identical to Run 1.
    run2_order = [2, 1, 0]  # C, B, A indices
    run2_results_unordered: dict[int, dict] = {}

    try:
        for i in run2_order:
            # FIX-C1: Use anonymized[j] in reversed order — same source as Run 1.
            others_anonymized = [anonymized[j] for j in reversed(range(3)) if j != i]
            self_letter = anonymized[i].get("letter", str(i))
            peer_pkg = _build_peer_package(self_letter, others_anonymized)

            if not _validate_peer_package_no_chain(
                peer_pkg, others_anonymized, raw_chains_for_validation=raw_chains_for_validation
            ):
                return _fail_result(
                    "FAIL_VALIDATION",
                    "reasoning_chain leaked into Run-2 peer_package",
                    wall_start,
                    total_tokens_in,
                    total_tokens_out,
                    total_cost,
                )

            revised = _call_advisor_with_revision(
                original_advisor_result=original_advisors[i],
                peer_package=peer_pkg,
                brief_xml=brief_xml,
                task_id=task_id,
                debate_round=2,
            )

            # FIX-H2: Validate revision_rationale consistency
            original_verdict = original_advisors[i].get("verdict", "ABSTAIN")
            inconsistency = _validate_revision_consistency(revised, original_verdict)
            if inconsistency is not True:
                sys.stderr.write(
                    f"[debate] WARNING: revision_rationale inconsistency for "
                    f"advisor {revised.get('advisor','?')} round 2: {inconsistency}\n"
                )
                revised = dict(revised)
                revised["status"] = "SCHEMA_INCONSISTENT"

            tokens_in = revised.get("tokens", {}).get("in", 0)
            tokens_out = revised.get("tokens", {}).get("out", 0)
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out
            total_cost += revised.get("cost_usd", 0.0)
            run2_results_unordered[i] = revised

    except Exception as exc:
        # FIX-H1: Run-2 failure preserves Run-1 results.
        # Return PARTIAL status with run1 intact rather than discarding everything.
        duration_s = time.monotonic() - wall_start
        sys.stderr.write(
            f"[debate] Run 2 failed partway: {exc} — returning Run 1 only\n"
        )
        vk.emit(
            "debate", "completed", task_id,
            instability="true",
            status="PARTIAL",
        )
        return {
            "run1": run1_results,
            "run2": [],
            "instability_detected": True,  # precautionary
            "instability_reasons": [f"run2_failed: {exc}"],
            "drift_metrics": [],
            "tier_downgrade_recommended": True,
            "tokens": {"in": total_tokens_in, "out": total_tokens_out},
            "cost_usd": total_cost,
            "duration_s": duration_s,
            "status": "PARTIAL",
            "error": str(exc),
        }

    # Reorder Run 2 results to match C->B->A presentation order
    run2_results: list[dict] = [run2_results_unordered[i] for i in run2_order]

    # --- Instability detection ---
    # Match run1 and run2 by index (same underlying advisor at position i)
    instability_detected, instability_reasons, drift_metrics = _detect_instability(
        run1_results, [run2_results_unordered[i] for i in [0, 1, 2]]
    )
    tier_downgrade_recommended = instability_detected

    duration_s = time.monotonic() - wall_start

    vk.emit(
        "debate", "completed", task_id,
        instability=str(instability_detected).lower()
    )

    return {
        "run1": run1_results,
        "run2": run2_results,
        "instability_detected": instability_detected,
        "instability_reasons": instability_reasons,
        "drift_metrics": drift_metrics,
        "tier_downgrade_recommended": tier_downgrade_recommended,
        "tokens": {"in": total_tokens_in, "out": total_tokens_out},
        "cost_usd": total_cost,
        "duration_s": duration_s,
        "status": "OK",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_peer_package(self_letter: str, others: list[dict]) -> str:
    """
    Build the peer-review payload for one advisor from ANONYMIZED dicts.

    Format:
      <peer_advisors>
        <advisor letter="X">
          <strengths>...</strengths>
          <risks>...</risks>
          <critical_blockers>...</critical_blockers>
        </advisor>
        ...
      </peer_advisors>

    MUST NOT include reasoning_chain, confidence, nplf — only voice-normalized
    bullets. confidence/nplf could leak fingerprints; reasoning_chain is explicitly
    banned (cornerstone of anti-collusion design).
    """
    parts: list[str] = ["<peer_advisors>"]
    for other in others:
        letter = other.get("letter", "?")
        if letter == self_letter:
            continue
        strengths = other.get("top_strengths", [])
        risks = other.get("top_risks", [])
        blockers = other.get("critical_blockers", [])

        strengths_text = "\n".join(f"  - {s}" for s in strengths)
        risks_text = "\n".join(f"  - {r}" for r in risks)
        blockers_text = "\n".join(f"  - {b}" for b in blockers)

        parts.append(f'  <advisor letter="{letter}">')
        parts.append(f"    <strengths>\n{strengths_text}\n    </strengths>")
        parts.append(f"    <risks>\n{risks_text}\n    </risks>")
        parts.append(f"    <critical_blockers>\n{blockers_text}\n    </critical_blockers>")
        parts.append("  </advisor>")
    parts.append("</peer_advisors>")
    return "\n".join(parts)


def _call_advisor_with_revision(
    original_advisor_result: dict,
    peer_package: str,
    brief_xml: str,
    task_id: str,
    debate_round: int,
) -> dict:
    """
    Re-invoke the advisor lane with a REVISION prompt.

    Uses the original advisor's provider_key (gemini-3.1-pro/opus-4-8/gpt-5.5).
    System prompt loaded from prompts/debate-revisor.md.
    Returns a new advisor dict (same shape as advisor_*.advise()).
    """
    provider_key: str = original_advisor_result.get("advisor", "")
    advisor_module = _ADVISOR_MODULES.get(provider_key)
    if advisor_module is None:
        raise ValueError(
            f"Unknown advisor provider key {provider_key!r}. "
            f"Expected one of: {sorted(_ADVISOR_MODULES.keys())}"
        )

    # Build the revision user prompt
    system_prompt = _load_debate_revisor_prompt()
    original_verdict = original_advisor_result.get("verdict", "ABSTAIN")
    original_confidence = original_advisor_result.get("confidence", 0.0)
    original_reasoning = original_advisor_result.get("reasoning_chain", "")
    original_strengths = original_advisor_result.get("top_strengths", [])
    original_risks = original_advisor_result.get("top_risks", [])
    original_blockers = original_advisor_result.get("critical_blockers", [])

    # Compose original verdict summary for the revision prompt
    original_summary = json.dumps({
        "verdict": original_verdict,
        "confidence": original_confidence,
        "top_strengths": original_strengths,
        "top_risks": original_risks,
        "critical_blockers": original_blockers,
        "reasoning_chain": original_reasoning,
    }, indent=2)

    user_prompt = (
        f"## Original Brief\n\n{brief_xml}\n\n"
        f"## Your Previous Verdict (Debate Round {debate_round})\n\n"
        f"```json\n{original_summary}\n```\n\n"
        f"## Peer Advisor Analyses\n\n{peer_package}\n\n"
        "Please revise your verdict as instructed. Return strict JSON."
    )

    # Re-invoke via the advisor module's advise() with the revision system prompt
    # We call the advisor module's underlying _advisor_common.run_advisor with
    # a custom user prompt by patching system/user building.
    # Since advisor_*.advise() doesn't accept custom prompts, we call _advisor_common
    # directly with the revision system prompt.
    from . import _advisor_common
    from . import _providers as providers

    entry = PROVIDER_REGISTRY.get(provider_key, {})
    price_in: float = entry.get("price_in", 0.0)
    price_out: float = entry.get("price_out", 0.0)

    # Get max_reasoning_kwargs per provider
    max_reasoning_kwargs = _get_max_reasoning_kwargs(provider_key)

    wall_start = time.monotonic()
    try:
        response = providers.call_provider(
            provider_key,
            system_prompt,
            user_prompt,
            max_tokens=4096,
            temperature=0.2,
            timeout_s=400.0,
            **max_reasoning_kwargs,
        )
        text = response.get("text", "")
        tokens_in = response.get("tokens", {}).get("in", 0)
        tokens_out = response.get("tokens", {}).get("out", 0)
        cost_usd = tokens_in * price_in + tokens_out * price_out
        duration_s = time.monotonic() - wall_start

        try:
            parsed = _advisor_common._parse_advisor_response(text)
        except ValueError:
            # Schema parse failure — return an ABSTAIN result preserving cost
            return {
                "advisor": provider_key,
                "label": original_advisor_result.get("label", "?"),
                "verdict": "ABSTAIN",
                "confidence": 0.0,
                "nplf": {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0},
                "top_strengths": [],
                "top_risks": [],
                "critical_blockers": [],
                "reasoning_chain": "",
                "revision_rationale": "",
                "tokens": {"in": tokens_in, "out": tokens_out},
                "cost_usd": cost_usd,
                "duration_s": duration_s,
                "status": "SCHEMA_FAIL",
                "error": f"debate_round={debate_round} schema_fail",
            }

        return {
            "advisor": provider_key,
            "label": original_advisor_result.get("label", "?"),
            "verdict": parsed.get("verdict", "ABSTAIN"),
            "confidence": parsed.get("confidence", 0.0),
            "nplf": parsed.get("nplf", {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0}),
            "top_strengths": parsed.get("top_strengths", []),
            "top_risks": parsed.get("top_risks", []),
            "critical_blockers": parsed.get("critical_blockers", []),
            "reasoning_chain": parsed.get("reasoning_chain", ""),
            "revision_rationale": parsed.get("revision_rationale", ""),
            "tokens": {"in": tokens_in, "out": tokens_out},
            "cost_usd": cost_usd,
            "duration_s": duration_s,
            "status": "OK",
            "error": None,
        }

    except Exception as exc:
        duration_s = time.monotonic() - wall_start
        return {
            "advisor": provider_key,
            "label": original_advisor_result.get("label", "?"),
            "verdict": "ABSTAIN",
            "confidence": 0.0,
            "nplf": {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0},
            "top_strengths": [],
            "top_risks": [],
            "critical_blockers": [],
            "reasoning_chain": "",
            "revision_rationale": "",
            "tokens": {"in": 0, "out": 0},
            "cost_usd": 0.0,
            "duration_s": duration_s,
            "status": "FAIL_API",
            "error": str(exc),
        }


def _detect_instability(
    run1_results: list[dict],
    run2_results: list[dict],
) -> tuple[bool, list[str], list[dict]]:
    """
    Compare each advisor (by position) across runs.

    Returns: (instability_bool, reason_list, drift_metrics_list).
    Instability triggered if ANY advisor has:
      - |confidence_run2 - confidence_run1| > 0.20
      - verdict changed between runs
    """
    instability = False
    reasons: list[str] = []
    drift_metrics: list[dict] = []

    for i, (r1, r2) in enumerate(zip(run1_results, run2_results)):
        label = r1.get("label", r1.get("advisor", str(i)))
        c1 = float(r1.get("confidence", 0.0))
        c2 = float(r2.get("confidence", 0.0))
        v1 = r1.get("verdict", "ABSTAIN")
        v2 = r2.get("verdict", "ABSTAIN")
        delta = abs(c2 - c1)
        verdict_changed = v1 != v2

        drift_metrics.append({
            "advisor_label": label,
            "confidence_delta": round(delta, 4),
            "verdict_changed": verdict_changed,
            "verdict_run1": v1,
            "verdict_run2": v2,
        })

        if delta > 0.20:
            instability = True
            reasons.append(
                f"Advisor {label}: confidence delta {delta:.3f} > 0.20 "
                f"(run1={c1:.2f}, run2={c2:.2f})"
            )
        if verdict_changed:
            instability = True
            reasons.append(
                f"Advisor {label}: verdict changed {v1} -> {v2} between runs"
            )

    return instability, reasons, drift_metrics


def _validate_peer_package_no_chain(
    peer_package: str,
    others: list[dict],
    raw_chains_for_validation: list[str] | None = None,
) -> bool:
    """
    Defensive check: assert no advisor's reasoning_chain content (or other
    fingerprinting fields) appears in the package payload.

    FIX-H5: When raw_chains_for_validation is provided (actual pre-anonymization
    chain strings), probes those 40-char substrings first. Without this, the
    validator was a near-no-op because anonymized dicts already have chains stripped.

    Also checks confidence JSON and nplf JSON don't leak.

    Returns True if clean (no leak), False if any value leaked.
    """
    # FIX-H5: probe actual chain substrings if supplied by caller
    if raw_chains_for_validation:
        for chain in raw_chains_for_validation:
            if chain and len(chain) > 20:
                probe = chain[:40].strip()
                if probe and probe in peer_package:
                    return False

    # Belt-and-suspenders: also probe chains present in `others` (usually stripped)
    for other in others:
        chain = other.get("reasoning_chain", "")
        if chain and len(chain) > 20:
            probe = chain[:40].strip()
            if probe and probe in peer_package:
                return False
        # Check confidence + nplf JSON-rendered forms don't leak
        if "confidence" in other:
            conf_str = f'"confidence": {other["confidence"]}'
            if conf_str in peer_package:
                return False
        if "nplf" in other and isinstance(other["nplf"], dict):
            nplf_str = json.dumps(other["nplf"])
            if nplf_str in peer_package:
                return False
    return True


def _validate_revision_consistency(revised: dict, original_verdict: str) -> bool | str:
    """
    FIX-H2: Validate that revision_rationale signal words are consistent with
    whether the verdict actually changed.

    Returns True if consistent, or an error string describing the inconsistency.
    On inconsistency the caller should downgrade revised["status"] to
    "SCHEMA_INCONSISTENT" and log a stderr warning. Does NOT raise.
    """
    rationale = revised.get("revision_rationale", "").lower()
    verdict_changed = revised.get("verdict", "ABSTAIN") != original_verdict

    held_signals = ("held", "hold", "no revision", "unchanged", "stand by", "maintain")
    revised_signals = ("revised my", "changed my", "updated my", "new evidence", "reconsidered")

    rationale_says_held = any(s in rationale for s in held_signals)
    rationale_says_revised = any(s in rationale for s in revised_signals)

    if verdict_changed and rationale_says_held and not rationale_says_revised:
        return (
            f"verdict changed {original_verdict}→{revised.get('verdict')} "
            f"but rationale says held"
        )
    if not verdict_changed and rationale_says_revised and not rationale_says_held:
        return "verdict unchanged but rationale says revised"
    return True


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _get_max_reasoning_kwargs(provider_key: str) -> dict:
    """Return provider-specific max-reasoning kwargs for debate revision calls."""
    if provider_key == "ollama-glm-5.2-cloud":
        return {"options": {"num_ctx": 131072}}
    elif provider_key == "gemini-3.1-pro":
        return {"thinking_config": {"thinking_level": "high"}}
    elif provider_key == "opus-4-8":
        return {"thinking": {"type": "enabled", "effort": "high"}}
    elif provider_key == "gpt-5.5":
        return {
            "reasoning": {"effort": "xhigh"},
            "text": {"verbosity": "high"},
            "_use_responses_api": True,
        }
    return {}


def _load_debate_revisor_prompt() -> str:
    """Load prompts/debate-revisor.md relative to this package's skill root."""
    skill_root = Path(__file__).resolve().parent.parent
    prompt_path = skill_root / "prompts" / "debate-revisor.md"
    return prompt_path.read_text(encoding="utf-8")


def _fail_result(
    status: str,
    error: str,
    wall_start: float,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
) -> dict:
    """Build a failure result dict."""
    return {
        "run1": [],
        "run2": [],
        "instability_detected": False,
        "instability_reasons": [],
        "drift_metrics": [],
        "tier_downgrade_recommended": False,
        "tokens": {"in": tokens_in, "out": tokens_out},
        "cost_usd": cost_usd,
        "duration_s": time.monotonic() - wall_start,
        "status": status,
        "error": error,
    }
