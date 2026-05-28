from __future__ import annotations

from lib.reporter import render_html_report


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
