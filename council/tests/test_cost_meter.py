"""
test_cost_meter.py -- 10 pytest cases for CostMeter.

Uses monkeypatch on:
- DAILY_SPEND_PATH (via _spend_path kwarg on CostMeter and module-level patch)
- _providers.PROVIDER_REGISTRY (deterministic prices)
- _send_telegram_alert (spy — no real Telegram)
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from lib import _providers
from lib.cost_meter import (
    CostMeter,
    DEFAULT_CAPS,
    DEFAULT_DAILY_CEILING,
    DEBATE_THRESHOLD_PCT,
    _compute_cost,
    _send_telegram_alert,
    _telegram_config_from_secrets,
)


# ---------------------------------------------------------------------------
# Shared fixture: deterministic PROVIDER_REGISTRY
# ---------------------------------------------------------------------------

FAKE_REGISTRY: dict = {
    "sonnet-4-6": {
        "vendor": "anthropic",
        "model_id": "claude-sonnet-4-6",
        "price_in": 1.00 / 1_000,   # $0.001 per token in
        "price_out": 2.00 / 1_000,  # $0.002 per token out
    },
    "haiku-4-5": {
        "vendor": "anthropic",
        "model_id": "claude-haiku",
        "price_in": 0.50 / 1_000,
        "price_out": 1.00 / 1_000,
    },
}


@pytest.fixture(autouse=True)
def patch_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch PROVIDER_REGISTRY globally for all cost_meter tests."""
    monkeypatch.setattr(_providers, "PROVIDER_REGISTRY", FAKE_REGISTRY)


@pytest.fixture()
def tmp_spend_path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "council-daily-spend.json"


def _make_meter(
    depth: str = "standard",
    *,
    task_id: str = "test-task",
    spend_path: pathlib.Path | None = None,
    cap_override: float | None = None,
    daily_ceiling: float = DEFAULT_DAILY_CEILING,
    force: bool = False,
) -> CostMeter:
    return CostMeter(
        depth,
        task_id=task_id,
        cap_override=cap_override,
        daily_ceiling=daily_ceiling,
        force=force,
        _spend_path=spend_path,
    )


# ---------------------------------------------------------------------------
# Test 1: init defaults -- caps by depth
# ---------------------------------------------------------------------------

def test_init_default_cap_by_depth(tmp_spend_path: pathlib.Path) -> None:
    quick = _make_meter("quick", spend_path=tmp_spend_path)
    standard = _make_meter("standard", spend_path=tmp_spend_path)
    deep = _make_meter("deep", spend_path=tmp_spend_path)

    assert quick.cap == 2.00
    assert standard.cap == 6.00
    assert deep.cap == 18.00

    # Confirm defaults: total=0, pct_used=0, ledger empty
    assert quick.total == 0.0
    assert quick.pct_used == 0.0
    assert quick.ledger == []


# ---------------------------------------------------------------------------
# Test 2: init -- cap_override wins over depth default
# ---------------------------------------------------------------------------

def test_init_cap_override(tmp_spend_path: pathlib.Path) -> None:
    meter = _make_meter("standard", cap_override=10.0, spend_path=tmp_spend_path)
    assert meter.cap == 10.0
    # depth default would be 6.0; override takes precedence
    assert meter.cap != DEFAULT_CAPS["standard"]


# ---------------------------------------------------------------------------
# Test 3: add() uses PROVIDER_REGISTRY for pricing
# ---------------------------------------------------------------------------

def test_add_uses_provider_registry(tmp_spend_path: pathlib.Path) -> None:
    meter = _make_meter(spend_path=tmp_spend_path)
    # price_in=0.001, price_out=0.002
    # cost = 1000 * 0.001 + 500 * 0.002 = 1.0 + 1.0 = 2.0
    tick_cost = meter.add(
        provider_key="sonnet-4-6",
        tokens_in=1000,
        tokens_out=500,
        step="normalize",
    )
    expected = 1000 * (1.00 / 1_000) + 500 * (2.00 / 1_000)
    assert abs(tick_cost - expected) < 1e-9
    assert abs(meter.total - expected) < 1e-9
    assert len(meter.ledger) == 1
    entry = meter.ledger[0]
    assert entry["step"] == "normalize"
    assert entry["provider_key"] == "sonnet-4-6"
    assert abs(entry["cost_usd"] - expected) < 1e-9


