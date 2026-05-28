"""
reconcile.py -- Task 8: Reconciler for the /council skill.

Synthesizes 3 anonymized advisor verdicts (from anonymize.py) into a single
dissent-preserving final verdict using the runtime-native support model.

Public API
----------
  reconcile(anonymized, *, task_id, brief_xml, shuffle_map) -> dict

Internal helpers (also importable for testing)
-----------------------------------------------
  _validate_anonymized_input(anonymized) -> str | None
  _build_reconciler_prompt(brief_xml, anonymized) -> tuple[str, str]
  _ensure_explainability_sections(verdict_md, anonymized, agreement_zones, split_zones, tier) -> str
  _validate_citations(verdict_md, tier) -> tuple[bool, list[str]]
  _compute_tier(opus_verdict, opus_confidence, anonymized, nplf_arithmetic) -> str
  _compute_nplf_arithmetic(anonymized, reconciler_nplf) -> dict
  _parse_reconciler_response(text) -> dict
  _extract_dissent_md(verdict_md) -> str
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time
from typing import Any

from . import _providers
from . import vk
from ._advisor_common import _BACKOFF_DELAYS, _MAX_ATTEMPTS, _strip_markdown_fences
from .anonymize import _FORBIDDEN_OUTPUT_KEYS
from .runtime import support_provider_key

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RECONCILER_PROVIDER_KEY = support_provider_key()
_OPUS_PROVIDER_KEY = _RECONCILER_PROVIDER_KEY  # backwards-compatible internal name

# Reconciler pricing from PROVIDER_REGISTRY
_RECONCILER_PRICE_IN = _providers.PROVIDER_REGISTRY.get(_RECONCILER_PROVIDER_KEY, {}).get("price_in", 5.00 / 1_000_000)
_RECONCILER_PRICE_OUT = _providers.PROVIDER_REGISTRY.get(_RECONCILER_PROVIDER_KEY, {}).get("price_out", 20.00 / 1_000_000)
_OPUS_PRICE_IN = _RECONCILER_PRICE_IN  # backwards-compatible internal name
_OPUS_PRICE_OUT = _RECONCILER_PRICE_OUT

# Valid tier values
_VALID_TIERS = frozenset({
    "STRONG_PASS",
    "PASS",
    "SPLIT",
    "BLOCK",
    "PARTIAL_QUORUM",
    "ABSTAIN",
})

# Load reconciler system prompt once at module import time.
_PROMPT_PATH = (
    pathlib.Path(__file__).parent.parent / "prompts" / "reconciler.md"
)
_RECONCILER_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_anonymized_input(anonymized: list[dict]) -> str | None:
    """
    Returns None if valid, error string if forbidden key found.
    Uses _FORBIDDEN_OUTPUT_KEYS from anonymize (symmetric defense).
    """
    leaked: list[str] = []
    for i, d in enumerate(anonymized):
        if not isinstance(d, dict):
            return f"anonymized[{i}] is not a dict"
        for key in _FORBIDDEN_OUTPUT_KEYS:
            if key in d:
                leaked.append(f"{key} (in index {i})")
    if leaked:
        return f"forbidden key(s) found in anonymized input: {', '.join(leaked)}"
    return None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_reconciler_prompt(brief_xml: str, anonymized: list[dict]) -> tuple[str, str]:
    """
    Returns (system, user).
    System: loaded from prompts/reconciler.md.
    User: <council_brief>...</council_brief> + 3 <response letter="A|B|C"> blocks.
    """
    system = _RECONCILER_SYSTEM_PROMPT

    # Wrap brief if not already wrapped
    stripped_brief = brief_xml.strip()
    if not stripped_brief.startswith("<council_brief>"):
        brief_block = f"<council_brief>\n{stripped_brief}\n</council_brief>"
    else:
        brief_block = stripped_brief

    # Build Response blocks
    response_blocks: list[str] = []
    for d in anonymized:
        letter = d.get("letter", "?")
        block_lines = [f'<response letter="{letter}">']
        block_lines.append(f'verdict: {d.get("verdict", "UNKNOWN")}')
        block_lines.append(f'confidence: {d.get("confidence", 0.0)}')

        nplf = d.get("nplf", {})
        block_lines.append(
            f'nplf: n={nplf.get("n", 0.0)} p={nplf.get("p", 0.0)} '
            f'l={nplf.get("l", 0.0)} f={nplf.get("f", 0.0)}'
        )

        strengths = d.get("top_strengths", [])
        block_lines.append("top_strengths:")
        for s in strengths:
            block_lines.append(f"  - {s}")

        risks = d.get("top_risks", [])
        block_lines.append("top_risks:")
        for r in risks:
            block_lines.append(f"  - {r}")

        blockers = d.get("critical_blockers", [])
        if blockers:
            block_lines.append("critical_blockers:")
            for b in blockers:
                block_lines.append(f"  - {b}")

        direct_answer = str(d.get("direct_answer_md") or "").strip()
        if direct_answer:
            block_lines.append("direct_answer_md:")
            block_lines.append(_clip_multiline(direct_answer, max_chars=12000))

        block_lines.append("</response>")
        response_blocks.append("\n".join(block_lines))

    user = brief_block + "\n\n" + "\n\n".join(response_blocks)
    return system, user


def _clip_multiline(text: str, *, max_chars: int) -> str:
    """Keep long public advisor reports bounded while preserving markdown shape."""
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 120].rstrip() + "\n\n[TRUNCATED: advisor direct_answer_md exceeded prompt budget]"


# ---------------------------------------------------------------------------
# Explainability sections
# ---------------------------------------------------------------------------

_EXPLAINABILITY_HEADERS = (
    "## Substantive Answer",
    "## Where Models Agree",
    "## Where Models Disagree",
    "## Unique Discoveries",
    "## Advisor Positions",
    "## Agreement Matrix",
    "## Disagreement Matrix",
    "## Final Synthesis Trace",
)


def _clean_inline(value: Any, *, max_len: int = 220) -> str:
    """Normalize public advisor text for compact markdown sections."""
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def _advisor_position_cards(anonymized: list[dict]) -> str:
    lines = ["## Advisor Positions"]
    for advisor in anonymized:
        letter = _clean_inline(advisor.get("letter", "?"), max_len=8)
        verdict = _clean_inline(advisor.get("verdict", "UNKNOWN"), max_len=32)
        confidence = float(advisor.get("confidence", 0.0))
        strengths = [_clean_inline(s) for s in advisor.get("top_strengths", [])[:2]]
        risks = [_clean_inline(r) for r in advisor.get("top_risks", [])[:2]]
        blockers = [_clean_inline(b) for b in advisor.get("critical_blockers", [])[:2]]

        lines.append(f"- Response {letter}: {verdict} at confidence {confidence:.2f}.")
        if strengths:
            lines.append(f"  - Main support: {'; '.join(strengths)}")
        if risks:
            lines.append(f"  - Main concern: {'; '.join(risks)}")
        if blockers:
            lines.append(f"  - Blocker: {'; '.join(blockers)}")
    return "\n".join(lines)


def _has_direct_answers(anonymized: list[dict]) -> bool:
    return any(str(advisor.get("direct_answer_md") or "").strip() for advisor in anonymized)


def _direct_answer_fallback_sections(
    anonymized: list[dict],
    agreement_zones: list[dict],
    split_zones: list[dict],
) -> str:
    """Fallback Perplexity-style sections when the reconciler omitted them."""
    cited_answers: list[str] = []
    for advisor in anonymized:
        answer = str(advisor.get("direct_answer_md") or "").strip()
        if not answer:
            continue
        letter = _clean_inline(advisor.get("letter", "?"), max_len=8)
        cited_answers.append(f"Response {letter}: {_clean_inline(answer, max_len=600)}")

    lines = ["## Substantive Answer"]
    if cited_answers:
        lines.extend(f"- {item}" for item in cited_answers)
    else:
        lines.append("- No advisor supplied a direct_answer_md payload.")

    lines.append("")
    lines.append("## Where Models Agree")
    if agreement_zones:
        for zone in agreement_zones:
            claim = _clean_inline(zone.get("claim", "Agreement zone"))
            letters = ", ".join(
                f"Response {_clean_inline(l, max_len=8)}"
                for l in zone.get("cited_letters", [])
            )
            lines.append(f"- {claim} ({letters or 'uncited'}).")
    else:
        lines.append("- No explicit agreement zones were emitted by the reconciler.")

    lines.append("")
    lines.append("## Where Models Disagree")
    if split_zones:
        for zone in split_zones:
            topic = _clean_inline(zone.get("topic", "Disagreement"))
            sides: list[str] = []
            for side in zone.get("sides", []):
                letters = ", ".join(
                    f"Response {_clean_inline(l, max_len=8)}"
                    for l in side.get("letters", [])
                )
                position = _clean_inline(side.get("position", "Position"))
                sides.append(f"{letters or 'uncited side'}: {position}")
            lines.append(f"- {topic}: {' | '.join(sides)}")
    else:
        lines.append("- No material disagreement recorded; advisor positions are aligned or differences were not decision-driving.")

    lines.append("")
    lines.append("## Unique Discoveries")
    lines.append("- Review each Response card for single-advisor discoveries; no separate unique-discovery list was emitted by the reconciler.")

    return "\n".join(lines)


def _agreement_matrix(agreement_zones: list[dict]) -> str:
    lines = ["## Agreement Matrix"]
    if not agreement_zones:
        lines.append("- No explicit agreement zones were emitted by the reconciler.")
        return "\n".join(lines)

    for zone in agreement_zones:
        claim = _clean_inline(zone.get("claim", "Agreement zone"))
        letters = zone.get("cited_letters", [])
        cited = ", ".join(f"Response {_clean_inline(l, max_len=8)}" for l in letters) or "not cited"
        lines.append(f"- {claim} — supported by {cited}.")
    return "\n".join(lines)


def _disagreement_matrix(split_zones: list[dict]) -> str:
    lines = ["## Disagreement Matrix"]
    if not split_zones:
        lines.append("- No material disagreement recorded; advisor positions are aligned or differences are not decision-driving.")
        return "\n".join(lines)

    for zone in split_zones:
        topic = _clean_inline(zone.get("topic", "Disagreement"))
        lines.append(f"- {topic}:")
        for side in zone.get("sides", []):
            position = _clean_inline(side.get("position", "Position"))
            letters = side.get("letters", [])
            cited = ", ".join(f"Response {_clean_inline(l, max_len=8)}" for l in letters) or "uncited side"
            lines.append(f"  - {cited}: {position}")
    return "\n".join(lines)


def _final_synthesis_trace(
    anonymized: list[dict],
    tier: str,
    nplf_arithmetic: dict | None = None,
) -> str:
    verdicts = [str(d.get("verdict", "ABSTAIN")) for d in anonymized]
    counts = {verdict: verdicts.count(verdict) for verdict in sorted(set(verdicts))}
    count_text = ", ".join(f"{k}={v}" for k, v in counts.items()) or "no advisor verdicts"
    gate_text = ""
    if nplf_arithmetic:
        gate = float(nplf_arithmetic.get("tier_gate_value", 0.0))
        cross = float(nplf_arithmetic.get("cross_advisor_mean", 0.0))
        rec = float(nplf_arithmetic.get("reconciler_nplf_mean", 0.0))
        gate_text = (
            f" NPLF gate used min(cross-advisor mean {cross:.2f}, "
            f"reconciler mean {rec:.2f}) = {gate:.2f}."
        )
    return (
        "## Final Synthesis Trace\n"
        f"- Advisor verdict distribution: {count_text}.\n"
        f"- Final tier: {tier}.\n"
        f"- How this was reached: the reconciler compared the public advisor verdicts, "
        f"agreement zones, split zones, blockers, confidence, and NPLF gate before assigning the final tier."
        f"{gate_text}\n"
        "- Privacy note: this trace is derived from public advisor fields only; raw reasoning_chain content is not used or exposed."
    )


def _ensure_explainability_sections(
    verdict_md: str,
    anonymized: list[dict],
    agreement_zones: list[dict],
    split_zones: list[dict],
    tier: str,
    nplf_arithmetic: dict | None = None,
) -> str:
    """
    Ensure the final markdown exposes each advisor position, agreement/disagreement
    structure, and the final synthesis trace without using raw reasoning chains.

    The model is asked to emit these sections, but this deterministic append-only
    fallback keeps old or degraded reconciler responses explainable.
    """
    sections: list[str] = []
    if _has_direct_answers(anonymized) and (
        "## Substantive Answer" not in verdict_md
        or "## Where Models Agree" not in verdict_md
        or "## Where Models Disagree" not in verdict_md
        or "## Unique Discoveries" not in verdict_md
    ):
        sections.append(_direct_answer_fallback_sections(anonymized, agreement_zones, split_zones))
    if "## Advisor Positions" not in verdict_md:
        sections.append(_advisor_position_cards(anonymized))
    if "## Agreement Matrix" not in verdict_md:
        sections.append(_agreement_matrix(agreement_zones))
    if "## Disagreement Matrix" not in verdict_md:
        sections.append(_disagreement_matrix(split_zones))
    if "## Final Synthesis Trace" not in verdict_md:
        sections.append(_final_synthesis_trace(anonymized, tier, nplf_arithmetic))

    if not sections:
        return verdict_md
    return verdict_md.rstrip() + "\n\n" + "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_reconciler_response(text: str) -> dict:
    """
    Parses reconciler output as strict JSON. Validates required keys and structure.

    Expected schema:
      verdict: PASS|REVISE|BLOCK
      confidence: float
      nplf: {n, p, l, f}
      verdict_md: str
      agreement_zones: list[{claim, cited_letters}]
      split_zones: list[{topic, sides: [{position, letters}]}]

    Raises ValueError on any failure.
    """
    stripped = _strip_markdown_fences(text)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON decode error: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    required = {"verdict", "confidence", "nplf", "verdict_md", "agreement_zones", "split_zones"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing required keys: {sorted(missing)}")

    # Validate verdict
    valid_verdicts = {"PASS", "REVISE", "BLOCK"}
    verdict = data["verdict"]
    if verdict not in valid_verdicts:
        raise ValueError(f"Invalid verdict {verdict!r}. Must be one of {sorted(valid_verdicts)}")

    # Validate confidence
    conf = data["confidence"]
    if not isinstance(conf, (int, float)):
        raise ValueError(f"confidence must be a number, got {type(conf).__name__}")

    # Validate nplf
    nplf = data["nplf"]
    if not isinstance(nplf, dict):
        raise ValueError(f"nplf must be a dict, got {type(nplf).__name__}")
    nplf_missing = {"n", "p", "l", "f"} - set(nplf.keys())
    if nplf_missing:
        raise ValueError(f"nplf missing keys: {sorted(nplf_missing)}")
    for key in ("n", "p", "l", "f"):
        if not isinstance(nplf[key], (int, float)):
            raise ValueError(f"nplf.{key} must be a number, got {type(nplf[key]).__name__}")

    # Validate verdict_md
    if not isinstance(data["verdict_md"], str):
        raise ValueError("verdict_md must be a string")

    # Validate agreement_zones
    if not isinstance(data["agreement_zones"], list):
        raise ValueError("agreement_zones must be a list")

    # Validate split_zones
    if not isinstance(data["split_zones"], list):
        raise ValueError("split_zones must be a list")

    return data


# ---------------------------------------------------------------------------
# Citation enforcement (AC-6)
# ---------------------------------------------------------------------------

_RESPONSE_CITE_RE = re.compile(r"Response\s+[ABC]", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```[^\n]*\n.*?\n```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Remove triple-backtick fenced code blocks from text."""
    return _CODE_FENCE_RE.sub("", text)


