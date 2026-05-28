"""
test_live_smoke.py — Live integration smoke test for /council.

Gated behind COUNCIL_LIVE_TESTS=1 env var. Never runs in normal CI.
Requires: Codex OAuth, claude CLI, and GEMINI_API_KEY in env.

Runs a minimal /council invocation against real Codex OAuth, Anthropic OAuth,
and Gemini API paths to validate the actual provider chain end-to-end.
"""
import os
import pytest
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

LIVE = os.environ.get("COUNCIL_LIVE_TESTS") == "1"


@pytest.mark.skipif(not LIVE, reason="COUNCIL_LIVE_TESTS=1 not set")
@pytest.mark.live
class TestLiveSmoke:

    def test_triage_live(self):
        """Triage classifies a real text via Codex OAuth / GPT-5.5."""
        from lib.triage import triage
        result = triage(
            "Should we add a staging environment before prod deploys?",
            threshold=10,  # low threshold so it proceeds
            task_id="live-smoke-triage-001",
        )
        # Just verify it didn't crash and returned a valid structure
        assert result["verdict"] in ("PROCEED", "PROCEED_FORCED", "REFUSE")
        assert isinstance(result["score"], int)

    def test_normalize_live(self):
        """Normalizer produces valid council_brief XML via Codex OAuth / GPT-5.5."""
        from lib.normalize import normalize
        result = normalize(
            "Should we migrate the LIS bot to a new VPS?",
            task_id="live-smoke-normalize-001",
        )
        assert result["verdict"] == "OK"
        assert result["brief_xml"] is not None
        assert "<council_brief>" in result["brief_xml"]
        assert "<goal>" in result["brief_xml"]

    def test_full_pipeline_quick_depth(self):
        """Full pipeline at --depth quick on a trivial brief."""
        from lib.orchestrator import run_council
        result = run_council(
            target="Should we use tabs or spaces in new Python files?",
            depth="quick",
            force=True,  # bypass triage for speed
            min_quorum=2,  # allow partial if one lane unavailable
            keep_chains=False,
            no_debate=True,
        )
        # Must complete without exception and return a tier
        assert result.get("tier") in ("PASS", "CONDITIONAL", "BLOCK", "UNAVAILABLE")
        assert result.get("council_task_id") is not None