# ---------------------------------------------------------------------------
# Test 4: add_raw() accumulates and records ledger entry
# ---------------------------------------------------------------------------

def test_add_raw(tmp_spend_path: pathlib.Path) -> None:
    meter = _make_meter(spend_path=tmp_spend_path)
    meter.add_raw(cost_usd=0.50, step="reconcile", label="opus-ext")

    assert abs(meter.total - 0.50) < 1e-9
    assert len(meter.ledger) == 1
    entry = meter.ledger[0]
    assert entry["step"] == "reconcile"
    assert entry["label"] == "opus-ext"
    assert entry["provider_key"] is None
    assert abs(entry["cost_usd"] - 0.50) < 1e-9


# ---------------------------------------------------------------------------
# Test 5: can_run_debate -- below threshold returns True
# ---------------------------------------------------------------------------

def test_can_run_debate_below_threshold(tmp_spend_path: pathlib.Path) -> None:
    meter = _make_meter("standard", spend_path=tmp_spend_path)
    # cap=6.00; put meter at 50% = $3.00
    meter.add_raw(cost_usd=3.00, step="advisor-opus")
    assert abs(meter.pct_used - 0.50) < 1e-9

    allowed, reason = meter.can_run_debate()
    assert allowed is True
    assert "within debate threshold" in reason


# ---------------------------------------------------------------------------
# Test 6: can_run_debate -- above threshold returns False
# ---------------------------------------------------------------------------

def test_can_run_debate_above_threshold(tmp_spend_path: pathlib.Path) -> None:
    meter = _make_meter("standard", spend_path=tmp_spend_path)
    # cap=6.00; put meter at 80% = $4.80
    meter.add_raw(cost_usd=4.80, step="advisor-opus")
    assert meter.pct_used > DEBATE_THRESHOLD_PCT

    allowed, reason = meter.can_run_debate()
    assert allowed is False
    assert "cost exceeds 70% threshold" in reason


# ---------------------------------------------------------------------------
# Test 7: check_cap triggers Telegram ONCE (idempotent)
# ---------------------------------------------------------------------------

def test_check_cap_triggers_telegram_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_spend_path: pathlib.Path,
) -> None:
    import lib.cost_meter as cm_module

    alert_calls: list[tuple[str, str]] = []

    def fake_alert(message: str, task_id: str) -> None:
        alert_calls.append((message, task_id))

    monkeypatch.setattr(cm_module, "_send_telegram_alert", fake_alert)

    meter = _make_meter("standard", spend_path=tmp_spend_path)
    # Exceed cap (cap=6.00)
    meter.add_raw(cost_usd=7.00, step="advisor-opus")

    # First call: alert fires
    within, msg = meter.check_cap()
    assert within is False
    assert len(alert_calls) == 1

    # Second call: within still False but NO additional alert
    within2, _ = meter.check_cap()
    assert within2 is False
    assert len(alert_calls) == 1, "Alert must fire only once (idempotent)"


# ---------------------------------------------------------------------------
# Test 8: check_daily_ceiling -- force bypass
# ---------------------------------------------------------------------------