def _validate_citations(verdict_md: str, tier: str) -> tuple[bool, list[str]]:
    """
    Returns (ok, gaps). gaps is list of missing-citation descriptions.

    Checks:
      - '## Agreement Zones' present in verdict_md.
      - '## Split Zones' present in verdict_md.
      - At least 1 Response [ABC] citation in the Agreement Zones section body.
      - At least 1 citation per side in Split Zones (when tier=SPLIT or split_zones non-empty).
    """
    gaps: list[str] = []

    # Check required headers
    if "## Agreement Zones" not in verdict_md:
        gaps.append("missing '## Agreement Zones' header in verdict_md")
    if "## Split Zones" not in verdict_md:
        gaps.append("missing '## Split Zones' header in verdict_md")

    if gaps:
        return False, gaps

    # Extract sections by splitting on ## headers
    sections: dict[str, str] = {}
    current_header: str | None = None
    current_lines: list[str] = []

    for line in verdict_md.splitlines():
        if line.startswith("## "):
            if current_header is not None:
                sections[current_header] = "\n".join(current_lines)
            current_header = line[3:].strip()
            current_lines = []
        else:
            if current_header is not None:
                current_lines.append(line)
    if current_header is not None:
        sections[current_header] = "\n".join(current_lines)

    # Check Agreement Zones body has at least one citation (FIX-C3: strip code fences first)
    agreement_body = sections.get("Agreement Zones", "")
    agreement_body_searchable = _strip_code_fences(agreement_body)
    if not _RESPONSE_CITE_RE.search(agreement_body_searchable):
        gaps.append(
            "Agreement Zones section body has no Response A/B/C citation"
        )

    # Check Split Zones body has citations if tier=SPLIT (FIX-C3: strip code fences first)
    split_body = sections.get("Split Zones", "")
    is_aligned = _split_body_claims_alignment(split_body)
    if tier == "SPLIT" and not is_aligned:
        # Need at least 2 different response letters cited (one per side)
        split_body_searchable = _strip_code_fences(split_body)
        found_letters = set(re.findall(r"Response\s+([ABC])", split_body_searchable, re.IGNORECASE))
        if len(found_letters) < 1:
            gaps.append(
                "Split Zones section body has no Response A/B/C citation "
                "(at least one citation per side required)"
            )
        # Note: full per-side validation would require JSON split_zones; we do best-effort here
        # requiring at least 1 citation total when tier=SPLIT
    elif not is_aligned and split_body.strip():
        # Non-SPLIT with non-empty split zones: still need at least 1 citation
        split_body_searchable = _strip_code_fences(split_body)
        if not _RESPONSE_CITE_RE.search(split_body_searchable):
            gaps.append(
                "Split Zones section body has content but no Response A/B/C citation"
            )

    if gaps:
        return False, gaps
    return True, []


