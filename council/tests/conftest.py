"""
conftest.py — Shared pytest fixtures for the /council skill test suite.

FIX-C1: _preflight_provider_check is an environment guard (checks for
OPENAI_API_KEY, GEMINI_API_KEY, claude CLI). Unit and acceptance tests run
with mocked advisor lanes and do not require real credentials, so the
preflight check is bypassed for all non-live tests via autouse fixture.

Live tests (COUNCIL_LIVE_TESTS=1) skip this bypass intentionally — they
exercise the real provider chain and need the preflight to be active.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def _bypass_preflight_in_unit_tests(monkeypatch, request):
    """
    Bypass _preflight_provider_check for all non-live, non-preflight tests.

    Live tests need real credentials. Preflight unit tests (marked
    'test_preflight') test the function directly and must not be patched.
    For every other test the preflight is patched to return [] so missing
    real credentials don't block the mocked-provider test suite.
    """
    # Skip bypass for live tests — they need real credentials
    if request.node.get_closest_marker("live"):
        return
    if os.environ.get("COUNCIL_LIVE_TESTS") == "1":
        return
    # Skip bypass for tests that directly exercise _preflight_provider_check
    if request.node.get_closest_marker("preflight_unit"):
        return

    # Council reporter publishes to GitHub Pages in production. Unit tests keep
    # that path disabled unless a test opts in and monkeypatches the publisher.
    monkeypatch.setenv("COUNCIL_REPORTER_ENABLED", "0")

    # Patch at the orchestrator module level so all call sites are covered.
    # Use bypass=kwarg-aware lambda to match updated signature (MED-1 fix).
    try:
        monkeypatch.setattr(
            "lib.orchestrator._preflight_provider_check",
            lambda depth, min_quorum, bypass=False: [],
        )
    except AttributeError:
        # orchestrator module not imported yet in some isolated unit tests — safe to skip.
        import sys as _sys
        _sys.stderr.write(
            f"[conftest] preflight bypass skipped for {request.node.nodeid!r} "
            "(orchestrator not yet imported — OK for pure-unit tests)\n"
        )
