---
name: shared-reporter-stall-recovery
description: Use when shared-reporter subagent stalls or times out rendering large D3/D4 research reports
---

# Problema

shared-reporter subagent stalls or times out when rendering D3/D4 research reports >80KB markdown, either by going down a dependency-install rabbit hole (markdown library), getting stuck mid-generation trying to write inline HTML in a single Write call, or hitting context limits mid-render. Two separate attempts in one session failed this way, costing ~15 minutes each.

# Procedura

Direct Python + scp path for large markdown → HTML reports. Bypasses shared-reporter subagent entirely for reports >80KB or when subagent has failed once.

## Steps

1. Confirm Python markdown package available: `python3 -c "import markdown; print(markdown.__version__)"`. If missing: `pip3 install --user markdown`.
2. Write generator script to `/tmp/gen_report.py` with inline Tier 2 HTML template (dark-first glassmorphism, Inter + JetBrains Mono via Google Fonts, Tailwind CDN, Chart.js CDN, sticky TOC, EPR panel, dark/light toggle, print CSS, OG tags, share button). Template uses `__BODY__` and `__TOC__` placeholders.
3. In the script: `markdown.Markdown(extensions=['tables', 'toc', 'fenced_code', 'attr_list', 'sane_lists'])`, then `md.convert(md_text)` for body and `md.toc` for sidebar.
4. Optional visual dividers: use string .replace() to inject custom HTML blocks at known markdown headings (e.g. Part boundaries in multi-part reports).
5. Run `python3 /tmp/gen_report.py` → produces `/tmp/reporter-cf-final.html`.
6. Read VPS config from `~/.nexus/config/vps.yaml` (keys: vps_host, vps_user, vps_report_path).
7. scp with timestamped filename: `scp /tmp/reporter-cf-final.html pafi@89.116.229.189:/var/www/nexus/{slug}-$(date +%Y%m%d-%H%M%S).html`
8. Verify HTTP 200: `curl -sI -k https://89.116.229.189/nexus/{file} | head -5`
9. Return VPS URL to user.

## Performance

Direct approach: ~30 seconds end-to-end (generator run + scp + verify).
shared-reporter subagent approach (when it works): 2-10 minutes.
shared-reporter subagent approach (when it stalls): 15+ minutes, may need kill + redispatch.

# Enforcement Loop

Trigger: D3/D4 research report >80KB markdown OR shared-reporter subagent has failed/stalled once in current session.
Check: Is the merged markdown file >80KB? Has shared-reporter been dispatched and returned stalled/killed once already?
Action: Skip subsequent shared-reporter dispatches. Write generator script directly with Write tool, run with Bash, scp to VPS, verify. Do not retry shared-reporter more than once per session for large reports.
Fallback: If Python markdown library cannot be installed (locked environment), fall back to manual section-by-section Write calls, but prefer pandoc if available.
