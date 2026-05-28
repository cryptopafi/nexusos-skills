"""
cost_meter.py -- Per-invocation cost tracker with cap and daily-ceiling enforcement.

Tracks running cost across all pipeline steps. Refuses debate when cap >70% used.
Daily ceiling enforcement. Telegram alert via Lis on breach.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

from . import _providers

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CAPS: dict[str, float] = {
    "quick": 2.00,
    "standard": 6.00,
    "deep": 18.00,
}

DEFAULT_DAILY_CEILING: float = 50.00
DEBATE_THRESHOLD_PCT: float = 0.70


def _default_daily_spend_path() -> pathlib.Path:
    explicit_path = os.environ.get("COUNCIL_DAILY_SPEND_PATH")
    if explicit_path:
        return pathlib.Path(explicit_path).expanduser()
    state_dir = os.environ.get("COUNCIL_STATE_DIR")
    if state_dir:
        return pathlib.Path(state_dir).expanduser() / "council-daily-spend.json"
    return pathlib.Path.home() / ".nexus" / "state" / "council-daily-spend.json"


DAILY_SPEND_PATH: pathlib.Path = _default_daily_spend_path()

_SECRETS_PATH: pathlib.Path = (
    pathlib.Path.home() / ".nexus" / "workspace" / "active" / "vps2-secrets.env"
)

_PURGE_DAYS: int = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_cost(provider_key: str, tokens_in: int, tokens_out: int) -> float:
    """Look up provider from PROVIDER_REGISTRY; return cost in USD."""
    registry = _providers.PROVIDER_REGISTRY
    if provider_key not in registry:
        raise KeyError(f"Unknown provider_key {provider_key!r} in PROVIDER_REGISTRY")
    entry = registry[provider_key]
    price_in: float = entry["price_in"]
    price_out: float = entry["price_out"]
    return (tokens_in * price_in) + (tokens_out * price_out)


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _purge_old_entries(data: dict[str, Any]) -> dict[str, Any]:
    """Remove date keys older than _PURGE_DAYS days. Returns pruned dict."""
    today = datetime.now(timezone.utc)
    cutoff_days = _PURGE_DAYS
    keys_to_delete: list[str] = []
    for date_str in list(data.keys()):
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if (today - day).days > cutoff_days:
                keys_to_delete.append(date_str)
        except ValueError:
            pass
    for k in keys_to_delete:
        del data[k]
    return data


def _read_daily_spend(
    spend_path: pathlib.Path | None = None,
    date_str: str | None = None,
) -> float:
    """
    Read today's total from DAILY_SPEND_PATH. date_str defaults to today's UTC date.
    Auto-purges entries older than _PURGE_DAYS on read (side-effect only in memory).
    """
    path = spend_path if spend_path is not None else DAILY_SPEND_PATH
    today = date_str or _utc_today()
    if not path.exists():
        return 0.0
    try:
        raw = path.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return 0.0
    data = _purge_old_entries(data)
    entries = data.get(today, [])
    return sum(float(e.get("cost_usd", 0.0)) for e in entries)


def _atomic_write_json(path: pathlib.Path, data: dict) -> None:
    """Write tmp then rename for crash-safety."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-council-spend-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _load_secrets_env(path: pathlib.Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE env file. Returns empty dict if absent or unreadable."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return result


def _telegram_config_from_secrets(secrets: dict[str, str]) -> tuple[str | None, str | None]:
    bot_token = (
        secrets.get("LIS_BOT_TOKEN")
        or secrets.get("TELEGRAM_BOT_TOKEN")
        or secrets.get("BOT_TOKEN")
    )
    chat_id = (
        secrets.get("LIS_CHAT_ID")
        or secrets.get("TELEGRAM_PAFI_CHAT_ID")
        or secrets.get("TELEGRAM_CHAT_ID")
    )
    return bot_token, chat_id


def _send_telegram_alert(message: str, task_id: str) -> None:
    """
    Fire-and-forget alert via Lis bot.
    Best-effort: log to stderr on failure but never raise.
    Reads bot config from ~/.nexus/workspace/active/vps2-secrets.env if present;
    silently no-op if not configured.
    """
    try:
        secrets = _load_secrets_env(_SECRETS_PATH)
        bot_token, chat_id = _telegram_config_from_secrets(secrets)
        if not bot_token or not chat_id:
            return
        payload = json.dumps({
            "chat_id": chat_id,
            "text": f"[council cost-meter] task={task_id}\n{message}",
            "parse_mode": "HTML",
        }).encode("utf-8")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as _resp:
            pass
    except Exception as exc:
        sys.stderr.write(
            f"[cost_meter] Telegram alert failed (non-fatal): {type(exc).__name__}: {exc}\n"
        )


# ---------------------------------------------------------------------------
# CostMeter
# ---------------------------------------------------------------------------