def test_check_daily_ceiling_force_bypass(
    tmp_spend_path: pathlib.Path,
) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Write $48 already spent today
    prior_data = {
        today: [
            {
                "ts": f"{today}T10:00:00Z",
                "task_id": "prior-task",
                "depth": "deep",
                "cost_usd": 48.00,
            }
        ]
    }
    tmp_spend_path.write_text(json.dumps(prior_data), encoding="utf-8")

    # New meter: $5 spend -> projected $53 > $50 ceiling
    meter_no_force = _make_meter(
        "standard",
        spend_path=tmp_spend_path,
        daily_ceiling=50.00,
        force=False,
    )
    meter_no_force.add_raw(cost_usd=5.00, step="triage")

    within, msg = meter_no_force.check_daily_ceiling()
    assert within is False
    assert "daily ceiling exceeded" in msg

    # With force=True: ceiling still breached but returns True
    meter_force = _make_meter(
        "standard",
        spend_path=tmp_spend_path,
        daily_ceiling=50.00,
        force=True,
    )
    meter_force.add_raw(cost_usd=5.00, step="triage")

    within_f, msg_f = meter_force.check_daily_ceiling()
    assert within_f is True
    assert "force bypass" in msg_f


# ---------------------------------------------------------------------------
# Test 9: commit_to_daily_ledger -- atomic write; preserves existing entries
# ---------------------------------------------------------------------------

def test_commit_to_daily_ledger_atomic(tmp_spend_path: pathlib.Path) -> None:
    yesterday = "2026-05-18"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Pre-existing file with yesterday's data
    existing = {
        yesterday: [
            {
                "ts": f"{yesterday}T09:00:00Z",
                "task_id": "old-task",
                "depth": "quick",
                "cost_usd": 1.50,
            }
        ]
    }
    tmp_spend_path.write_text(json.dumps(existing), encoding="utf-8")

    meter = _make_meter("standard", spend_path=tmp_spend_path)
    meter.add_raw(cost_usd=3.00, step="normalize")
    meter.commit_to_daily_ledger()

    assert tmp_spend_path.exists()
    data = json.loads(tmp_spend_path.read_text(encoding="utf-8"))

    # Yesterday's entry preserved
    assert yesterday in data
    assert len(data[yesterday]) == 1
    assert data[yesterday][0]["cost_usd"] == 1.50

    # Today's entry added
    assert today in data
    today_entries = data[today]
    assert len(today_entries) == 1
    assert abs(today_entries[0]["cost_usd"] - 3.00) < 1e-9
    assert today_entries[0]["task_id"] == "test-task"
    assert today_entries[0]["depth"] == "standard"


# ---------------------------------------------------------------------------
# Test 10: Telegram alert failure does NOT raise into pipeline
# ---------------------------------------------------------------------------

def test_telegram_alert_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    tmp_spend_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
) -> None:
    import lib.cost_meter as cm_module

    def exploding_alert(message: str, task_id: str) -> None:
        raise RuntimeError("Telegram network failure simulated")

    monkeypatch.setattr(cm_module, "_send_telegram_alert", exploding_alert)

    meter = _make_meter("standard", spend_path=tmp_spend_path)
    # Exceed cap to trigger alert
    meter.add_raw(cost_usd=7.00, step="advisor")

    # Must NOT raise
    within, msg = meter.check_cap()
    assert within is False

    # Stderr warning should be logged
    captured = capsys.readouterr()
    assert "non-fatal" in captured.err or "cost_meter" in captured.err


def test_telegram_config_accepts_ledger_aliases() -> None:
    token, chat_id = _telegram_config_from_secrets({
        "BOT_TOKEN": "bot-token",
        "TELEGRAM_PAFI_CHAT_ID": "chat-id",
    })

    assert token == "bot-token"
    assert chat_id == "chat-id"


def test_daily_spend_path_honors_state_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    import importlib
    import lib.cost_meter as cm_module

    monkeypatch.setenv("COUNCIL_STATE_DIR", str(tmp_path / "state"))
    reloaded = importlib.reload(cm_module)

    assert reloaded.DAILY_SPEND_PATH == tmp_path / "state" / "council-daily-spend.json"

    monkeypatch.delenv("COUNCIL_STATE_DIR", raising=False)
    importlib.reload(cm_module)
