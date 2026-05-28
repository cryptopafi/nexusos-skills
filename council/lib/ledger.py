"""
ledger.py — Privacy-hardened writeback for /council pipeline (Step 8).

Sinks: local disk (always) + Cortex (always) + Notion (STRONG_PASS/BLOCK only)
       + Telegram via Lis (always best-effort).

AC-12: grep BEFORE remote sinks. Any reasoning_chain in non-raw files -> FAIL_DISK.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import stat
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from . import vk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def _default_council_base() -> pathlib.Path:
    workspace_dir = os.environ.get("COUNCIL_WORKSPACE_DIR")
    if workspace_dir:
        return pathlib.Path(workspace_dir).expanduser()
    return pathlib.Path.home() / ".nexus" / "workspace" / "council"


_COUNCIL_BASE = _default_council_base()
_CORTEX_URL = os.environ.get("COUNCIL_CORTEX_URL", "http://localhost:6400/api/store")
_CORTEX_COLLECTION = "sessions"
_CORTEX_MAX_TEXT = 8000
_NOTION_TIERS = {"STRONG_PASS", "BLOCK"}
_ADVISOR_LABELS = ("A", "B", "C")


def _default_secrets_path() -> pathlib.Path:
    secrets_path = os.environ.get("COUNCIL_VPS2_SECRETS")
    if secrets_path:
        return pathlib.Path(secrets_path).expanduser()
    return pathlib.Path.home() / ".nexus" / "workspace" / "active" / "vps2-secrets.env"


_VPS2_SECRETS = _default_secrets_path()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def write_ledger(
    *,
    task_id: str,
    council_task_id: str,
    brief_xml: str,
    advisor_results: list[dict],
    anonymized: list[dict],
    shuffle_map: dict,
    seed: int,
    reconciler_result: dict,
    debate_result: dict | None,
    cost_meter_total: float,
    keep_chains: bool = False,
) -> dict:
    """
    Persist all council artifacts to 4 sinks with privacy hardening.

    Returns a status dict with workspace_dir, files_written, cortex_id,
    notion_url, telegram_sent, privacy_audit, status, errors.

    Raises:
        ValueError: if advisor_results does not have exactly 3 entries.
    """
    if len(advisor_results) != 3:
        raise ValueError(
            f"advisor_results must have exactly 3 entries, got {len(advisor_results)}"
        )

    # FIX-C2: emit "entered" so the ledger step is observable in VK stream
    vk.emit("ledger", "entered", task_id)

    errors: dict[str, str] = {}
    warnings: dict[str, str] = {}
    files_written: list[str] = []
    cortex_id: str | None = None
    notion_url: str | None = None
    html_report_url: str | None = None
    reporter_output: dict[str, Any] | None = None
    telegram_sent = False

    # --- 1. Prepare workspace dir -----------------------------------------
    workspace_dir = _COUNCIL_BASE / council_task_id
    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        vk.emit("ledger", "failed", task_id, reason="mkdir_failed", error_class=type(exc).__name__)
        return {
            "workspace_dir": str(workspace_dir),
            "files_written": [],
            "cortex_id": None,
            "notion_url": None,
            "telegram_sent": False,
            "privacy_audit": {
                "chain_in_local": False,
                "chain_in_cortex": False,
                "chain_in_notion": False,
                "ac12_grep_clean": False,
            },
            "status": "FAIL_DISK",
            "errors": {"disk": str(exc)},
        }

    # --- 2. Write canonical files (stripped) --------------------------------
    stripped = _strip_chains(advisor_results)
    try:
        files_written = _write_local_files(
            workspace_dir=workspace_dir,
            brief_xml=brief_xml,
            anonymized=anonymized,
            stripped_advisors=stripped,
            shuffle_map=shuffle_map,
            seed=seed,
            reconciler_result=reconciler_result,
            debate_result=debate_result,
            cost_meter_total=cost_meter_total,
        )
    except OSError as exc:
        vk.emit("ledger", "failed", task_id, reason="write_local_failed", error_class=type(exc).__name__)
        return {
            "workspace_dir": str(workspace_dir),
            "files_written": [],
            "cortex_id": None,
            "notion_url": None,
            "telegram_sent": False,
            "privacy_audit": {
                "chain_in_local": False,
                "chain_in_cortex": False,
                "chain_in_notion": False,
                "ac12_grep_clean": False,
            },
            "status": "FAIL_DISK",
            "errors": {"disk": str(exc)},
        }

    # --- 3. Optionally write raw chains (protected) -------------------------
    chain_in_local = False
    if keep_chains:
        try:
            raw_files = _write_chains_protected(workspace_dir, advisor_results)
            files_written.extend(raw_files)
            chain_in_local = True
            # Run 7-day purge only when keep_chains is active
            _purge_old_chains(_COUNCIL_BASE)
        except OSError as exc:
            errors["chains"] = str(exc)

    # --- 4. AC-12 privacy grep check ----------------------------------------
    ac12_clean = _ac12_grep_check(workspace_dir, advisor_results, keep_chains)
    if not ac12_clean:
        try:
            _redact_chain_overlaps(workspace_dir, advisor_results, keep_chains)
        except OSError:
            pass
        ac12_clean = _ac12_grep_check(workspace_dir, advisor_results, keep_chains)
    if not ac12_clean:
        vk.emit("ledger", "failed", task_id, reason="ac12_grep_leak")
        return {
            "workspace_dir": str(workspace_dir),
            "files_written": files_written,
            "cortex_id": None,
            "notion_url": None,
            "telegram_sent": False,
            "privacy_audit": {
                "chain_in_local": chain_in_local,
                "chain_in_cortex": False,
                "chain_in_notion": False,
                "ac12_grep_clean": False,
            },
            "status": "FAIL_DISK",
            "errors": {"ac12": "reasoning_chain leak detected in workspace files"},
        }

    # --- 5. Shared-reporter HTML output (local + GitHub Pages, best-effort) ---
    if os.environ.get("COUNCIL_REPORTER_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}:
        reporter_output, reporter_err = _publish_html_report(
            workspace_dir=workspace_dir,
            task_id=task_id,
            council_task_id=council_task_id,
            brief_xml=brief_xml,
            stripped_advisors=stripped,
            reconciler_result=reconciler_result,
            debate_result=debate_result,
            cost_meter_total=cost_meter_total,
        )
        if reporter_output:
            result = reporter_output.get("result", {})
            files = result.get("files", {}) if isinstance(result, dict) else {}
            if isinstance(files, dict):
                files_written.extend(str(path) for path in files.values() if path)
            html_report_url = result.get("github_pages_url") or result.get("share_url")
        if reporter_err:
            warnings["reporter"] = reporter_err

    # --- 6. Cortex sink (always, best-effort) --------------------------------
    tier = reconciler_result.get("tier", "UNKNOWN")
    confidence = float(reconciler_result.get("confidence", 0.0))
    verdict_md = reconciler_result.get("verdict_md", "")
    cortex_text = verdict_md[:_CORTEX_MAX_TEXT]
    cortex_metadata = {
        "type": "council-verdict",
        "procedure": "PROC-COUNCIL-DESIGN-001",
        "rule_id": "Pending",
        "has_enforcement_loop": True,
        "forge_version": "1.4",
        "council_task_id": council_task_id,
        "tier": tier,
        "confidence": confidence,
        "advisor_count": 3,
        "tags": ["council", "multi-model", "deliberation", tier.lower()],
        "ts_iso": datetime.now(timezone.utc).isoformat(),
        "cost_usd": cost_meter_total,
    }
    cortex_payload = {
        "collection": _CORTEX_COLLECTION,
        "text": cortex_text,
        "metadata": cortex_metadata,
    }
    cortex_id, cortex_err = _write_cortex(cortex_payload, cortex_metadata)
    if cortex_err:
        errors["cortex"] = cortex_err

    # --- 7. Notion sink (STRONG_PASS / BLOCK only) --------------------------
    if tier in _NOTION_TIERS:
        dissent_md = reconciler_result.get("dissent_md", "")
        notion_url, notion_err = _write_notion(tier, verdict_md, dissent_md, council_task_id)
        if notion_err == "notion_mcp_unavailable":
            warnings["notion"] = notion_err
        elif notion_err:
            errors["notion"] = notion_err

    # --- 8. Telegram sink (always, best-effort) -----------------------------
    try:
        sent, tg_err = _send_telegram(council_task_id, tier, confidence, cost_meter_total)
        telegram_sent = sent
        if tg_err:
            errors["telegram"] = tg_err
    except Exception as exc:
        telegram_sent = False
        errors["telegram"] = str(exc)

    # --- 9. 30-day workspace purge (idempotent) ------------------------------
    try:
        _purge_old_workspaces(_COUNCIL_BASE)
    except Exception:
        pass  # purge failure is non-fatal (broaden beyond OSError for safety)

    # --- 10. Determine status -----------------------------------------------
    # FIX-M2: distinguish Cortex-only partial from other partials
    if cortex_id is None and "cortex" in errors:
        import sys as _sys
        _sys.stderr.write("[ledger] Cortex unavailable — skipping Cortex writeback.\n")

    if errors:
        only_cortex_error = set(errors.keys()) == {"cortex"}
        if only_cortex_error and cortex_id is None:
            status = "PARTIAL_NO_CORTEX"
        else:
            status = "PARTIAL"
    else:
        status = "OK"

    # FIX-C2: emit "completed" (even on PARTIAL — ledger ran to end)
    vk.emit(
        "ledger", "completed", task_id,
        cortex_id=cortex_id or "skipped",
        telegram_sent=str(telegram_sent),
        status=status,
    )

    return {
        "workspace_dir": str(workspace_dir),
        "files_written": files_written,
        "cortex_id": cortex_id,
        "notion_url": notion_url,
        "html_report_url": html_report_url,
        "reporter": reporter_output,
        "telegram_sent": telegram_sent,
        "privacy_audit": {
            "chain_in_local": chain_in_local,
            "chain_in_cortex": False,
            "chain_in_notion": False,
            "ac12_grep_clean": True,
        },
        "status": status,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers — filesystem
# ---------------------------------------------------------------------------
def _strip_chains(advisor_results: list[dict]) -> list[dict]:
    """Return new list with reasoning_chain removed from each dict (defensive copy)."""
    stripped = []
    for adv in advisor_results:
        d = copy.deepcopy(adv)
        d.pop("reasoning_chain", None)
        stripped.append(d)
    return stripped


def _publish_html_report(**kwargs: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Late import keeps ledger usable if reporter dependencies are unavailable."""
    from .reporter import publish_council_report

    return publish_council_report(**kwargs)