class CostMeter:
    """Per-invocation cost meter with cap + daily-ceiling enforcement."""

    def __init__(
        self,
        depth: str,
        *,
        task_id: str,
        cap_override: float | None = None,
        daily_ceiling: float = DEFAULT_DAILY_CEILING,
        force: bool = False,
        force_test: bool = False,
        _spend_path: pathlib.Path | None = None,
    ) -> None:
        if depth not in DEFAULT_CAPS and cap_override is None:
            raise ValueError(
                f"Unknown depth {depth!r}. Must be one of {list(DEFAULT_CAPS)} "
                "or supply cap_override."
            )
        self._depth = depth
        self._task_id = task_id
        self._cap: float = cap_override if cap_override is not None else DEFAULT_CAPS[depth]
        self._daily_ceiling: float = daily_ceiling
        self._force: bool = force
        self._force_test: bool = force_test
        self._spend_path: pathlib.Path = _spend_path if _spend_path is not None else DAILY_SPEND_PATH
        self._total: float = 0.0
        self._ledger: list[dict] = []
        self._alert_fired: bool = False

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def add(
        self,
        *,
        provider_key: str,
        tokens_in: int,
        tokens_out: int,
        step: str,
    ) -> float:
        """
        Tick cost from PROVIDER_REGISTRY pricing. Updates running total.
        Returns the cost of THIS tick (not cumulative).
        """
        cost = _compute_cost(provider_key, tokens_in, tokens_out)
        self._total += cost
        self._ledger.append({
            "step": step,
            "label": "",
            "provider_key": provider_key,
            "tokens": {"in": tokens_in, "out": tokens_out},
            "cost_usd": cost,
            "ts": _utc_now_iso(),
        })
        return cost

    def add_raw(self, *, cost_usd: float, step: str, label: str = "") -> None:
        """Tick raw cost when caller already computed it."""
        self._total += cost_usd
        self._ledger.append({
            "step": step,
            "label": label,
            "provider_key": None,
            "tokens": None,
            "cost_usd": cost_usd,
            "ts": _utc_now_iso(),
        })

    # ------------------------------------------------------------------
    # Guard checks
    # ------------------------------------------------------------------

    def can_run_debate(self) -> tuple[bool, str]:
        """Returns (allowed, reason). False if cumulative >70% of cap."""
        pct = self.pct_used
        if pct > DEBATE_THRESHOLD_PCT:
            return (
                False,
                f"cost exceeds 70% threshold: {pct:.1%} of cap "
                f"(${self._total:.4f} / ${self._cap:.2f})",
            )
        return (
            True,
            f"within debate threshold: {pct:.1%} of cap "
            f"(${self._total:.4f} / ${self._cap:.2f})",
        )

    def check_cap(self) -> tuple[bool, str]:
        """
        Returns (within_cap, message).
        Fires Telegram alert if cap breached (idempotent — once per instance).
        """
        if self._total > self._cap:
            if not self._alert_fired:
                self._alert_fired = True
                try:
                    _send_telegram_alert(
                        f"Cap breached: ${self._total:.4f} > ${self._cap:.2f} "
                        f"(depth={self._depth})",
                        self._task_id,
                    )
                except Exception as exc:
                    sys.stderr.write(
                        f"[cost_meter] check_cap alert error (non-fatal): "
                        f"{type(exc).__name__}: {exc}\n"
                    )
            return (
                False,
                f"cap exceeded: ${self._total:.4f} > ${self._cap:.2f}",
            )
        return (
            True,
            f"within cap: ${self._total:.4f} / ${self._cap:.2f}",
        )

    def check_daily_ceiling(self) -> tuple[bool, str]:
        """
        Returns (within_ceiling, message).
        False if (prior_spend + current total) >= daily_ceiling AND not force/force_test.

        FIX-H3: force_test=True exempts the daily ceiling check so AC-7
        6-permutation harness can run without consuming daily budget. Returns
        (True, "force_test-bypass") when force_test is set.
        """
        # FIX-H3: force_test bypass (distinct from force for audit-trail clarity)
        if self._force_test:
            prior = _read_daily_spend(self._spend_path)
            projected = prior + self._total
            return (
                True,
                f"force_test-bypass: daily ceiling would be ${projected:.4f} "
                f">= ${self._daily_ceiling:.2f}",
            )
        prior = _read_daily_spend(self._spend_path)
        projected = prior + self._total
        if projected >= self._daily_ceiling and not self._force:
            return (
                False,
                f"daily ceiling exceeded: ${projected:.4f} >= ${self._daily_ceiling:.2f} "
                f"(prior=${prior:.4f} + current=${self._total:.4f})",
            )
        if self._force and projected >= self._daily_ceiling:
            return (
                True,
                f"force bypass: daily ceiling would be ${projected:.4f} "
                f">= ${self._daily_ceiling:.2f}",
            )
        return (
            True,
            f"within daily ceiling: ${projected:.4f} / ${self._daily_ceiling:.2f}",
        )

    # ------------------------------------------------------------------
    # Ledger persistence
    # ------------------------------------------------------------------

    def commit_to_daily_ledger(self) -> None:
        """
        Append final cumulative cost to DAILY_SPEND_PATH as a daily-keyed entry.
        Atomic write (write tmp + rename).
        """
        today = _utc_today()
        path = self._spend_path

        if path.exists():
            try:
                raw = path.read_text(encoding="utf-8")
                data: dict[str, Any] = json.loads(raw)
            except (json.JSONDecodeError, OSError):
                data = {}
        else:
            data = {}

        data = _purge_old_entries(data)
        if today not in data:
            data[today] = []

        data[today].append({
            "ts": _utc_now_iso(),
            "task_id": self._task_id,
            "depth": self._depth,
            "cost_usd": round(self._total, 6),
        })

        _atomic_write_json(path, data)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total(self) -> float:
        """Cumulative cost so far this invocation."""
        return self._total

    @property
    def cap(self) -> float:
        """Configured cap for this invocation."""
        return self._cap

    @property
    def pct_used(self) -> float:
        """total/cap (0.0..1.0+)."""
        if self._cap == 0.0:
            return 0.0
        return self._total / self._cap

    @property
    def ledger(self) -> list[dict]:
        """Audit-trail of all ticks."""
        return list(self._ledger)
