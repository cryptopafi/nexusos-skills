"""
test_ledger.py — 14 pytest cases for lib/ledger.py

Covers: filesystem (5), sink resilience (4), Cortex payload (2),
        purge (2), status (1).

NO real network calls — all remote sinks are monkeypatched.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat
import time
from unittest.mock import MagicMock

import pytest

from lib.ledger import (
    _ac12_grep_check,
    _default_council_base,
    _default_secrets_path,
    _load_telegram_config,
    _purge_old_chains,
    _purge_old_workspaces,
    write_ledger,
)
import lib.ledger as ledger_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
ADVISOR_WITH_CHAIN = {
    "label": "Advisor",
    "recommendation": "Buy",
    "confidence": 0.9,
    "reasoning_chain": ["step1: consider X", "step2: conclude Y"],
}

ADVISOR_NO_CHAIN = {
    "label": "Advisor",
    "recommendation": "Buy",
    "confidence": 0.9,
}

RECONCILER = {
    "tier": "STRONG_PASS",
    "verdict_md": "## Verdict\nAll advisors agree.",
    "dissent_md": "No dissent.",
    "confidence": 0.92,
}

RECONCILER_PASS = {
    "tier": "PASS",
    "verdict_md": "## Verdict\nAdvisors mostly agree.",
    "dissent_md": "",
    "confidence": 0.75,
}

SHUFFLE_MAP = {"A": 0, "B": 1, "C": 2}

BASE_KWARGS = dict(
    task_id="nx-test-001",
    council_task_id="council-20260519-1200-TEST",
    brief_xml="<brief>Test brief</brief>",
    advisor_results=[ADVISOR_WITH_CHAIN.copy(), ADVISOR_WITH_CHAIN.copy(), ADVISOR_WITH_CHAIN.copy()],
    anonymized=[ADVISOR_NO_CHAIN.copy(), ADVISOR_NO_CHAIN.copy(), ADVISOR_NO_CHAIN.copy()],
    shuffle_map=SHUFFLE_MAP,
    seed=42,
    reconciler_result=RECONCILER.copy(),
    debate_result=None,
    cost_meter_total=1.23,
)


def _mock_sinks(monkeypatch):
    """Monkeypatch all remote sinks to succeed; returns spy holders."""
    cortex_calls = []
    notion_calls = []
    telegram_calls = []

    def fake_cortex(payload, metadata):
        cortex_calls.append((payload, metadata))
        return ("fake-cortex-id-123", None)

    def fake_notion(tier, verdict_md, dissent_md, council_task_id):
        notion_calls.append((tier, verdict_md, dissent_md, council_task_id))
        return ("https://notion.so/fake-page", None)

    def fake_telegram(council_task_id, tier, confidence, cost):
        telegram_calls.append((council_task_id, tier, confidence, cost))
        return (True, None)

    monkeypatch.setattr(ledger_mod, "_write_cortex", fake_cortex)
    monkeypatch.setattr(ledger_mod, "_write_notion", fake_notion)
    monkeypatch.setattr(ledger_mod, "_send_telegram", fake_telegram)

    return cortex_calls, notion_calls, telegram_calls


def _run_ledger(tmp_path, monkeypatch, *, reconciler=None, keep_chains=False, debate=None):
    """Run write_ledger using tmp_path as base, with mocked sinks."""
    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    cortex_calls, notion_calls, telegram_calls = _mock_sinks(monkeypatch)
    kwargs = dict(BASE_KWARGS)
    kwargs["advisor_results"] = [
        ADVISOR_WITH_CHAIN.copy(),
        ADVISOR_WITH_CHAIN.copy(),
        ADVISOR_WITH_CHAIN.copy(),
    ]
    if reconciler is not None:
        kwargs["reconciler_result"] = reconciler
    if debate is not None:
        kwargs["debate_result"] = debate
    kwargs["keep_chains"] = keep_chains
    result = write_ledger(**kwargs)
    return result, cortex_calls, notion_calls, telegram_calls


# ---------------------------------------------------------------------------
# Filesystem (5)
# ---------------------------------------------------------------------------

def test_writes_canonical_file_set(tmp_path, monkeypatch):
    """8 core files must exist in workspace_dir after a default-mode write."""
    result, _, _, _ = _run_ledger(tmp_path, monkeypatch)
    ws = pathlib.Path(result["workspace_dir"])
    expected = {
        "brief.md",
        "anonymized.json",
        "advisor-A-structured.json",
        "advisor-B-structured.json",
        "advisor-C-structured.json",
        "verdict.md",
        "dissent.md",
        "seed.json",
        "cost.json",
    }
    found = {f.name for f in ws.iterdir() if f.is_file()}
    assert expected.issubset(found), f"Missing: {expected - found}"


def test_no_chain_in_structured_files(tmp_path, monkeypatch):
    """JSON-level check: reasoning_chain key must NOT appear in structured advisor files."""
    result, _, _, _ = _run_ledger(tmp_path, monkeypatch)
    ws = pathlib.Path(result["workspace_dir"])
    for label in ("A", "B", "C"):
        path = ws / f"advisor-{label}-structured.json"
        data = json.loads(path.read_text())
        assert "reasoning_chain" not in data, (
            f"advisor-{label}-structured.json contains reasoning_chain key"
        )


def test_keep_chains_writes_raw_with_chmod(tmp_path, monkeypatch):
    """keep_chains=True: 3 raw files exist, each 0o600, parent dir 0o700."""
    result, _, _, _ = _run_ledger(tmp_path, monkeypatch, keep_chains=True)
    ws = pathlib.Path(result["workspace_dir"])
    for label in ("A", "B", "C"):
        raw = ws / f"advisor-{label}-raw.json"
        assert raw.exists(), f"Missing {raw.name}"
        file_mode = stat.S_IMODE(raw.stat().st_mode)
        assert file_mode == 0o600, f"{raw.name} mode={oct(file_mode)}, expected 0o600"
    dir_mode = stat.S_IMODE(ws.stat().st_mode)
    assert dir_mode == 0o700, f"workspace dir mode={oct(dir_mode)}, expected 0o700"


def test_ac12_grep_clean_default(tmp_path, monkeypatch):
    """Default mode: no file in workspace contains the string 'reasoning_chain'."""
    result, _, _, _ = _run_ledger(tmp_path, monkeypatch)
    ws = pathlib.Path(result["workspace_dir"])
    needle = "reasoning_chain"
    leaking = []
    for fpath in ws.rglob("*"):
        if fpath.is_file():
            if needle in fpath.read_text(encoding="utf-8", errors="replace"):
                leaking.append(fpath.name)
    assert leaking == [], f"Found reasoning_chain in: {leaking}"


def test_ac12_grep_clean_with_keep_chains(tmp_path, monkeypatch):
    """
    With keep_chains=True the raw files may contain reasoning_chain, but
    the structured.json files must still be clean (AC-12 grep excludes *-raw.json).
    """
    result, _, _, _ = _run_ledger(tmp_path, monkeypatch, keep_chains=True)
    ws = pathlib.Path(result["workspace_dir"])
    needle = "reasoning_chain"
    leaking = []
    for fpath in ws.rglob("*"):
        if fpath.is_file() and not fpath.name.endswith("-raw.json"):
            if needle in fpath.read_text(encoding="utf-8", errors="replace"):
                leaking.append(fpath.name)
    assert leaking == [], f"Found reasoning_chain in non-raw files: {leaking}"
    # Verify raw files DO contain the chain (confirming the exclusion matters)
    raw_a = ws / "advisor-A-raw.json"
    assert "reasoning_chain" in raw_a.read_text()


# ---------------------------------------------------------------------------
# Sink resilience (4)
# ---------------------------------------------------------------------------

def test_cortex_failure_does_not_block_local(tmp_path, monkeypatch):
    """Cortex 503 -> status=PARTIAL_NO_CORTEX, local files still written, errors['cortex'] set.

    FIX-M2: when Cortex is the only failing sink, status is now PARTIAL_NO_CORTEX
    (not PARTIAL) so callers can distinguish Cortex-only degradation from other
    partial states.
    """
    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: (None, "503 Service Unavailable"))
    monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: ("https://notion.so/x", None))
    monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (True, None))

    result = write_ledger(**{**BASE_KWARGS, "advisor_results": [
        ADVISOR_WITH_CHAIN.copy(),
        ADVISOR_WITH_CHAIN.copy(),
        ADVISOR_WITH_CHAIN.copy(),
    ]})
    assert result["status"] == "PARTIAL_NO_CORTEX"
    assert "cortex" in result["errors"]
    ws = pathlib.Path(result["workspace_dir"])
    assert (ws / "verdict.md").exists()
    assert len(result["files_written"]) > 0


def test_notion_only_on_strong_pass_or_block(tmp_path, monkeypatch):
    """tier=PASS -> notion NOT called; tier=STRONG_PASS -> notion IS called."""
    notion_calls = []

    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: ("cid", None))
    monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (True, None))

    def spy_notion(tier, verdict_md, dissent_md, council_task_id):
        notion_calls.append(tier)
        return ("https://notion.so/x", None)

    monkeypatch.setattr(ledger_mod, "_write_notion", spy_notion)

    # PASS -> notion NOT called
    write_ledger(**{
        **BASE_KWARGS,
        "council_task_id": "council-20260519-1200-P001",
        "advisor_results": [ADVISOR_WITH_CHAIN.copy()] * 3,
        "reconciler_result": RECONCILER_PASS.copy(),
    })
    assert notion_calls == []

    # STRONG_PASS -> notion IS called
    write_ledger(**{
        **BASE_KWARGS,
        "council_task_id": "council-20260519-1200-P002",
        "advisor_results": [ADVISOR_WITH_CHAIN.copy()] * 3,
        "reconciler_result": RECONCILER.copy(),
    })
    assert "STRONG_PASS" in notion_calls


def test_telegram_failure_does_not_block(tmp_path, monkeypatch):
    """Telegram raises -> write_ledger completes, status=PARTIAL, errors['telegram'] set."""
    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: ("cid", None))
    monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: ("https://notion.so/x", None))

    def bad_telegram(*args):
        raise RuntimeError("network down")

    monkeypatch.setattr(ledger_mod, "_send_telegram", bad_telegram)

    result = write_ledger(**{**BASE_KWARGS, "advisor_results": [
        ADVISOR_WITH_CHAIN.copy()] * 3})
    assert result["status"] == "PARTIAL"
    assert "telegram" in result["errors"]
    assert result["privacy_audit"]["ac12_grep_clean"] is True


def test_fail_disk_aborts_remote_sinks(tmp_path, monkeypatch):
    """AC-12 failure -> FAIL_DISK; Cortex/Notion/Telegram spies NOT called."""
    cortex_calls = []
    notion_calls = []
    telegram_calls = []

    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_ac12_grep_check", lambda ws, adv, kc: False)
    monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: cortex_calls.append(p) or ("cid", None))
    monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: notion_calls.append(a) or ("url", None))
    monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: telegram_calls.append(a) or (True, None))

    result = write_ledger(**{**BASE_KWARGS, "advisor_results": [
        ADVISOR_WITH_CHAIN.copy()] * 3})
    assert result["status"] == "FAIL_DISK"
    assert cortex_calls == []
    assert notion_calls == []
    assert telegram_calls == []


def test_ac12_redacts_chain_overlap_before_remote_sinks(tmp_path, monkeypatch):
    """Exact reasoning overlap in verdict/dissent is redacted before sink writes."""
    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    cortex_calls, notion_calls, telegram_calls = _mock_sinks(monkeypatch)

    chain = (
        "This exact private overlap should be redacted before ledger sinks because "
        "it resembles a reasoning trace rather than a public advisor field."
    )
    overlap = chain[:40]
    reconciler = {
        **RECONCILER_PASS,
        "verdict_md": f"## Summary\n{overlap} appears here.\n\n## Split Zones\nNone.",
        "dissent_md": f"Dissent mentions {overlap}.",
    }
    advisor = {**ADVISOR_WITH_CHAIN, "reasoning_chain": chain}

    result = write_ledger(**{
        **BASE_KWARGS,
        "advisor_results": [advisor, ADVISOR_WITH_CHAIN.copy(), ADVISOR_WITH_CHAIN.copy()],
        "reconciler_result": reconciler,
    })

    workspace_dir = tmp_path / BASE_KWARGS["council_task_id"]
    assert result["privacy_audit"]["ac12_grep_clean"] is True
    assert result["status"] == "OK"
    assert cortex_calls
    assert telegram_calls
    assert notion_calls == []
    assert overlap not in (workspace_dir / "verdict.md").read_text()
    assert overlap not in (workspace_dir / "dissent.md").read_text()
    assert "[AC12-redacted-reasoning-overlap]" in (workspace_dir / "verdict.md").read_text()


def test_shared_reporter_output_runs_after_ac12(tmp_path, monkeypatch):
    """Reporter receives stripped advisors and returns an HTML report URL."""
    monkeypatch.setenv("COUNCIL_REPORTER_ENABLED", "1")
    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_write_cortex", lambda p, m: ("cid", None))
    monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: ("https://notion.so/x", None))
    monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (True, None))
    captured = {}

    def fake_reporter(**kwargs):
        captured.update(kwargs)
        assert all("reasoning_chain" not in advisor for advisor in kwargs["stripped_advisors"])
        return (
            {
                "agent": "shared-reporter",
                "status": "published",
                "result": {
                    "files": {"html": str(tmp_path / "report.html")},
                    "share_url": "https://cryptopafi.github.io/nexusos-reports/test.html",
                    "github_pages_url": "https://cryptopafi.github.io/nexusos-reports/test.html",
                },
            },
            None,
        )

    monkeypatch.setattr(ledger_mod, "_publish_html_report", fake_reporter)
    result = write_ledger(**{
        **BASE_KWARGS,
        "advisor_results": [ADVISOR_WITH_CHAIN.copy()] * 3,
    })

    assert captured["council_task_id"] == BASE_KWARGS["council_task_id"]
    assert result["html_report_url"] == "https://cryptopafi.github.io/nexusos-reports/test.html"
    assert result["reporter"]["agent"] == "shared-reporter"


# ---------------------------------------------------------------------------
# Cortex payload (2)
# ---------------------------------------------------------------------------

def test_cortex_payload_has_forge_metadata(tmp_path, monkeypatch):
    """Cortex payload must include FORGE metadata fields."""
    captured = {}

    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: ("url", None))
    monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (True, None))

    def spy_cortex(payload, metadata):
        captured["payload"] = payload
        captured["metadata"] = metadata
        return ("cid", None)

    monkeypatch.setattr(ledger_mod, "_write_cortex", spy_cortex)

    write_ledger(**{**BASE_KWARGS, "advisor_results": [ADVISOR_WITH_CHAIN.copy()] * 3})

    assert captured, "Cortex spy was never called"
    meta = captured["payload"]["metadata"]
    assert meta["has_enforcement_loop"] is True
    assert meta["forge_version"] == "1.4"
    assert meta["rule_id"] == "Pending"
    assert meta["type"] == "council-verdict"
    assert captured["payload"]["collection"] == "sessions"


def test_cortex_text_no_chain(tmp_path, monkeypatch):
    """Cortex payload text (verdict_md) must NOT contain reasoning_chain content."""
    captured = {}

    monkeypatch.setattr(ledger_mod, "_COUNCIL_BASE", tmp_path)
    monkeypatch.setattr(ledger_mod, "_write_notion", lambda *a: ("url", None))
    monkeypatch.setattr(ledger_mod, "_send_telegram", lambda *a: (True, None))

    def spy_cortex(payload, metadata):
        captured["payload"] = payload
        return ("cid", None)

    monkeypatch.setattr(ledger_mod, "_write_cortex", spy_cortex)

    advisor_with_heavy_chain = {
        "label": "Advisor",
        "recommendation": "Buy",
        "reasoning_chain": ["VERY SECRET CHAIN DATA"],
    }
    write_ledger(**{
        **BASE_KWARGS,
        "advisor_results": [advisor_with_heavy_chain.copy()] * 3,
    })

    text = captured["payload"]["text"]
    assert "reasoning_chain" not in text
    assert "VERY SECRET CHAIN DATA" not in text


# ---------------------------------------------------------------------------
# Purge (2)
# ---------------------------------------------------------------------------

def test_purge_old_chains(tmp_path):
    """Old raw chain file (8d) deleted; recent file (1d) kept."""
    old_file = tmp_path / "advisor-A-raw.json"
    recent_file = tmp_path / "advisor-B-raw.json"
    old_file.write_text('{"reasoning_chain": ["old"]}')
    recent_file.write_text('{"reasoning_chain": ["new"]}')

    now = time.time()
    os.utime(old_file, (now - 8 * 86400, now - 8 * 86400))
    os.utime(recent_file, (now - 1 * 86400, now - 1 * 86400))

    count = _purge_old_chains(tmp_path, days=7)
    assert count == 1
    assert not old_file.exists()
    assert recent_file.exists()


def test_purge_old_workspaces(tmp_path):
    """Old council-* dir (31d) deleted; recent dir (5d) kept."""
    old_dir = tmp_path / "council-20260401-0900-OLD1"
    recent_dir = tmp_path / "council-20260515-0900-NEW1"
    old_dir.mkdir()
    recent_dir.mkdir()
    (old_dir / "verdict.md").write_text("old verdict")
    (recent_dir / "verdict.md").write_text("new verdict")

    now = time.time()
    os.utime(old_dir, (now - 31 * 86400, now - 31 * 86400))
    os.utime(recent_dir, (now - 5 * 86400, now - 5 * 86400))

    count = _purge_old_workspaces(tmp_path, days=30)
    assert count == 1
    assert not old_dir.exists()
    assert recent_dir.exists()


# ---------------------------------------------------------------------------
# Status (1)
# ---------------------------------------------------------------------------

def test_status_ok_when_all_sinks_succeed(tmp_path, monkeypatch):
    """All sinks succeed -> status=OK, errors={}."""
    result, cortex_calls, notion_calls, telegram_calls = _run_ledger(tmp_path, monkeypatch)
    assert result["status"] == "OK", f"Expected OK, got {result['status']}: {result['errors']}"
    assert result["errors"] == {}
    assert result["cortex_id"] == "fake-cortex-id-123"
    assert result["telegram_sent"] is True
    # STRONG_PASS tier -> notion was called
    assert result["notion_url"] == "https://notion.so/fake-page"
    assert result["privacy_audit"]["ac12_grep_clean"] is True
    assert result["privacy_audit"]["chain_in_cortex"] is False
    assert result["privacy_audit"]["chain_in_notion"] is False


def test_load_telegram_config_accepts_cost_meter_aliases(tmp_path, monkeypatch):
    for key in ("LIS_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "BOT_TOKEN",
                "LIS_CHAT_ID", "TELEGRAM_PAFI_CHAT_ID", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)
    secrets_path = tmp_path / "vps2-secrets.env"
    secrets_path.write_text(
        "LIS_BOT_TOKEN=lis-token\nLIS_CHAT_ID=lis-chat\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ledger_mod, "_VPS2_SECRETS", secrets_path)

    assert _load_telegram_config() == ("lis-token", "lis-chat")


def test_load_telegram_config_prefers_env_aliases(tmp_path, monkeypatch):
    secrets_path = tmp_path / "vps2-secrets.env"
    secrets_path.write_text(
        "TELEGRAM_BOT_TOKEN=file-token\nTELEGRAM_CHAT_ID=file-chat\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ledger_mod, "_VPS2_SECRETS", secrets_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "env-chat")

    assert _load_telegram_config() == ("env-token", "env-chat")


def test_council_base_honors_workspace_env(monkeypatch, tmp_path):
    monkeypatch.setenv("COUNCIL_WORKSPACE_DIR", str(tmp_path / "council-workspace"))

    assert _default_council_base() == tmp_path / "council-workspace"


def test_secrets_path_honors_env(monkeypatch, tmp_path):
    custom = tmp_path / "secrets.env"
    monkeypatch.setenv("COUNCIL_VPS2_SECRETS", str(custom))

    assert _default_secrets_path() == custom
