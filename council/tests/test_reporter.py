from __future__ import annotations

from pathlib import Path

from lib.reporter import render_html_report, _report_title, _update_index


def test_advisor_card_labels_do_not_duplicate_advisor_prefix():
    reporter_input = {
        "metadata": {
            "title": "Test Council Report",
            "council_task_id": "test-council",
        },
        "context": {
            "cost_usd": 0.0,
            "nplf": {"n": 3.0, "p": 2.0, "l": 3.0, "f": 2.0},
        },
        "report_markdown": "## Summary\nDone.",
    }
    advisors = [
        {"letter": "A", "verdict": "BLOCK", "confidence": 0.95},
        {"label": "Advisor 2", "verdict": "REVISE", "confidence": 0.78},
    ]
    reconciler = {"tier": "SPLIT", "confidence": 0.82, "verdict_md": "## Summary\nDone."}

    html = render_html_report(reporter_input, advisors, reconciler)

    assert "Advisor Advisor" not in html
    assert "Advisor A" in html
    assert "Advisor 2" in html


def test_report_title_uses_description_not_only_task_id():
    brief = (
        "<council_brief><goal>Audit and improve a high-risk investment strategy "
        "designed to turn $10M into $1B within 10 years.</goal></council_brief>"
    )

    title = _report_title({"tier": "BLOCK"}, "council-20260528-2105-emva", brief)

    assert title.startswith("Block:")
    assert "High-Risk Investment Strategy Council Audit" in title
    assert title.endswith("— council-20260528-2105-emva")
    assert title != "Block Council Report - council-20260528-2105-emva"


def test_report_index_uses_html_title_not_filename(tmp_path: Path):
    (tmp_path / "council-20260528-2105-emva.html").write_text(
        "<html><head><title>Block: High-Risk Investment Strategy Council Audit — "
        "council-20260528-2105-emva</title></head><body></body></html>",
        encoding="utf-8",
    )

    _update_index(tmp_path)

    index = (tmp_path / "council-reports-index.html").read_text(encoding="utf-8")
    assert "Block: High-Risk Investment Strategy Council Audit" in index
    assert "Council 20260528 2105 Emva" not in index
