"""
Shared-reporter adapter for Council HTML outputs.

The canonical shared-reporter skill is instruction-only in this environment,
so Council emits the same ReporterInput/ReporterOutput contract locally and
renders a GitHub Pages-compatible HTML artifact from AC-12-clean data only.
"""
from __future__ import annotations

import html
import json
import os
import pathlib
import re
import subprocess
from datetime import datetime, timezone
from typing import Any


PAGES_BASE_URL = os.environ.get(
    "COUNCIL_REPORTS_BASE_URL",
    "https://cryptopafi.github.io/nexusos-reports",
)
DEFAULT_PAGES_REPO = pathlib.Path(
    os.environ.get("COUNCIL_REPORTS_REPO", "/Users/pafi/Claude/repos/nexusos-reports")
).expanduser()


def publish_council_report(
    *,
    workspace_dir: pathlib.Path,
    task_id: str,
    council_task_id: str,
    brief_xml: str,
    stripped_advisors: list[dict],
    reconciler_result: dict,
    debate_result: dict | None,
    cost_meter_total: float,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Render and optionally publish a Council report using shared-reporter schema.

    Returns (reporter_output, error). Errors are non-fatal to the ledger caller.
    """
    try:
        reporter_skill = _find_reporter_skill()
        report_markdown = _build_report_markdown(
            brief_xml=brief_xml,
            advisors=stripped_advisors,
            reconciler=reconciler_result,
            debate=debate_result,
            cost=cost_meter_total,
        )
        title = _report_title(reconciler_result, council_task_id)
        reporter_input = {
            "task": "publish",
            "report_type": "session",
            "report_markdown": report_markdown,
            "metadata": {
                "title": title,
                "agent": "genie",
                "date": datetime.now(timezone.utc).date().isoformat(),
                "council_task_id": council_task_id,
                "task_id": task_id,
            },
            "context": {
                "source_skill": "council",
                "reporter_skill": "shared-reporter",
                "reporter_skill_path": str(reporter_skill) if reporter_skill else None,
                "tier": reconciler_result.get("tier", "UNKNOWN"),
                "confidence": reconciler_result.get("confidence"),
                "cost_usd": cost_meter_total,
                "advisor_count": len(stripped_advisors),
                "nplf": _nplf_from(reconciler_result),
            },
            "output_format": "html",
            "tier": 2,
            "deploy_vps": False,
            "deploy_target": "github",
        }

        html_doc = render_html_report(reporter_input, stripped_advisors, reconciler_result)
        _assert_clean_for_external_publish(html_doc, reporter_input, stripped_advisors)

        input_path = workspace_dir / "reporter-input.json"
        html_path = workspace_dir / "report.html"
        output_path = workspace_dir / "reporter-output.json"
        input_path.write_text(json.dumps(reporter_input, indent=2, ensure_ascii=False), encoding="utf-8")
        html_path.write_text(html_doc, encoding="utf-8")

        share_url = None
        github_path = None
        if _deploy_enabled():
            share_url, github_path = _publish_to_github_pages(
                html_doc=html_doc,
                council_task_id=council_task_id,
                title=title,
            )

        reporter_output = {
            "agent": "shared-reporter",
            "status": "published" if share_url else "rendered_local",
            "result": {
                "files": {
                    "input": str(input_path),
                    "html": str(html_path),
                    "output": str(output_path),
                    "github_pages_file": str(github_path) if github_path else None,
                },
                "share_url": share_url or str(html_path),
                "fallback_url": str(html_path),
                "github_pages_url": share_url,
                "vps_url": None,
                "metadata": reporter_input["metadata"],
            },
        }
        output_path.write_text(json.dumps(reporter_output, indent=2, ensure_ascii=False), encoding="utf-8")
        return reporter_output, None
    except Exception as exc:
        return None, str(exc)


def render_html_report(
    reporter_input: dict[str, Any],
    advisors: list[dict],
    reconciler: dict,
) -> str:
    title = str(reporter_input["metadata"]["title"])
    tier = str(reconciler.get("tier", "UNKNOWN"))
    confidence = _as_float(reconciler.get("confidence"))
    cost = _as_float(reporter_input["context"].get("cost_usd"))
    nplf = reporter_input["context"].get("nplf") if isinstance(reporter_input["context"].get("nplf"), dict) else {}
    nplf_avg = sum(nplf.values()) / len(nplf) if nplf else None
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subtitle = _first_sentence(str(reconciler.get("verdict_md") or reporter_input["report_markdown"]))

    return HTML_TEMPLATE.format(
        title=_esc(title),
        subtitle=_esc(subtitle),
        generated=_esc(generated),
        tier=_esc(tier),
        confidence=f"{confidence:.2f}" if confidence is not None else "n/a",
        nplf_avg=f"{nplf_avg:.2f}/4" if nplf_avg is not None else "n/a",
        cost=f"${cost:.4f}" if cost is not None else "n/a",
        task=_esc(str(reporter_input["metadata"].get("council_task_id", ""))),
        vote_summary=_vote_summary(advisors, tier),
        decision_flow=_decision_flow(advisors, tier),
        advisor_cards=_advisor_cards(advisors),
        advisor_rows=_advisor_rows(advisors),
        nplf_rows=_nplf_rows(nplf),
        narrative=_markdown_to_html(reporter_input["report_markdown"]),
        raw_json=_esc(json.dumps(_public_raw_payload(reporter_input, advisors, reconciler), indent=2, ensure_ascii=False)[:20000]),
    )


def _find_reporter_skill() -> pathlib.Path | None:
    explicit = os.environ.get("COUNCIL_REPORTER_SKILL")
    candidates = []
    if explicit:
        candidates.append(pathlib.Path(explicit).expanduser())
    home = pathlib.Path.home()
    candidates.extend(
        [
            home / ".agents" / "skills" / "shared-reporter" / "SKILL.md",
            home / ".codex" / "skills" / "shared-reporter" / "SKILL.md",
            home / ".claude" / "skills" / "shared-reporter" / "SKILL.md",
            home / ".hermes" / "skills" / "shared-reporter" / "SKILL.md",
            home / ".nexus" / "v2" / "shared-skills" / "reporter" / "SKILL.md",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    return None


def _deploy_enabled() -> bool:
    value = os.environ.get("COUNCIL_REPORTER_DEPLOY", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _publish_to_github_pages(
    *,
    html_doc: str,
    council_task_id: str,
    title: str,
) -> tuple[str | None, pathlib.Path | None]:
    repo = DEFAULT_PAGES_REPO
    if not (repo / ".git").exists():
        return None, None

    filename = f"{_slugify(council_task_id or title)}.html"
    target = repo / filename
    target.write_text(html_doc, encoding="utf-8")
    _update_index(repo)
    if os.environ.get("COUNCIL_REPORTER_GIT", "1").strip().lower() not in {"0", "false", "no", "off"}:
        _git_commit_if_needed(repo, [filename, "council-reports-index.html"], f"Publish Council report {council_task_id}")
    return f"{PAGES_BASE_URL}/{filename}", target


def _update_index(repo: pathlib.Path) -> None:
    reports = sorted(repo.glob("*.html"))
    rows = []
    for path in reports:
        if path.name == "council-reports-index.html":
            continue
        title = path.stem.replace("-", " ").title()
        rows.append(
            f"<tr><td><a href='{_esc(path.name)}'>{_esc(title)}</a></td>"
            f"<td><code>{_esc(path.name)}</code></td></tr>"
        )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    index = INDEX_TEMPLATE.format(generated=_esc(generated), rows="\n".join(rows), count=len(rows))
    (repo / "council-reports-index.html").write_text(index, encoding="utf-8")


def _git_commit_if_needed(repo: pathlib.Path, files: list[str], message: str) -> None:
    _run(["git", "add", *files], repo)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        return
    _run(["git", "commit", "-m", message], repo)
    _run(["git", "push", "origin", "main"], repo)


def _run(cmd: list[str], cwd: pathlib.Path) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True, timeout=60)
    return proc.stdout.strip()


def _build_report_markdown(
    *,
    brief_xml: str,
    advisors: list[dict],
    reconciler: dict,
    debate: dict | None,
    cost: float,
) -> str:
    parts = [
        "# Council Report",
        "",
        "## Final Verdict",
        str(reconciler.get("verdict_md") or "No verdict text provided."),
        "",
        "## Dissent",
        str(reconciler.get("dissent_md") or "No dissent recorded."),
        "",
        "## Advisor Positions",
        _advisor_markdown(advisors),
        "",
        "## Scoring",
        _score_markdown(reconciler, cost),
        "",
        "## Source Brief",
        brief_xml.strip() or "No brief provided.",
    ]
    if debate:
        parts.extend(["", "## Debate Revision", json.dumps(_clean_public(debate), indent=2, ensure_ascii=False)])
    return "\n".join(parts).strip() + "\n"


def _advisor_markdown(advisors: list[dict]) -> str:
    lines = []
    for idx, advisor in enumerate(advisors, start=1):
        label = advisor.get("label") or f"Advisor {idx}"
        recommendation = advisor.get("recommendation") or advisor.get("verdict") or "n/a"
        confidence = advisor.get("confidence", "n/a")
        strengths = _list_text(advisor.get("top_strengths") or advisor.get("strengths"))
        risks = _list_text(advisor.get("top_risks") or advisor.get("risks"))
        lines.append(
            f"### {label}\n"
            f"- Position: {recommendation}\n"
            f"- Confidence: {confidence}\n"
            f"- Agrees on: {strengths or 'not specified'}\n"
            f"- Disagrees or warns on: {risks or 'not specified'}"
        )
    return "\n\n".join(lines) if lines else "No advisor positions found."


def _score_markdown(reconciler: dict, cost: float) -> str:
    nplf = _nplf_from(reconciler)
    lines = [
        f"- Tier: {reconciler.get('tier', 'UNKNOWN')}",
        f"- Confidence: {reconciler.get('confidence', 'n/a')}",
        f"- Cost: ${cost:.4f}",
    ]
    if nplf:
        lines.extend(f"- {key.upper()}: {value:.2f}/4" for key, value in nplf.items())
    return "\n".join(lines)


def _nplf_from(reconciler: dict) -> dict[str, float]:
    raw = reconciler.get("nplf")
    if not isinstance(raw, dict):
        raw = reconciler.get("scores") if isinstance(reconciler.get("scores"), dict) else {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, (int, float)):
            out[str(key).lower()] = float(value)
    return out


def _assert_clean_for_external_publish(
    html_doc: str,
    reporter_input: dict[str, Any],
    advisors: list[dict],
) -> None:
    payload = html_doc + "\n" + json.dumps(reporter_input, ensure_ascii=False)
    if "reasoning_chain" in payload:
        raise ValueError("reporter payload contains reasoning_chain")
    for advisor in advisors:
        if "reasoning_chain" in advisor:
            raise ValueError("stripped advisor still contains reasoning_chain")


def _public_raw_payload(
    reporter_input: dict[str, Any],
    advisors: list[dict],
    reconciler: dict,
) -> dict[str, Any]:
    return {
        "reporter_input": _clean_public(reporter_input),
        "advisors": _clean_public(advisors),
        "reconciler": _clean_public(reconciler),
    }


def _clean_public(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean_public(v) for k, v in value.items() if k != "reasoning_chain"}
    if isinstance(value, list):
        return [_clean_public(item) for item in value]
    return value


def _advisor_rows(advisors: list[dict]) -> str:
    if not advisors:
        return "<tr><td colspan='5'>No advisor rows available.</td></tr>"
    rows = []
    for idx, advisor in enumerate(advisors, start=1):
        label = advisor.get("label") or f"Advisor {idx}"
        recommendation = advisor.get("recommendation") or advisor.get("verdict") or "n/a"
        confidence = advisor.get("confidence", "n/a")
        agrees = _list_text(advisor.get("top_strengths") or advisor.get("strengths"))
        risks = _list_text(advisor.get("top_risks") or advisor.get("risks"))
        rows.append(
            "<tr>"
            f"<td><strong>{_esc(label)}</strong></td>"
            f"<td><span class='pill'>{_esc(recommendation)}</span></td>"
            f"<td>{_esc(confidence)}</td>"
            f"<td>{_esc(agrees or 'not specified')}</td>"
            f"<td>{_esc(risks or 'not specified')}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _vote_summary(advisors: list[dict], tier: str) -> str:
    counts: dict[str, int] = {}
    for advisor in advisors:
        verdict = str(advisor.get("recommendation") or advisor.get("verdict") or "n/a").upper()
        counts[verdict] = counts.get(verdict, 0) + 1
    votes = " / ".join(f"{count} {verdict}" for verdict, count in sorted(counts.items()))
    return (
        f"<section class='decision-band'>"
        f"<div><small>Committee Shape</small><strong>{_esc(votes or 'No advisor votes')}</strong>"
        f"<span>Final reconciler tier: {_esc(tier)}</span></div>"
        f"<div><small>How To Read</small><strong>Vote → Motivation → Objection → Synthesis</strong>"
        f"<span>The report shows what each advisor believed, where they split, and why the final tier followed.</span></div>"
        f"</section>"
    )


def _decision_flow(advisors: list[dict], tier: str) -> str:
    votes = [str(a.get("recommendation") or a.get("verdict") or "n/a").upper() for a in advisors]
    vote_text = " + ".join(votes) if votes else "No votes"
    return (
        "<section class='flow' aria-label='Decision flow'>"
        "<div class='flow-step'><small>1</small><strong>Independent advisors</strong>"
        f"<span>{_esc(vote_text)}</span></div>"
        "<div class='flow-arrow'>→</div>"
        "<div class='flow-step'><small>2</small><strong>Agreement / dissent map</strong>"
        "<span>Shared claims and explicit objections are separated.</span></div>"
        "<div class='flow-arrow'>→</div>"
        "<div class='flow-step'><small>3</small><strong>Final synthesis</strong>"
        f"<span>{_esc(tier)} after weighing public advisor positions.</span></div>"
        "</section>"
    )


def _advisor_cards(advisors: list[dict]) -> str:
    if not advisors:
        return "<p class='muted'>No advisor rationale cards available.</p>"
    cards = []
    for idx, advisor in enumerate(advisors, start=1):
        label = advisor.get("label") or f"Advisor {idx}"
        verdict = str(advisor.get("recommendation") or advisor.get("verdict") or "n/a").upper()
        confidence = advisor.get("confidence", "n/a")
        strengths = advisor.get("top_strengths") or advisor.get("strengths") or []
        risks = advisor.get("top_risks") or advisor.get("risks") or []
        motivation = _first_list_item(strengths) or "No public motivation recorded."
        objection = _first_list_item(risks) or "No public objection recorded."
        cards.append(
            f"<article class='advisor-card vote-{_verdict_class(verdict)}'>"
            f"<div class='advisor-head'><span>Advisor {_esc(label)}</span>"
            f"<b>{_esc(verdict)}</b></div>"
            f"<div class='confidence'><span>Confidence</span><strong>{_esc(confidence)}</strong></div>"
            f"<h3>Why this advisor voted this way</h3><p>{_esc(motivation)}</p>"
            f"<h3>Main objection or warning</h3><p>{_esc(objection)}</p>"
            f"</article>"
        )
    return "<section class='advisor-cards'>" + "\n".join(cards) + "</section>"


def _nplf_rows(nplf: dict[str, float]) -> str:
    if not nplf:
        return "<p class='muted'>No NPLF score was present.</p>"
    labels = {"n": "Need", "p": "Plan", "l": "Leverage", "f": "Fit"}
    rows = []
    for key, value in nplf.items():
        pct = max(0.0, min(100.0, float(value) / 4.0 * 100.0))
        rows.append(
            f"<div class='score'><span>{_esc(labels.get(key, key.upper()))}</span>"
            f"<b><i style='width:{pct:.1f}%'></i></b><strong>{float(value):.2f}</strong></div>"
        )
    return "\n".join(rows)


def _markdown_to_html(markdown: str) -> str:
    out: list[str] = []
    in_list = False
    for line in markdown.splitlines():
        if line.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{_esc(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{_esc(line[4:].strip())}</h3>")
        elif re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append("<li>" + _inline_md(re.sub(r"^\s*[-*]\s+", "", line)) + "</li>")
        elif line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{_inline_md(line.strip())}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _inline_md(text: str) -> str:
    text = _esc(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def _report_title(reconciler: dict, council_task_id: str) -> str:
    verdict = str(reconciler.get("tier", "Council")).replace("_", " ").title()
    return f"{verdict} Council Report - {council_task_id}"


def _first_sentence(text: str, limit: int = 260) -> str:
    clean = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return "Council report generated from the reconciled advisor record."
    match = re.search(r"(.{40,}?[.!?])\s", clean)
    snippet = match.group(1) if match else clean[:limit]
    return snippet[:limit].rstrip()


def _list_text(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value[:3] if item)
    if isinstance(value, str):
        return value
    return ""


def _first_list_item(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            if item:
                return str(item)
        return ""
    if isinstance(value, str):
        return value
    return ""


def _verdict_class(verdict: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", verdict.lower()).strip("-")
    return clean or "unknown"


def _as_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _slugify(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return re.sub(r"-+", "-", clean).strip("-") or "council-report"


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: dark; --bg:#111; --panel:#1b1b1b; --panel2:#242424; --line:#303030; --text:#e8e8e8; --muted:#a0a0a0; --green:#5bc46b; --amber:#f0a631; --red:#e5534b; --blue:#76a9ff; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:radial-gradient(circle at 16% 0%, #1f2937 0, transparent 28rem), var(--bg); color:var(--text); font:14px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:30px 24px 60px; }}
.top {{ display:flex; justify-content:space-between; gap:16px; align-items:center; margin-bottom:26px; }}
.brand {{ font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }}
button {{ border:1px solid var(--line); background:var(--panel); color:var(--text); border-radius:8px; padding:8px 12px; }}
.hero {{ padding:28px 0 22px; border-bottom:1px solid var(--line); }}
h1 {{ font-size:clamp(32px, 5vw, 58px); line-height:1.02; margin:0 0 14px; letter-spacing:0; }}
.subtitle {{ max-width:850px; color:var(--muted); font-size:17px; }}
.meta {{ margin-top:16px; color:var(--muted); font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; }}
.grid {{ display:grid; gap:16px; }}
.metrics {{ grid-template-columns:repeat(5, minmax(0,1fr)); margin:22px 0; }}
.two {{ grid-template-columns:minmax(0,.85fr) minmax(0,1.15fr); align-items:start; }}
.card {{ background:color-mix(in srgb, var(--panel) 92%, transparent); border:1px solid var(--line); border-radius:8px; padding:18px; box-shadow:0 16px 38px rgba(0,0,0,.25); }}
.decision-band {{ display:grid; grid-template-columns:1fr 1.25fr; gap:16px; margin:0 0 16px; }}
.decision-band div {{ border:1px solid var(--line); border-radius:8px; padding:16px 18px; background:linear-gradient(135deg, rgba(118,169,255,.14), rgba(27,27,27,.95)); }}
.decision-band small,.flow-step small {{ color:var(--muted); text-transform:uppercase; letter-spacing:.08em; display:block; }}
.decision-band strong {{ display:block; font-size:20px; margin:6px 0; }}
.decision-band span,.flow-step span {{ color:var(--muted); }}
.flow {{ display:grid; grid-template-columns:1fr 34px 1fr 34px 1fr; align-items:stretch; gap:10px; margin:0 0 16px; }}
.flow-step {{ border:1px solid var(--line); border-radius:8px; padding:14px; background:var(--panel); }}
.flow-step strong {{ display:block; margin:6px 0; font-size:16px; }}
.flow-arrow {{ display:grid; place-items:center; color:var(--muted); font-size:22px; }}
.advisor-cards {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:16px; margin:0 0 16px; }}
.advisor-card {{ border:1px solid var(--line); border-radius:8px; padding:16px; background:var(--panel); }}
.advisor-card.vote-pass {{ border-top:4px solid var(--green); }}
.advisor-card.vote-revise,.advisor-card.vote-split {{ border-top:4px solid var(--amber); }}
.advisor-card.vote-block,.advisor-card.vote-abstain {{ border-top:4px solid var(--red); }}
.advisor-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
.advisor-head span {{ color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-size:12px; }}
.advisor-head b {{ border:1px solid var(--line); border-radius:999px; padding:4px 10px; background:#151515; }}
.confidence {{ display:flex; justify-content:space-between; align-items:center; margin:12px 0 8px; padding:8px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
.confidence span {{ color:var(--muted); }}
.advisor-card h3 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:14px 0 5px; }}
.advisor-card p {{ margin:0; }}
.metric small {{ color:var(--muted); text-transform:uppercase; letter-spacing:.08em; display:block; }}
.metric strong {{ display:block; font-size:24px; margin:8px 0 2px; overflow-wrap:anywhere; }}
.metric span {{ color:var(--muted); }}
h2 {{ margin:0 0 14px; font-size:22px; }}
h3 {{ margin:18px 0 8px; color:var(--blue); }}
.score {{ display:grid; grid-template-columns:130px minmax(120px, 1fr) 52px; align-items:center; gap:12px; margin:11px 0; }}
.score b {{ height:16px; background:#111; border:1px solid var(--line); border-radius:999px; overflow:hidden; }}
.score i {{ display:block; height:100%; border-radius:999px; background:linear-gradient(90deg, var(--red), var(--amber), var(--green)); }}
.table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; }}
table {{ border-collapse:collapse; width:100%; min-width:760px; background:var(--panel); }}
th,td {{ border-bottom:1px solid var(--line); padding:11px 12px; text-align:left; vertical-align:top; }}
th {{ background:var(--panel2); color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
tr:hover td {{ background:rgba(255,255,255,.025); }}
.pill {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:3px 9px; background:#151515; font-weight:700; }}
.narrative {{ margin-top:16px; }}
.narrative p {{ margin:9px 0; }}
.narrative ul {{ padding-left:22px; }}
code {{ background:#101010; border:1px solid var(--line); border-radius:5px; padding:1px 5px; }}
pre {{ max-height:420px; overflow:auto; background:#090909; border:1px solid var(--line); border-radius:8px; padding:14px; }}
.muted {{ color:var(--muted); }}
summary {{ cursor:pointer; color:var(--muted); }}
a {{ color:var(--blue); text-decoration:none; }}
@media (max-width:880px) {{ .metrics,.two {{ grid-template-columns:1fr; }} .score {{ grid-template-columns:100px minmax(90px,1fr) 46px; }} }}
@media (max-width:980px) {{ .decision-band,.advisor-cards,.flow {{ grid-template-columns:1fr; }} .flow-arrow {{ display:none; }} }}
</style>
</head>
<body>
<main class="wrap">
  <nav class="top"><div class="brand">Council Report</div><button onclick="navigator.clipboard.writeText(location.href).then(()=>this.textContent='Copied')">Share</button></nav>
  <header class="hero"><h1>{title}</h1><p class="subtitle">{subtitle}</p><div class="meta">Generated {generated} | Task {task}</div></header>
  <section class="grid metrics">
    <article class="card metric"><small>Outcome</small><strong>{tier}</strong><span>Verdict</span></article>
    <article class="card metric"><small>Certainty</small><strong>{confidence}</strong><span>Confidence</span></article>
    <article class="card metric"><small>Quality</small><strong>{nplf_avg}</strong><span>NPLF average</span></article>
    <article class="card metric"><small>Run Spend</small><strong>{cost}</strong><span>Cost</span></article>
    <article class="card metric"><small>Evidence</small><strong>3</strong><span>Advisors</span></article>
  </section>
  {vote_summary}
  {decision_flow}
  {advisor_cards}
  <section class="grid two">
    <article class="card"><h2>NPLF Scorecard</h2>{nplf_rows}</article>
    <article class="card"><h2>Advisor Matrix</h2><div class="table-wrap"><table><thead><tr><th>Advisor</th><th>Position</th><th>Confidence</th><th>Agrees On</th><th>Disagrees / Warns On</th></tr></thead><tbody>{advisor_rows}</tbody></table></div></article>
  </section>
  <section class="card narrative"><h2>Decision Trace</h2>{narrative}</section>
  <details class="card narrative"><summary>Public structured artifact</summary><pre><code>{raw_json}</code></pre></details>
</main>
</body>
</html>
"""


INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Council Reports Index</title>
<style>
body {{ margin:0; background:#111; color:#e8e8e8; font:14px/1.5 Inter, system-ui, sans-serif; }}
.wrap {{ max-width:1120px; margin:0 auto; padding:36px 24px; }}
h1 {{ font-size:46px; margin:0 0 10px; }}
p {{ color:#aaa; }}
table {{ width:100%; border-collapse:collapse; background:#1b1b1b; border:1px solid #303030; border-radius:8px; overflow:hidden; }}
th,td {{ padding:12px; border-bottom:1px solid #303030; text-align:left; vertical-align:top; }}
th {{ background:#242424; color:#aaa; text-transform:uppercase; font-size:12px; letter-spacing:.06em; }}
a {{ color:#76a9ff; text-decoration:none; }}
code {{ color:#bbb; }}
</style>
</head>
<body><main class="wrap">
<h1>Council Reports</h1>
<p>{count} rendered Council reports. Generated {generated}.</p>
<table><thead><tr><th>Report</th><th>File</th></tr></thead><tbody>{rows}</tbody></table>
</main></body></html>
"""