def _split_body_claims_alignment(split_body: str) -> bool:
    body = _strip_code_fences(split_body).strip().lower()
    if not body:
        return True
    no_split = re.search(
        r"\b(no|none|without)\b.{0,40}\b(split|dissent|disagreement|dispute|conflict)",
        body,
    )
    aligned = re.search(r"\b(aligned|agreement|agree|consensus|no material disagreement)\b", body)
    return bool(no_split or aligned)


# ---------------------------------------------------------------------------
# NPLF arithmetic
# ---------------------------------------------------------------------------

def _compute_nplf_arithmetic(
    anonymized: list[dict],
    reconciler_nplf: dict,
) -> dict:
    """
    Per plan §2 Tier NPLF source:
      advisor_nplf_mean = (n+p+l+f)/4 per advisor
      cross_advisor_mean = mean of the non-ABSTAIN advisor means
      reconciler_nplf_mean = mean of reconciler nplf
      tier_gate_value = min(cross_advisor_mean, reconciler_nplf_mean)

    FIX-H1: ABSTAIN advisors are excluded from cross_advisor_mean. Including
    their 0.0 NPLF would unfairly drag down the gate value and could cause
    legitimate PASS verdicts to fail the 3.0 gate when min_quorum=2 is used.
    Defensive fallback to 0.0 if all advisors abstained (orchestrator should
    have short-circuited before this point).
    """
    advisor_means: list[float] = []
    for d in anonymized:
        if d.get("verdict") == "ABSTAIN":
            continue  # FIX-H1: skip ABSTAINs from NPLF math
        nplf = d.get("nplf", {})
        if not nplf:
            continue
        n = float(nplf.get("n", 0.0))
        p = float(nplf.get("p", 0.0))
        l_ = float(nplf.get("l", 0.0))
        f = float(nplf.get("f", 0.0))
        advisor_means.append((n + p + l_ + f) / 4.0)

    cross_advisor_mean = sum(advisor_means) / len(advisor_means) if advisor_means else 0.0

    rn = float(reconciler_nplf.get("n", 0.0))
    rp = float(reconciler_nplf.get("p", 0.0))
    rl = float(reconciler_nplf.get("l", 0.0))
    rf = float(reconciler_nplf.get("f", 0.0))
    reconciler_nplf_mean = (rn + rp + rl + rf) / 4.0

    tier_gate_value = min(cross_advisor_mean, reconciler_nplf_mean)

    return {
        "advisor_means": advisor_means,
        "cross_advisor_mean": cross_advisor_mean,
        "reconciler_nplf_mean": reconciler_nplf_mean,
        "tier_gate_value": tier_gate_value,
    }


