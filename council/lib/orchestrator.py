"""
orchestrator.py -- Top-level /council pipeline orchestrator.

Wires all 11 modules (triage, normalize, advisor_gemini/opus/gpt,
anonymize, reconcile, debate, ledger, cost_meter, workspace, vk) into
a single run_council() entry point.

v1.0: advisor lanes are called sequentially (parallel is a v1.1 opt).
"""

from __future__ import annotations

import pathlib
import sys
import time
import traceback
from typing import Any

from . import (
    advisor_gemini,
    advisor_gpt,
    advisor_opus,
    anonymize,
    debate,
    ledger,
    normalize,
    reconcile,
    triage,
    vk,
    workspace,
)
from .cost_meter import CostMeter
from .runtime import support_provider_label

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_DEPTHS = frozenset({"quick", "standard", "deep"})
_VALID_MIN_QUORUMS = frozenset({2, 3})

# Triage score threshold (score < this AND not force → REFUSE).
_TRIAGE_THRESHOLD = 40

# Tier names for INSUFFICIENT_QUORUM short-circuit.
_TIER_INSUFFICIENT_QUORUM = "INSUFFICIENT_QUORUM"


# ---------------------------------------------------------------------------
# Vendor diversity enforcement (FIX-H2)
# ---------------------------------------------------------------------------

def _preflight_provider_check(depth: str, min_quorum: int, *, bypass: bool = False) -> list[str]:
    """
    Returns list of warnings. Raises ValueError if quorum cannot be met.

    Args:
        depth:      Depth tier (unused currently; reserved for tier-aware caps).
        min_quorum: Minimum required advisor lanes.
        bypass:     If True, skip all checks and return immediately. Used by
                    force_test=True (acceptance-test harness) and the autouse
                    conftest fixture so missing real credentials don't block
                    mocked-provider unit tests. Callers should set this
                    explicitly — do not rely on a callsite guard.
    """
    if bypass:
        return []

    import os as _os
    import shutil as _shutil
    import pathlib as _pathlib
    warnings: list[str] = []
    unavailable: list[str] = []

    # Anthropic via claude CLI
    if not _shutil.which("claude"):
        unavailable.append("anthropic (claude CLI missing)")

    # OpenAI (either OPENAI_API_KEY OR `codex` OAuth CLI)
    openai_key_ok = bool(_os.environ.get("OPENAI_API_KEY"))
    if not openai_key_ok:
        if not _shutil.which("codex"):
            unavailable.append("openai (missing OPENAI_API_KEY and codex CLI missing)")
        else:
            try:
                from ._oauth import codex_auth_present
                if not codex_auth_present():
                    unavailable.append("openai (missing OPENAI_API_KEY and codex not logged in: ~/.codex/auth.json missing/empty)")
            except Exception:
                unavailable.append("openai (missing OPENAI_API_KEY and codex auth check failed)")

    # Google (prefer gemini-cli OAuth; fall back to GEMINI_API_KEY)
    gemini_oauth_ok = bool(_shutil.which("gemini") and (_pathlib.Path.home() / ".gemini" / "oauth_creds.json").exists())
    gemini_key_ok = bool(_os.environ.get("GEMINI_API_KEY") or _os.environ.get("GOOGLE_API_KEY"))
    if not (gemini_oauth_ok or gemini_key_ok):
        unavailable.append("google (no gemini OAuth creds at ~/.gemini/oauth_creds.json and no GEMINI_API_KEY)")

    available_count = 3 - len(unavailable)
    if available_count < min_quorum:
        raise ValueError(
            f"PREFLIGHT_FAIL: {len(unavailable)} advisor lane(s) unavailable "
            f"({', '.join(unavailable)}); available={available_count} < "
            f"min_quorum={min_quorum}. Supply missing credentials or use "
            f"--min-quorum {available_count} to proceed with partial council."
        )
    if unavailable:
        warnings.append(
            f"WARN: {len(unavailable)} advisor lane(s) unavailable: "
            f"{', '.join(unavailable)}. Council will run with {available_count}/3 advisors."
        )
    return warnings