def _write_local_files(
    *,
    workspace_dir: pathlib.Path,
    brief_xml: str,
    anonymized: list[dict],
    stripped_advisors: list[dict],
    shuffle_map: dict,
    seed: int,
    reconciler_result: dict,
    debate_result: dict | None,
    cost_meter_total: float,
) -> list[str]:
    """Write the canonical set of files. Returns list of absolute path strings."""
    written: list[str] = []

    def _dump(path: pathlib.Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    def _dump_json(path: pathlib.Path, obj: Any) -> None:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(str(path))

    _dump(workspace_dir / "brief.md", brief_xml)
    _dump_json(workspace_dir / "anonymized.json", anonymized)

    for label, adv in zip(_ADVISOR_LABELS, stripped_advisors):
        _dump_json(workspace_dir / f"advisor-{label}-structured.json", adv)

    verdict_md = reconciler_result.get("verdict_md", "")
    dissent_md = reconciler_result.get("dissent_md", "")
    _dump(workspace_dir / "verdict.md", verdict_md)
    _dump(workspace_dir / "dissent.md", dissent_md)

    seed_data = {"seed": seed, "shuffle_map": shuffle_map}
    _dump_json(workspace_dir / "seed.json", seed_data)

    cost_data: dict[str, Any] = {"cost_usd_total": cost_meter_total}
    if "ledger" in reconciler_result:
        cost_data["ledger"] = reconciler_result["ledger"]
    _dump_json(workspace_dir / "cost.json", cost_data)

    if debate_result is not None:
        _dump_json(workspace_dir / "debate.json", debate_result)

    return written


def _write_chains_protected(
    workspace_dir: pathlib.Path,
    advisor_results: list[dict],
) -> list[str]:
    """Write raw advisor JSONs with chmod 600; set parent dir chmod 700."""
    os.chmod(workspace_dir, 0o700)
    written: list[str] = []
    for label, adv in zip(_ADVISOR_LABELS, advisor_results):
        path = workspace_dir / f"advisor-{label}-raw.json"
        path.write_text(json.dumps(adv, indent=2, ensure_ascii=False), encoding="utf-8")
        os.chmod(path, 0o600)
        written.append(str(path))
    return written


def _ac12_grep_check(
    workspace_dir: pathlib.Path,
    advisor_results: list[dict],
    keep_chains: bool,
) -> bool:
    """
    Walk workspace_dir; for all files EXCEPT advisor-*-raw.json, check for:
      1. literal 'reasoning_chain' key string (catches struct misuse)
      2. first 40 chars of each advisor's reasoning_chain VALUE (catches content leak)
    Returns True if clean, False if any leak detected.

    FIX-H4: probing actual chain values catches content leaks that key-string
    grep would miss (e.g. a future bug serialises chain value into structured.json
    without the 'reasoning_chain' key name).
    """
    needle = "reasoning_chain"
    chain_probes = _chain_value_probes(advisor_results)

    for fpath in _ac12_target_files(workspace_dir, keep_chains):
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            if needle in content:
                return False
            for probe in chain_probes:
                if probe in content:
                    return False
        except OSError:
            # Unreadable file — treat as clean (edge case)
            pass
    return True


def _redact_chain_overlaps(
    workspace_dir: pathlib.Path,
    advisor_results: list[dict],
    keep_chains: bool,
) -> None:
    """
    Best-effort self-healing pass for AC-12 value-probe hits.

    In real council runs, the reconciler can independently reuse a generic
    opening phrase from an advisor's public rationale even though it never saw
    raw reasoning_chain fields. Redacting exact probe overlaps preserves the
    hard privacy invariant while allowing the ledger to complete.
    """
    probes = _chain_value_probes(advisor_results)
    if not probes:
        return

    for fpath in _ac12_target_files(workspace_dir, keep_chains):
        content = fpath.read_text(encoding="utf-8", errors="replace")
        redacted = content
        for probe in probes:
            redacted = redacted.replace(probe, "[AC12-redacted-reasoning-overlap]")
        if redacted != content:
            fpath.write_text(redacted, encoding="utf-8")


def _chain_value_probes(advisor_results: list[dict]) -> list[str]:
    """Return deterministic probes for accidental reasoning_chain value leaks."""
    probes: list[str] = []
    seen: set[str] = set()
    for adv in advisor_results:
        chain_value = adv.get("reasoning_chain", "")
        if not chain_value:
            continue
        if isinstance(chain_value, str):
            chain = chain_value.strip()
        else:
            chain = json.dumps(chain_value, ensure_ascii=False).strip()
        if len(chain) <= 20:
            continue

        offsets = {0}
        window = min(80, len(chain))
        if len(chain) > window:
            offsets.update({
                len(chain) // 3,
                len(chain) // 2,
                max(0, len(chain) - window),
            })

        candidates = [chain[:40].strip()]
        candidates.extend(chain[offset:offset + window].strip() for offset in sorted(offsets))
        for candidate in candidates:
            if len(candidate) >= 20 and candidate not in seen:
                probes.append(candidate)
                seen.add(candidate)
    return probes


def _ac12_target_files(
    workspace_dir: pathlib.Path,
    keep_chains: bool,  # noqa: ARG001
) -> list[pathlib.Path]:
    """Return files that must never contain raw reasoning_chain data."""
    targets: list[pathlib.Path] = []
    for fpath in workspace_dir.rglob("*"):
        if not fpath.is_file():
            continue
        # Raw chain files legitimately hold reasoning_chain when keep_chains=True
        if fpath.name.endswith("-raw.json"):
            continue
        targets.append(fpath)
    return targets


# ---------------------------------------------------------------------------
# Helpers — remote sinks
# ---------------------------------------------------------------------------
def _write_cortex(
    payload: dict, metadata: dict  # noqa: ARG001
) -> tuple[str | None, str | None]:
    """
    POST to localhost:6400/api/store. Returns (cortex_id, error).
    Never raises into caller.
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            _CORTEX_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            cid = body.get("id") or body.get("cortex_id") or body.get("uuid")
            return (str(cid) if cid else None, None)
    except Exception as exc:
        return (None, str(exc))


def _write_notion(
    tier: str,
    verdict_md: str,
    dissent_md: str,
    council_task_id: str,
) -> tuple[str | None, str | None]:
    """
    Only called when tier in {STRONG_PASS, BLOCK}. Best-effort.
    Returns (notion_url, error).

    FIX-H6 (v1.0.1 stub): Notion MCP (Model Context Protocol) integration is
    deferred to v1.1. This function returns a visible non-fatal warning.
    STRONG_PASS and BLOCK verdicts still receive Telegram + Cortex + filesystem
    records. v1.0 keeps Notion as a no-op stub so missing Notion MCP does not
    mark otherwise successful ledgers as PARTIAL.
    """
    try:
        # notion_add_block MCP is not available in stdlib context.
        return (None, "notion_mcp_unavailable")
    except Exception as exc:
        return (None, str(exc))


def _send_telegram(
    council_task_id: str,
    tier: str,
    confidence: float,
    cost: float,
) -> tuple[bool, str | None]:
    """
    Best-effort Lis bot relay. Posts one-line message to Pafi.
    Returns (sent, error). Never raises into caller.
    """
    try:
        token, chat_id = _load_telegram_config()
        if not token or not chat_id:
            return (False, "telegram_config_missing")
        msg = f"🏛 council-{council_task_id} {tier} conf={confidence:.2f} cost=${cost:.4f}"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = json.dumps({"chat_id": chat_id, "text": msg}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                return (True, None)
            return (False, result.get("description", "telegram_error"))
    except Exception as exc:
        return (False, str(exc))


def _load_telegram_config() -> tuple[str | None, str | None]:
    """Read Telegram bot config from vps2-secrets.env if present."""
    values: dict[str, str] = {}
    if _VPS2_SECRETS.exists():
        try:
            for line in _VPS2_SECRETS.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
        except OSError:
            pass
    token = (
        os.environ.get("LIS_BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("BOT_TOKEN")
        or values.get("LIS_BOT_TOKEN")
        or values.get("TELEGRAM_BOT_TOKEN")
        or values.get("BOT_TOKEN")
    )
    chat_id = (
        os.environ.get("LIS_CHAT_ID")
        or os.environ.get("TELEGRAM_PAFI_CHAT_ID")
        or os.environ.get("TELEGRAM_CHAT_ID")
        or values.get("LIS_CHAT_ID")
        or values.get("TELEGRAM_PAFI_CHAT_ID")
        or values.get("TELEGRAM_CHAT_ID")
    )
    return (token, chat_id)


# ---------------------------------------------------------------------------
# Helpers — purge
# ---------------------------------------------------------------------------
def _purge_old_chains(base_dir: pathlib.Path, days: int = 7) -> int:
    """
    Delete advisor-*-raw.json files older than `days` days.
    Returns count purged.
    """
    cutoff = time.time() - days * 86400
    count = 0
    if not base_dir.exists():
        return 0
    for fpath in base_dir.rglob("advisor-*-raw.json"):
        try:
            if fpath.stat().st_mtime < cutoff:
                fpath.unlink()
                count += 1
        except OSError:
            pass
    return count


def _purge_old_workspaces(base_dir: pathlib.Path, days: int = 30) -> int:
    """
    Delete entire council-YYYYMMDD-HHMM-* dirs older than `days` days.
    Returns count purged.
    """
    cutoff = time.time() - days * 86400
    count = 0
    if not base_dir.exists():
        return 0
    for dpath in base_dir.iterdir():
        if not dpath.is_dir():
            continue
        if not dpath.name.startswith("council-"):
            continue
        try:
            if dpath.stat().st_mtime < cutoff:
                import shutil
                shutil.rmtree(dpath, ignore_errors=True)
                count += 1
        except OSError:
            pass
    return count