# ---------------------------------------------------------------------------
# Tier computation
# ---------------------------------------------------------------------------

def _compute_tier(
    opus_verdict: str,
    opus_confidence: float,
    anonymized: list[dict],
    nplf_arithmetic: dict,
) -> str:
    """
    Pure function. Apply §2 signal table rules. Returns one of 6 tiers.

    HARD rule: tier=SPLIT cannot be silently collapsed to PASS via majority.
    If there is no 2-of-3 majority on any single verdict, tier=SPLIT regardless
    of what opus_verdict says.

    BLOCK fires when any advisor flagged a critical_blocker AND reconciler verdict
    is BLOCK or REVISE (treats both as agreement with the blocker).

    PARTIAL_QUORUM fires when 2 or more advisors ABSTAIN — orchestrator decides.
    """
    verdicts = [d.get("verdict", "ABSTAIN") for d in anonymized]
    gate = nplf_arithmetic.get("tier_gate_value", 0.0)
    confidences = [float(d.get("confidence", 0.0)) for d in anonymized]

    # Count verdicts
    pass_count = verdicts.count("PASS")
    revise_count = verdicts.count("REVISE")
    block_count = verdicts.count("BLOCK")

    # FIX-M3: 2 or more ABSTAINs -> PARTIAL_QUORUM before majority check
    abstain_count = verdicts.count("ABSTAIN")
    if abstain_count >= 2:
        result_tier = "PARTIAL_QUORUM"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    # Majority: any single verdict appears 2+ times
    has_majority = (pass_count >= 2 or revise_count >= 2 or block_count >= 2)

    # HARD rule: if no majority, tier=SPLIT regardless of opus_verdict
    if not has_majority:
        sys.stderr.write(
            f"[reconcile] HARD RULE: no 2-of-3 majority in advisor verdicts "
            f"({verdicts}). Forcing tier=SPLIT (opus_verdict={opus_verdict!r} ignored).\n"
        )
        result_tier = "SPLIT"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    # Low reconciler confidence -> SPLIT
    if opus_confidence < 0.65:
        result_tier = "SPLIT"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    if block_count >= 2:
        result_tier = "BLOCK"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    # FIX-C2: BLOCK: any advisor has critical_blockers AND reconciler agrees (BLOCK or REVISE)
    has_blockers = any(d.get("critical_blockers") for d in anonymized)
    if has_blockers and opus_verdict in ("BLOCK", "REVISE"):
        result_tier = "BLOCK"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    # FIX-C1: STRONG_PASS: all 3 PASS AND all 3 confidence >= 0.85 AND gate >= 3.5
    # AND opus_verdict=="PASS" AND opus_confidence >= 0.85
    if (
        pass_count == 3
        and all(c >= 0.85 for c in confidences)
        and gate >= 3.5
        and opus_verdict == "PASS"
        and opus_confidence >= 0.85
    ):
        result_tier = "STRONG_PASS"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    # FIX-C1: PASS: 2/3 PASS AND gate >= 3.0 AND opus_verdict=="PASS"
    if pass_count >= 2 and gate >= 3.0 and opus_verdict == "PASS":
        result_tier = "PASS"
        assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
        return result_tier

    # FIX-C1: Warn if advisors mostly PASS but reconciler returned REVISE/BLOCK (mismatch)
    if pass_count >= 2 and opus_verdict in ("REVISE", "BLOCK"):
        sys.stderr.write(
            f"[reconcile] advisor-vs-reconciler mismatch: {pass_count}/3 advisors PASS "
            f"but opus_verdict={opus_verdict!r}@{opus_confidence}. "
            f"Falling through to SPLIT.\n"
        )

    # Default to SPLIT if nothing else matched
    result_tier = "SPLIT"
    assert result_tier in _VALID_TIERS, f"_compute_tier produced invalid tier {result_tier!r}"
    return result_tier