def _enforce_vendor_diversity() -> None:
    """
    HARD rule per PROC-COUNCIL-DESIGN-001 §2 Pas 3: all 3 advisor lanes must
    come from different vendors. Raises RuntimeError if fewer than 3 unique
    vendors are present in the active advisor configuration.
    """
    from ._providers import PROVIDER_REGISTRY
    advisor_keys = [
        advisor_gemini.PROVIDER_KEY,
        advisor_opus.PROVIDER_KEY,
        advisor_gpt.PROVIDER_KEY,
    ]
    vendors = {PROVIDER_REGISTRY[k]["vendor"] for k in advisor_keys if k in PROVIDER_REGISTRY}
    if len(vendors) < 3:
        raise RuntimeError(
            f"HARD violation: /council requires 3 different vendors, got "
            f"{sorted(vendors)} (advisor keys: {advisor_keys}). "
            f"See PROC-COUNCIL-DESIGN-001 §2 Pas 3."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_council(
    target: str | pathlib.Path,
    *,
    depth: str = "standard",
    no_debate: bool = False,
    force: bool = False,
    min_quorum: int = 3,
    keep_chains: bool = False,
    force_test: bool = False,
) -> dict:
    """
    Top-level /council invocation. Wires all 11 modules in order.

    Args:
        target:      Path to a brief file OR raw text.
        depth:       "quick" | "standard" | "deep".
        no_debate:   Skip debate even in deep mode.
        force:       Bypass triage threshold gate.
        min_quorum:  Minimum non-ABSTAIN advisors required (2 or 3).
        keep_chains: If True, reasoning_chains survive to ledger.
        force_test:  Internal flag for acceptance-test isolation.

    Returns a result dict with keys:
        council_task_id, tier, verdict_md, dissent_md, confidence, nplf,
        duration_s, cost_usd, ledger, stages, status, error.

    Raises:
        ValueError: invalid depth or min_quorum.

    NOTE (v1.0): advisor lanes run sequentially.  Parallel execution via
    asyncio.gather() is a planned v1.1 optimisation documented in PROC-COUNCIL-DESIGN-001.
    """
    # ------------------------------------------------------------------
    # Step 1 – validate args + init
    # ------------------------------------------------------------------
    if depth not in _VALID_DEPTHS:
        raise ValueError(f"depth must be one of {sorted(_VALID_DEPTHS)}, got {depth!r}")
    if min_quorum not in _VALID_MIN_QUORUMS:
        raise ValueError(f"min_quorum must be in {sorted(_VALID_MIN_QUORUMS)}, got {min_quorum!r}")

    # FIX-H2: enforce 3-vendor diversity before spending any budget
    _enforce_vendor_diversity()

    # FIX-C1: preflight credential check — fail loudly before spending any budget.
    # bypass=force_test so the acceptance-test harness (mocked providers) runs without credentials.
    preflight_warnings = _preflight_provider_check(depth, min_quorum, bypass=force_test)
    for w in preflight_warnings:
        sys.stderr.write(f"[orchestrator] {w}\n")

    wall_start = time.monotonic()
    council_task_id = workspace.generate_task_id()
    # FIX-H3: propagate force_test so daily ceiling is bypassed for test harness runs
    meter = CostMeter(depth=depth, task_id=council_task_id, force=force, force_test=force_test)

    # FIX-H1: orchestrator-level VK emits removed; individual steps cover observability.
    # Check daily ceiling before spending anything.
    ceiling_ok, ceiling_msg = meter.check_daily_ceiling()
    if not ceiling_ok:
        return _emit_refused_result(
            council_task_id,
            ceiling_msg,
            depth,
            meter=meter,
            wall_start=wall_start,
        )

    stages: dict[str, Any] = {
        "triage": None,
        "normalize": None,
        "advisors": [],
        "anonymize": None,
        "reconcile": None,
        "debate": None,
    }

    try:
        # ------------------------------------------------------------------
        # Step 2 – read target text
        # ------------------------------------------------------------------
        target_text = _read_target(target)

        # ------------------------------------------------------------------
        # Step 3 – triage
        # ------------------------------------------------------------------
        triage_result = triage.triage(
            target_text,
            threshold=_TRIAGE_THRESHOLD,
            force=force,
            task_id=council_task_id,
        )
        meter.add_raw(
            cost_usd=_support_model_cost(
                triage_result.get("support_tokens", triage_result.get("haiku_tokens", {}))
            ),
            step="triage",
            label=support_provider_label(),
        )
        stages["triage"] = triage_result

        # Check per-step cap and mid-flight daily ceiling (FIX-M5).
        cap_ok, cap_msg = meter.check_cap()
        if not cap_ok:
            return _emit_refused_result(
                council_task_id,
                f"cap_breach_after_triage: {cap_msg}",
                depth,
                meter=meter,
                wall_start=wall_start,
                stages=stages,
                commit_spend=True,
            )
        ceiling_ok, ceiling_msg = meter.check_daily_ceiling()
        if not ceiling_ok:
            return _emit_refused_result(
                council_task_id,
                f"daily_ceiling_after_triage: {ceiling_msg}",
                depth,
                meter=meter,
                wall_start=wall_start,
                stages=stages,
                commit_spend=True,
            )

        if triage_result.get("verdict") == "REFUSE":
            _commit_meter_best_effort(meter)
            duration_s = time.monotonic() - wall_start
            return {
                "council_task_id": council_task_id,
                "tier": "REFUSED",
                "verdict_md": "",
                "dissent_md": "",
                "confidence": 0.0,
                "nplf": {},
                "duration_s": duration_s,
                "cost_usd": meter.total,
                "ledger": {},
                "stages": stages,
                "status": "REFUSED",
                "error": triage_result.get("reason", "triage refused"),
            }

        # ------------------------------------------------------------------
        # Step 4 – normalize
        # ------------------------------------------------------------------
        normalize_result = normalize.normalize(target_text, task_id=council_task_id)
        meter.add_raw(
            cost_usd=float(normalize_result.get("cost_usd", 0.0)),
            step="normalize",
            label=normalize_result.get("provider_used", "unknown"),
        )
        stages["normalize"] = normalize_result

        if normalize_result.get("verdict") == "FAIL_ALL_PROVIDERS":
            raise RuntimeError(
                f"normalize failed: {normalize_result.get('error', 'all providers exhausted')}"
            )

        brief_xml: str = normalize_result.get("brief_xml", "")

        cap_ok, cap_msg = meter.check_cap()
        if not cap_ok:
            return _emit_refused_result(
                council_task_id,
                f"cap_breach_after_normalize: {cap_msg}",
                depth,
                meter=meter,
                wall_start=wall_start,
                stages=stages,
                commit_spend=True,
            )

        # ------------------------------------------------------------------
        # Step 5 – advisors (sequential, v1.0)
        # ------------------------------------------------------------------
        advisor_results = _build_advisor_list(brief_xml, council_task_id, depth, meter)
        stages["advisors"] = advisor_results

        cap_ok, cap_msg = meter.check_cap()
        if not cap_ok:
            return _emit_refused_result(
                council_task_id,
                f"cap_breach_after_advisors: {cap_msg}",
                depth,
                meter=meter,
                wall_start=wall_start,
                stages=stages,
                commit_spend=True,
            )
        ceiling_ok, ceiling_msg = meter.check_daily_ceiling()  # FIX-M5
        if not ceiling_ok:
            return _emit_refused_result(
                council_task_id,
                f"daily_ceiling_after_advisors: {ceiling_msg}",
                depth,
                meter=meter,
                wall_start=wall_start,
                stages=stages,
                commit_spend=True,
            )

        # ------------------------------------------------------------------
        # Step 6 – quorum check
        # ------------------------------------------------------------------
        advisor_results, quorum_abort = _handle_quorum(advisor_results, min_quorum)
        if quorum_abort:
            _commit_meter_best_effort(meter)
            duration_s = time.monotonic() - wall_start
            return {
                "council_task_id": council_task_id,
                "tier": _TIER_INSUFFICIENT_QUORUM,
                "verdict_md": "",
                "dissent_md": "",
                "confidence": 0.0,
                "nplf": {},
                "duration_s": duration_s,
                "cost_usd": meter.total,
                "ledger": {},
                "stages": stages,
                "status": "ABSTAINED",
                "error": quorum_abort,
            }

        # ------------------------------------------------------------------
        # Step 7 – anonymize
        # ------------------------------------------------------------------
        anon_result = anonymize.anonymize(advisor_results, task_id=council_task_id)
        meter.add_raw(
            cost_usd=float(anon_result.get("cost_usd", 0.0)),
            step="anonymize",
            label=support_provider_label(),
        )
        stages["anonymize"] = anon_result

        anon_list: list[dict] = anon_result.get("anonymized") or []
        shuffle_map: dict = anon_result.get("shuffle_map", {})
        shuffle_seed: int = anon_result.get("seed", 0)

        # Fall back to raw advisor results if anonymize returned empty list
        # (e.g. support-model routing unavailable). In that case build minimal placeholders.
        if not anon_list or len(anon_list) != 3:
            anon_list = _minimal_anon_fallback(advisor_results)
            shuffle_map = {"A": 0, "B": 1, "C": 2}

        cap_ok, cap_msg = meter.check_cap()
        if not cap_ok:
            return _emit_refused_result(
                council_task_id,
                f"cap_breach_after_anonymize: {cap_msg}",
                depth,
                meter=meter,
                wall_start=wall_start,
                stages=stages,
                commit_spend=True,
            )

        # ------------------------------------------------------------------
        # Step 8 – reconcile
        # ------------------------------------------------------------------
        reconcile_result = reconcile.reconcile(
            anon_list,
            task_id=council_task_id,
            brief_xml=brief_xml,
            shuffle_map=shuffle_map,
        )
        meter.add_raw(
            cost_usd=float(reconcile_result.get("cost_usd", 0.0)),
            step="reconcile",
            label=support_provider_label(),
        )
        stages["reconcile"] = reconcile_result

        # FIX-H2: surface post-reconcile cap breach in the final result instead of silently passing.
        # FIX-M5: also check daily ceiling mid-flight after reconcile.
        _post_reconcile_cap_breach: str | None = None
        cap_ok, cap_msg = meter.check_cap()
        if not cap_ok:
            sys.stderr.write(f"[council] post-reconcile cap breach: {cap_msg} (continuing with verdict)\n")
            _post_reconcile_cap_breach = cap_msg
        ceiling_ok, ceiling_msg = meter.check_daily_ceiling()  # FIX-M5
        if not ceiling_ok:
            sys.stderr.write(f"[council] post-reconcile daily ceiling: {ceiling_msg} (continuing with verdict)\n")
            if _post_reconcile_cap_breach is None:
                _post_reconcile_cap_breach = ceiling_msg

        # ------------------------------------------------------------------
        # Step 9 – optional debate (deep + not no_debate)
        # ------------------------------------------------------------------
        debate_result: dict | None = None
        if depth == "deep" and not no_debate:
            can_debate, debate_msg = meter.can_run_debate()
            if can_debate:
                # FIX-C1: Realign advisor_results to match the shuffled anonymized order.
                # anonymized[i].letter was assigned post-shuffle; shuffle_map[letter]
                # gives the original label (index or string) that corresponds to it.
                # Build label → advisor map, then align.
                label_to_advisor = {adv.get("label", str(idx)): adv
                                    for idx, adv in enumerate(advisor_results)}
                # Also index-keyed fallback (shuffle_map may use integer indices)
                idx_to_advisor = {idx: adv for idx, adv in enumerate(advisor_results)}

                aligned_advisors: list[dict] = []
                for anon in anon_list:
                    letter = anon["letter"]
                    original_label = shuffle_map.get(letter, letter)
                    if original_label in label_to_advisor:
                        aligned_advisors.append(label_to_advisor[original_label])
                    elif original_label in idx_to_advisor:
                        aligned_advisors.append(idx_to_advisor[original_label])
                    else:
                        # Defensive: index-based fallback
                        idx = {"A": 0, "B": 1, "C": 2}.get(letter, 0)
                        aligned_advisors.append(advisor_results[idx])

                debate_result = debate.run_debate(
                    anonymized=anon_list,
                    original_advisors=aligned_advisors,
                    brief_xml=brief_xml,
                    task_id=council_task_id,
                    raw_chains_for_validation=[r.get("reasoning_chain", "") for r in advisor_results],
                )
                meter.add_raw(
                    cost_usd=float(debate_result.get("cost_usd", 0.0)),
                    step="debate",
                    label="multi-lane",
                )
                stages["debate"] = debate_result

                # Tier downgrade if debate detected instability.
                if debate_result.get("tier_downgrade_recommended"):
                    current_tier = reconcile_result.get("tier", "PASS")
                    reconcile_result = dict(reconcile_result)
                    reconcile_result["tier"] = _downgrade_tier(current_tier)
                    reconcile_result["debate_downgraded"] = True

        # ------------------------------------------------------------------
        # Step 10 – ledger (4 sinks)
        # ------------------------------------------------------------------
        ledger_result = ledger.write_ledger(
            task_id=council_task_id,
            council_task_id=council_task_id,
            brief_xml=brief_xml,
            advisor_results=advisor_results,
            anonymized=anon_list,
            shuffle_map=shuffle_map,
            seed=shuffle_seed,
            reconciler_result=reconcile_result,
            debate_result=debate_result,
            cost_meter_total=meter.total,
            keep_chains=keep_chains,
        )

        # ------------------------------------------------------------------
        # Step 11 – commit cost to daily ledger
        # ------------------------------------------------------------------
        try:
            meter.commit_to_daily_ledger()
        except Exception as exc:
            sys.stderr.write(
                f"[orchestrator] daily ledger commit failed (non-fatal): {exc}\n"
            )

        duration_s = time.monotonic() - wall_start

        # ------------------------------------------------------------------
        # Step 12 – build final result dict
        # FIX-H2: error field carries post-reconcile cap breach message if any.
        # ------------------------------------------------------------------
        return {
            "council_task_id": council_task_id,
            "tier": reconcile_result.get("tier", "UNKNOWN"),
            "verdict_md": reconcile_result.get("verdict_md", ""),
            "dissent_md": reconcile_result.get("dissent_md", ""),
            "confidence": float(reconcile_result.get("confidence", 0.0)),
            "nplf": reconcile_result.get("nplf", {}),
            "duration_s": duration_s,
            "cost_usd": meter.total,
            "ledger": ledger_result,
            "stages": stages,
            "status": "OK",
            "error": _post_reconcile_cap_breach,
        }

    except Exception as exc:
        duration_s = time.monotonic() - wall_start
        err_detail = f"{type(exc).__name__}: {exc}"
        sys.stderr.write(
            f"[orchestrator] FAILED task={council_task_id}: {err_detail}\n"
            f"{traceback.format_exc()}\n"
        )
        return {
            "council_task_id": council_task_id,
            "tier": "UNKNOWN",
            "verdict_md": "",
            "dissent_md": "",
            "confidence": 0.0,
            "nplf": {},
            "duration_s": duration_s,
            "cost_usd": meter.total,
            "ledger": {},
            "stages": stages,
            "status": "FAILED",
            "error": err_detail,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_target(target: str | pathlib.Path) -> str:
    """
    Return target as text.
    If target looks like a file path and exists on disk, read it.
    Otherwise treat target as raw text.
    """
    path = pathlib.Path(target)
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        pass
    return str(target)


def _build_advisor_list(
    brief_xml: str,
    council_task_id: str,
    depth: str,
    meter: CostMeter,
) -> list[dict]:
    """
    Call all 3 advisor lanes sequentially (v1.0 — parallel is v1.1).
    Returns 3 raw advisor result dicts in the order [gemini, opus, gpt].
    Each result's cost is added to the meter.

    NOTE: If an advisor raises, a synthetic ABSTAIN placeholder is returned
    for that lane so the orchestrator can decide on quorum.
    """
    results: list[dict] = []
    lanes = [
        ("advisor_gemini", "A", advisor_gemini.advise),
        ("advisor_opus",   "B", advisor_opus.advise),
        ("advisor_gpt",    "C", advisor_gpt.advise),
    ]
    for lane_name, lane_letter, advise_fn in lanes:
        try:
            result = advise_fn(brief_xml, task_id=council_task_id, depth=depth)
        except Exception as exc:
            from ._providers import PermanentProviderError
            is_permanent = isinstance(exc, PermanentProviderError)
            sys.stderr.write(
                f"[orchestrator] advisor lane {lane_name} raised "
                f"{type(exc).__name__}: {exc} — substituting ABSTAIN\n"
            )
            # FIX-M2: emit VK failed marker before substituting ABSTAIN placeholder.
            vk.emit(
                f"dispatch_{lane_letter}",
                "failed",
                council_task_id,
                error_class=type(exc).__name__,
            )
            # FIX-C1: for permanent credential failures, mark UNAVAILABLE (not ABSTAIN)
            if is_permanent:
                placeholder = _make_abstain_placeholder(lane_name)
                placeholder["status"] = "UNAVAILABLE"
                placeholder["error"] = f"UNAVAILABLE: {exc}"
                result = placeholder
            else:
                result = _make_abstain_placeholder(lane_name)

        # Accumulate cost into meter.
        raw_cost = float(result.get("cost_usd", 0.0))
        if raw_cost > 0.0:
            meter.add_raw(cost_usd=raw_cost, step=lane_name, label=lane_name)

        results.append(result)

    return results


def _handle_quorum(
    advisor_results: list[dict],
    min_quorum: int,
) -> tuple[list[dict], str | None]:
    """
    Count non-ABSTAIN advisors.

    If >= min_quorum are non-ABSTAIN → return (all 3 results, None).
    If < min_quorum → return (results, "INSUFFICIENT_QUORUM") to trigger
      orchestrator-level ABSTAINED short-circuit.

    ABSTAIN advisors remain in the list (as-is) so reconcile can see
    the placeholder objects if quorum is satisfied.
    """
    non_abstain = sum(
        1 for r in advisor_results
        if r.get("status", "").upper() not in ("ABSTAIN", "FAIL_API", "FAILED", "UNAVAILABLE")
        and r.get("verdict", "").upper() != "ABSTAIN"
    )
    if non_abstain >= min_quorum:
        return advisor_results, None
    return advisor_results, "INSUFFICIENT_QUORUM"


def _emit_refused_result(
    council_task_id: str,
    reason: str,
    depth: str,
    *,
    meter: CostMeter | None = None,
    wall_start: float | None = None,
    stages: dict[str, Any] | None = None,
    commit_spend: bool = False,
) -> dict:
    """Build a refused-result dict for triage refusal or cap breach."""
    if commit_spend and meter is not None:
        _commit_meter_best_effort(meter)
    duration_s = time.monotonic() - wall_start if wall_start is not None else 0.0
    cost_usd = meter.total if meter is not None else 0.0
    return {
        "council_task_id": council_task_id,
        "tier": "REFUSED",
        "verdict_md": "",
        "dissent_md": "",
        "confidence": 0.0,
        "nplf": {},
        "duration_s": duration_s,
        "cost_usd": cost_usd,
        "ledger": {},
        "stages": stages or {
            "triage": None,
            "normalize": None,
            "advisors": [],
            "anonymize": None,
            "reconcile": None,
            "debate": None,
        },
        "status": "REFUSED",
        "error": reason,
    }


def _commit_meter_best_effort(meter: CostMeter) -> None:
    if meter.total <= 0:
        return
    try:
        meter.commit_to_daily_ledger()
    except Exception as exc:
        sys.stderr.write(
            f"[orchestrator] daily spend commit failed on refused path "
            f"(non-fatal): {type(exc).__name__}: {exc}\n"
        )


def _make_abstain_placeholder(label: str) -> dict:
    """Synthetic ABSTAIN advisor result for a failed/timed-out lane."""
    return {
        "verdict": "ABSTAIN",
        "confidence": 0.0,
        "nplf": {"novel": 0, "practical": 0, "legal": 0, "financial": 0},
        "top_strengths": [],
        "top_risks": [],
        "critical_blockers": [],
        "verdict_md": "",
        "reasoning_chain": "",
        "tokens": {"in": 0, "out": 0},
        "cost_usd": 0.0,
        "duration_s": 0.0,
        "status": "ABSTAIN",
        "error": f"lane {label} unavailable",
        "advisor": label,
        "provider_key": "",
    }


def _minimal_anon_fallback(advisor_results: list[dict]) -> list[dict]:
    """
    Construct minimal anonymized dicts when anonymize() returned an empty list.
    Used so reconcile() always receives exactly 3 dicts.

    FIX-M1: Only fields in the anonymized output allowlist are included.
    verdict_md is NOT in the allowed set — it is a raw advisor field that must
    not appear in anonymized output (could leak provider identity via writing style).
    """
    letters = ["A", "B", "C"]
    out = []
    for i, res in enumerate(advisor_results[:3]):
        out.append({
            "letter": letters[i],
            "verdict": res.get("verdict", "ABSTAIN"),
            "confidence": float(res.get("confidence", 0.0)),
            "nplf": res.get("nplf", {}),
            "top_strengths": res.get("top_strengths", []),
            "top_risks": res.get("top_risks", []),
            "critical_blockers": res.get("critical_blockers", []),
        })
    while len(out) < 3:
        out.append({
            "letter": letters[len(out)],
            "verdict": "ABSTAIN",
            "confidence": 0.0,
            "nplf": {},
            "top_strengths": [],
            "top_risks": [],
            "critical_blockers": [],
        })
    return out


def _downgrade_tier(tier: str) -> str:
    """
    One-step tier downgrade when debate detects instability.
    STRONG_PASS → PASS → SPLIT; anything else stays.
    """
    _downgrade_map = {
        "STRONG_PASS": "PASS",
        "PASS": "SPLIT",
    }
    return _downgrade_map.get(tier, tier)


def _support_model_cost(support_tokens: dict) -> float:
    """Estimate runtime support-step cost from legacy token dict names."""
    from ._providers import PROVIDER_REGISTRY
    provider = support_provider_label()
    entry = PROVIDER_REGISTRY.get(provider, {})
    price_in = float(entry.get("price_in", 5.00 / 1_000_000))
    price_out = float(entry.get("price_out", 20.00 / 1_000_000))
    t_in = int(support_tokens.get("in", 0))
    t_out = int(support_tokens.get("out", 0))
    return (t_in * price_in) + (t_out * price_out)


_support_gpt_cost = _support_model_cost  # backwards-compatible test alias
_haiku_cost = _support_model_cost  # backwards-compatible test alias