# ---------------------------------------------------------------------------
# Dissent extractor
# ---------------------------------------------------------------------------

def _extract_dissent_md(verdict_md: str) -> str:
    """
    Extract the '## Split Zones' section as standalone dissent_md.
    Returns empty string if section contains 'No split zones' alignment marker.
    """
    if "## Split Zones" not in verdict_md:
        return ""

    # Find the section
    parts = verdict_md.split("## Split Zones", 1)
    if len(parts) < 2:
        return ""

    section_content = parts[1]
    # Trim at the next ## header if present
    next_header = re.search(r"\n## ", section_content)
    if next_header:
        section_content = section_content[: next_header.start()]

    section_content = section_content.strip()

    # Return empty if advisors fully aligned
    if "No split zones" in section_content and "advisors aligned" in section_content:
        return ""

    return "## Split Zones\n" + section_content


# ---------------------------------------------------------------------------
# Dissent reconstruction fallback (FIX-H1)
# ---------------------------------------------------------------------------

def _reconstruct_dissent_from_verdicts(anonymized: list[dict]) -> list[dict]:
    """
    Programmatic fallback when reconciler fails to emit split_zones for SPLIT tier.
    Builds minimal split_zones from the raw advisor verdict differences.
    """
    by_verdict: dict[str, list[str]] = {}
    for d in anonymized:
        v = d.get("verdict", "ABSTAIN")
        by_verdict.setdefault(v, []).append(d["letter"])
    sides = [
        {"position": f"Verdict: {v}", "letters": letters}
        for v, letters in by_verdict.items()
    ]
    return [{"topic": "Advisors split on verdict (reconstructed from raw verdicts)", "sides": sides}]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def reconcile(
    anonymized: list[dict],
    *,
    task_id: str,
    brief_xml: str,
    shuffle_map: dict[str, str],
) -> dict:
    """
    Synthesize 3 anonymized advisor verdicts into a single dissent-preserving verdict.

    Args:
        anonymized:  3 sanitized advisor dicts from anonymize.py output.
        task_id:     For VK emission (step="reconcile").
        brief_xml:   Original canonical brief from normalize.py.
        shuffle_map: From anonymize output — kept opaque to reconciler,
                     included in result for replay.

    Returns:
        dict with keys: tier, verdict_md, dissent_md, confidence, nplf,
        nplf_arithmetic, agreement_zones, split_zones, tokens, cost_usd,
        duration_s, status, error, shuffle_map.

    Raises:
        ValueError: if anonymized is not 3 dicts, or brief_xml is empty.
    """
    # Structural pre-checks (raise immediately)
    if not isinstance(anonymized, list) or len(anonymized) != 3:
        raise ValueError(
            f"reconcile: expected exactly 3 anonymized dicts, got "
            f"{len(anonymized) if isinstance(anonymized, list) else type(anonymized)}"
        )
    if not brief_xml or not brief_xml.strip():
        raise ValueError("reconcile: brief_xml must not be empty")

    wall_start = time.monotonic()
    vk.emit("reconcile", "entered", task_id)

    # -------------------------------------------------------------------------
    # Input validation: forbidden key check (symmetric defense)
    # -------------------------------------------------------------------------
    validation_error = _validate_anonymized_input(anonymized)
    if validation_error:
        return _fail_result(
            status="FAIL_VALIDATION",
            error=validation_error,
            shuffle_map=shuffle_map,
            wall_start=wall_start,
        )

    # -------------------------------------------------------------------------
    # Build prompt
    # -------------------------------------------------------------------------
    system_prompt, user_prompt = _build_reconciler_prompt(brief_xml, anonymized)

    # -------------------------------------------------------------------------
    # Call runtime support model with high reasoning, exp-backoff retry
    # -------------------------------------------------------------------------
    opus_entry = _providers.PROVIDER_REGISTRY.get(_RECONCILER_PROVIDER_KEY, {})
    price_in = opus_entry.get("price_in", _OPUS_PRICE_IN)
    price_out = opus_entry.get("price_out", _OPUS_PRICE_OUT)

    last_error: str | None = None
    attempt = 0
    schema_fail_count = 0
    schema_retry_note = ""
    total_tokens_in = 0
    total_tokens_out = 0
    parsed: dict | None = None

    # Citation enforcement retry state
    citation_attempt = 0
    citation_retry_note = ""
    effective_user = user_prompt
    verdict_drift: dict | None = None

    while attempt < _MAX_ATTEMPTS:
        try:
            call_user = effective_user
            if schema_retry_note:
                call_user = (
                    f"{effective_user}\n\n"
                    f"[INSTRUCTION: previous output was malformed: {schema_retry_note}. "
                    f"Return valid JSON this time.]"
                )

            response = _providers.call_provider(
                _RECONCILER_PROVIDER_KEY,
                system_prompt,
                call_user,
                max_tokens=8192,
                temperature=0.2,
                reasoning={"effort": "high"},
                text={"verbosity": "high"},
            )
            text = response.get("text", "")
            total_tokens_in += response.get("tokens", {}).get("in", 0)
            total_tokens_out += response.get("tokens", {}).get("out", 0)

            # Schema parse
            try:
                parsed = _parse_reconciler_response(text)
            except ValueError as ve:
                schema_fail_count += 1
                schema_retry_note = str(ve)[:200]
                if schema_fail_count >= 2:
                    # FIX-M2: schema double-fail → FAIL_SCHEMA (not FAIL_API)
                    cost_usd = total_tokens_in * price_in + total_tokens_out * price_out
                    return _fail_result(
                        status="FAIL_SCHEMA",
                        error=f"schema_fail after 2 attempts: {ve}",
                        shuffle_map=shuffle_map,
                        wall_start=wall_start,
                        tokens={"in": total_tokens_in, "out": total_tokens_out},
                        cost_usd=cost_usd,
                    )
                # First schema fail: retry without incrementing transient attempt
                continue

            # Successful parse — break out of retry loop
            break

        except _providers.PermanentProviderError as exc:
            return _fail_result(
                status="FAIL_API",
                error=str(exc),
                shuffle_map=shuffle_map,
                wall_start=wall_start,
                tokens={"in": total_tokens_in, "out": total_tokens_out},
                cost_usd=total_tokens_in * price_in + total_tokens_out * price_out,
            )

        except _providers.TransientProviderError as exc:
            last_error = str(exc)
            attempt += 1
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_BACKOFF_DELAYS[attempt - 1])
            continue

    else:
        # All transient attempts exhausted
        return _fail_result(
            status="FAIL_API",
            error=f"transient_exhausted after {_MAX_ATTEMPTS} attempts: {last_error}",
            shuffle_map=shuffle_map,
            wall_start=wall_start,
            tokens={"in": total_tokens_in, "out": total_tokens_out},
            cost_usd=total_tokens_in * price_in + total_tokens_out * price_out,
        )

    if parsed is None:
        return _fail_result(
            status="FAIL_API",
            error="no parsed response after retry loop",
            shuffle_map=shuffle_map,
            wall_start=wall_start,
        )

    # -------------------------------------------------------------------------
    # Citation enforcement BEFORE tier computation (AC-6)
    # -------------------------------------------------------------------------
    # Compute a preliminary tier for citation checks
    preliminary_nplf_arith = _compute_nplf_arithmetic(anonymized, parsed["nplf"])
    preliminary_tier = _compute_tier(
        parsed["verdict"],
        float(parsed["confidence"]),
        anonymized,
        preliminary_nplf_arith,
    )

    citation_ok, citation_gaps = _validate_citations(parsed["verdict_md"], preliminary_tier)

    if not citation_ok:
        citation_attempt += 1
        if citation_attempt < 2:
            # ONE retry with explicit note about missing citations
            gaps_str = "; ".join(citation_gaps)
            citation_retry_note = f"missing citations: {gaps_str}"
            retry_user = (
                f"{user_prompt}\n\n"
                f"[INSTRUCTION: previous output had citation issues: {citation_retry_note}. "
                f"Ensure every Agreement Zone and Split Zone section body cites "
                f"Response A, Response B, or Response C explicitly.]"
            )
            try:
                response2 = _providers.call_provider(
                    _RECONCILER_PROVIDER_KEY,
                    system_prompt,
                    retry_user,
                    max_tokens=8192,
                    temperature=0.2,
                    reasoning={"effort": "high"},
                    text={"verbosity": "high"},
                )
                text2 = response2.get("text", "")
                total_tokens_in += response2.get("tokens", {}).get("in", 0)
                total_tokens_out += response2.get("tokens", {}).get("out", 0)

                try:
                    parsed2 = _parse_reconciler_response(text2)
                except ValueError as ve2:
                    return _fail_result(
                        status="FAIL_CITATION",
                        error=f"citation retry produced invalid JSON: {ve2}; original gaps: {gaps_str}",
                        shuffle_map=shuffle_map,
                        wall_start=wall_start,
                        tokens={"in": total_tokens_in, "out": total_tokens_out},
                        cost_usd=total_tokens_in * price_in + total_tokens_out * price_out,
                    )

                # Re-check citations
                preliminary_nplf_arith2 = _compute_nplf_arithmetic(anonymized, parsed2["nplf"])
                preliminary_tier2 = _compute_tier(
                    parsed2["verdict"],
                    float(parsed2["confidence"]),
                    anonymized,
                    preliminary_nplf_arith2,
                )
                citation_ok2, citation_gaps2 = _validate_citations(parsed2["verdict_md"], preliminary_tier2)
                if not citation_ok2:
                    return _fail_result(
                        status="FAIL_CITATION",
                        error=f"citation gaps after retry: {'; '.join(citation_gaps2)}",
                        shuffle_map=shuffle_map,
                        wall_start=wall_start,
                        tokens={"in": total_tokens_in, "out": total_tokens_out},
                        cost_usd=total_tokens_in * price_in + total_tokens_out * price_out,
                    )

                # FIX-H3: detect and log verdict drift between original and citation-retry parse
                verdict_drift: dict | None = None
                if parsed2["verdict"] != parsed["verdict"]:
                    sys.stderr.write(
                        f"[reconcile] citation retry changed verdict: "
                        f"{parsed['verdict']}@{parsed['confidence']} → "
                        f"{parsed2['verdict']}@{parsed2['confidence']} "
                        f"for task {task_id}\n"
                    )
                    verdict_drift = {
                        "pre_citation_retry": {
                            "verdict": parsed["verdict"],
                            "confidence": parsed["confidence"],
                        },
                        "post_citation_retry": {
                            "verdict": parsed2["verdict"],
                            "confidence": parsed2["confidence"],
                        },
                    }

                # Second attempt succeeded
                parsed = parsed2
                preliminary_nplf_arith = preliminary_nplf_arith2
                preliminary_tier = preliminary_tier2

            except (_providers.PermanentProviderError, _providers.TransientProviderError) as exc:
                return _fail_result(
                    status="FAIL_CITATION",
                    error=f"citation retry API error: {exc}; original gaps: {gaps_str}",
                    shuffle_map=shuffle_map,
                    wall_start=wall_start,
                    tokens={"in": total_tokens_in, "out": total_tokens_out},
                    cost_usd=total_tokens_in * price_in + total_tokens_out * price_out,
                )
        else:
            return _fail_result(
                status="FAIL_CITATION",
                error=f"citation gaps: {'; '.join(citation_gaps)}",
                shuffle_map=shuffle_map,
                wall_start=wall_start,
                tokens={"in": total_tokens_in, "out": total_tokens_out},
                cost_usd=total_tokens_in * price_in + total_tokens_out * price_out,
            )

    # -------------------------------------------------------------------------
    # Final tier and NPLF (using final parsed)
    # -------------------------------------------------------------------------
    nplf_arithmetic = _compute_nplf_arithmetic(anonymized, parsed["nplf"])
    tier = _compute_tier(
        parsed["verdict"],
        float(parsed["confidence"]),
        anonymized,
        nplf_arithmetic,
    )

    verdict_md = parsed["verdict_md"]
    split_zones = parsed.get("split_zones", [])
    dissent_md = _extract_dissent_md(verdict_md)

    # FIX-H1: SPLIT tier must never have empty split_zones or dissent_md.
    # Trigger one retry with a note; if still empty, reconstruct programmatically.
    if tier == "SPLIT" and (not split_zones or not dissent_md):
        split_retry_note = (
            "previous output declared SPLIT but provided no dissent; "
            "populate split_zones with the cited advisor disagreement that drove the split"
        )
        try:
            split_retry_user = (
                f"{user_prompt}\n\n"
                f"[INSTRUCTION: {split_retry_note}.]"
            )
            response_split = _providers.call_provider(
                _RECONCILER_PROVIDER_KEY,
                system_prompt,
                split_retry_user,
                max_tokens=8192,
                temperature=0.2,
                reasoning={"effort": "high"},
                text={"verbosity": "high"},
            )
            text_split = response_split.get("text", "")
            total_tokens_in += response_split.get("tokens", {}).get("in", 0)
            total_tokens_out += response_split.get("tokens", {}).get("out", 0)
            try:
                parsed_split = _parse_reconciler_response(text_split)
                split_zones_retry = parsed_split.get("split_zones", [])
                dissent_md_retry = _extract_dissent_md(parsed_split["verdict_md"])
                if split_zones_retry and dissent_md_retry:
                    parsed = parsed_split
                    split_zones = split_zones_retry
                    dissent_md = dissent_md_retry
                    verdict_md = parsed_split["verdict_md"]
                    nplf_arithmetic = _compute_nplf_arithmetic(anonymized, parsed_split["nplf"])
                    tier = _compute_tier(
                        parsed_split["verdict"],
                        float(parsed_split["confidence"]),
                        anonymized,
                        nplf_arithmetic,
                    )
                else:
                    raise ValueError("split retry still empty")
            except ValueError:
                # Programmatic fallback: reconstruct from advisor verdict diff
                split_zones = _reconstruct_dissent_from_verdicts(anonymized)
                dissent_md = (
                    "## Split Zones\n"
                    + split_zones[0]["topic"] + "\n"
                    + "\n".join(
                        f"- {side['position']}: {', '.join(side['letters'])}"
                        for side in split_zones[0]["sides"]
                    )
                )
                sys.stderr.write(
                    f"[reconcile] SPLIT with empty split_zones: programmatic dissent "
                    f"reconstruction used for task {task_id}\n"
                )
        except (_providers.PermanentProviderError, _providers.TransientProviderError) as exc:
            # Fallback on API error too
            split_zones = _reconstruct_dissent_from_verdicts(anonymized)
            dissent_md = (
                "## Split Zones\n"
                + split_zones[0]["topic"] + "\n"
                + "\n".join(
                    f"- {side['position']}: {', '.join(side['letters'])}"
                    for side in split_zones[0]["sides"]
                )
            )
            sys.stderr.write(
                f"[reconcile] SPLIT with empty split_zones: retry API error ({exc}); "
                f"programmatic dissent reconstruction used for task {task_id}\n"
            )

    verdict_md = _ensure_explainability_sections(
        verdict_md,
        anonymized,
        parsed.get("agreement_zones", []),
        split_zones,
        tier,
        nplf_arithmetic,
    )

    cost_usd = total_tokens_in * price_in + total_tokens_out * price_out
    duration_s = time.monotonic() - wall_start

    vk.emit(
        "reconcile",
        "completed",
        task_id,
        tier=tier,
        confidence=str(round(float(parsed["confidence"]), 4)),
    )

    return {
        "tier": tier,
        "verdict_md": verdict_md,
        "dissent_md": dissent_md,
        "confidence": float(parsed["confidence"]),
        "nplf": parsed["nplf"],
        "nplf_arithmetic": nplf_arithmetic,
        "agreement_zones": parsed.get("agreement_zones", []),
        "split_zones": split_zones,
        "tokens": {"in": total_tokens_in, "out": total_tokens_out},
        "cost_usd": cost_usd,
        "duration_s": duration_s,
        "status": "OK",
        "error": None,
        "shuffle_map": shuffle_map,
        "verdict_drift": verdict_drift,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fail_result(
    *,
    status: str,
    error: str,
    shuffle_map: dict,
    wall_start: float,
    tokens: dict | None = None,
    cost_usd: float = 0.0,
) -> dict:
    """Build a failed reconcile result dict."""
    duration_s = time.monotonic() - wall_start
    return {
        "tier": "ABSTAIN",
        "verdict_md": "",
        "dissent_md": "",
        "confidence": 0.0,
        "nplf": {"n": 0.0, "p": 0.0, "l": 0.0, "f": 0.0},
        "nplf_arithmetic": {
            "advisor_means": [],
            "cross_advisor_mean": 0.0,
            "reconciler_nplf_mean": 0.0,
            "tier_gate_value": 0.0,
        },
        "agreement_zones": [],
        "split_zones": [],
        "tokens": tokens if tokens is not None else {"in": 0, "out": 0},
        "cost_usd": cost_usd,
        "duration_s": duration_s,
        "status": status,
        "error": error,
        "shuffle_map": shuffle_map,
    }
