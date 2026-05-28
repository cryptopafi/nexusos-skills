"""
test_claude_cli_provider.py -- 10 test cases for _call_claude_subprocess (v1.0.3).

All tests mock subprocess.run and shutil.which. NO live CLI calls.

Cases:
  1.  test_call_claude_subprocess_happy_path
  2.  test_call_claude_subprocess_cli_missing
  3.  test_call_claude_subprocess_401_permanent
  4.  test_call_claude_subprocess_model_not_found_permanent
  5.  test_call_claude_subprocess_rate_limit_transient
  6.  test_call_claude_subprocess_timeout_transient
  7.  test_call_claude_subprocess_non_json_output_permanent
  8.  test_call_claude_subprocess_is_error_field
  9.  test_call_claude_subprocess_token_extraction
  10. test_call_anthropic_drops_max_tokens_with_warning
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

import lib._providers as providers_mod
from lib._providers import (
    PermanentProviderError,
    TransientProviderError,
    _call_claude_subprocess,
    _call_anthropic,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HAPPY_JSON = json.dumps({
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": "The answer is 42.",
    "duration_ms": 5000,
    "total_cost_usd": 0.0012,
    "usage": {
        "input_tokens": 80,
        "output_tokens": 12,
        "cache_read_input_tokens": 500,
        "cache_creation_input_tokens": 0,
    },
})


def _make_run_result(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


# ---------------------------------------------------------------------------
# Case 1: happy path — valid JSON response
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessHappyPath:

    def test_call_claude_subprocess_happy_path(self):
        """CLI returns valid JSON → dict with text, tokens, cost_usd."""
        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run", return_value=_make_run_result(stdout=_HAPPY_JSON)):

            result = _call_claude_subprocess(
                model="claude-haiku-4-5",
                system="You are a helpful assistant.",
                user="What is 6 * 7?",
            )

        assert result["text"] == "The answer is 42."
        assert result["tokens"]["in"] == 80
        assert result["tokens"]["out"] == 12
        assert result["cost_usd"] == pytest.approx(0.0012)
        assert result["duration_ms"] == 5000


# ---------------------------------------------------------------------------
# Case 2: claude CLI missing → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessCliMissing:

    def test_call_claude_subprocess_cli_missing(self):
        """shutil.which returns None → PermanentProviderError mentioning install."""
        with patch("lib._providers.shutil.which", return_value=None):
            with pytest.raises(PermanentProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-sonnet-4-6",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "anthropic"
        assert "install" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 3: returncode != 0, stderr contains "401 auth" → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocess401Permanent:

    def test_call_claude_subprocess_401_permanent(self):
        """returncode=1, stderr contains '401 auth' → PermanentProviderError."""
        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   return_value=_make_run_result(returncode=1, stderr="Error: 401 auth credentials invalid")):

            with pytest.raises(PermanentProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-sonnet-4-6",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "anthropic"
        msg = str(exc_info.value).lower()
        assert "auth" in msg or "401" in msg


# ---------------------------------------------------------------------------
# Case 4: stderr contains "invalid model" → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessModelNotFoundPermanent:

    def test_call_claude_subprocess_model_not_found_permanent(self):
        """returncode=1, stderr='invalid model' → PermanentProviderError."""
        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   return_value=_make_run_result(returncode=1, stderr="invalid model: claude-imaginary-99")):

            with pytest.raises(PermanentProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-imaginary-99",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "anthropic"
        assert "model" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 5: stderr contains "rate limit exceeded" → TransientProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessRateLimitTransient:

    def test_call_claude_subprocess_rate_limit_transient(self):
        """returncode=1, stderr mentions 'rate' → TransientProviderError."""
        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   return_value=_make_run_result(returncode=1, stderr="rate limit exceeded, retry after 60s")):

            with pytest.raises(TransientProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-sonnet-4-6",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "anthropic"
        assert "transient" in str(exc_info.value).lower() or "rate" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 6: subprocess.TimeoutExpired → TransientProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessTimeoutTransient:

    def test_call_claude_subprocess_timeout_transient(self):
        """subprocess.TimeoutExpired → TransientProviderError."""
        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60.0)):

            with pytest.raises(TransientProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-sonnet-4-6",
                    system="sys",
                    user="usr",
                    timeout_s=60.0,
                )

        assert exc_info.value.provider == "anthropic"
        assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 7: stdout is not valid JSON → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessNonJsonOutputPermanent:

    def test_call_claude_subprocess_non_json_output_permanent(self):
        """CLI returns non-JSON stdout → PermanentProviderError."""
        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   return_value=_make_run_result(returncode=0, stdout="not json at all!!!")):

            with pytest.raises(PermanentProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-haiku-4-5",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "anthropic"
        assert "non-json" in str(exc_info.value).lower() or "json" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 8: JSON with is_error=true → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessIsErrorField:

    def test_call_claude_subprocess_is_error_field(self):
        """JSON response with is_error=true → PermanentProviderError."""
        error_json = json.dumps({
            "type": "result",
            "is_error": True,
            "api_error_status": "model_not_found",
            "result": "",
        })

        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   return_value=_make_run_result(returncode=0, stdout=error_json)):

            with pytest.raises(PermanentProviderError) as exc_info:
                _call_claude_subprocess(
                    model="claude-haiku-4-5",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "anthropic"
        assert "is_error" in str(exc_info.value).lower() or "model_not_found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Case 9: token extraction — all usage fields present in returned dict
# ---------------------------------------------------------------------------

class TestCallClaudeSubprocessTokenExtraction:

    def test_call_claude_subprocess_token_extraction(self):
        """usage.input_tokens=100, output_tokens=50 → tokens.in=100, tokens.out=50; cache fields present."""
        rich_json = json.dumps({
            "is_error": False,
            "result": "some text",
            "total_cost_usd": 0.0055,
            "duration_ms": 1234,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 300,
                "cache_creation_input_tokens": 10,
            },
        })

        with patch("lib._providers.shutil.which", return_value="/usr/local/bin/claude"), \
             patch("lib._providers.subprocess.run",
                   return_value=_make_run_result(returncode=0, stdout=rich_json)):

            result = _call_claude_subprocess(
                model="claude-sonnet-4-6",
                system="sys",
                user="usr",
            )

        assert result["tokens"]["in"] == 100
        assert result["tokens"]["out"] == 50
        assert result["tokens"]["cache_read"] == 300
        assert result["tokens"]["cache_creation"] == 10
        assert result["cost_usd"] == pytest.approx(0.0055)
        assert result["duration_ms"] == 1234


# ---------------------------------------------------------------------------
# Case 10: _call_anthropic drops non-default max_tokens with stderr warning
# ---------------------------------------------------------------------------

class TestCallAnthropicDropsMaxTokensWithWarning:

    def test_call_anthropic_drops_max_tokens_with_warning(self, monkeypatch: pytest.MonkeyPatch, caplog):
        """Non-default max_tokens → debug log warning emitted; subprocess still called (no error).

        FIX-M1: warning was demoted from sys.stderr.write to logger.debug to suppress
        the 29-line spam produced by the voice-normalizer's sequential Haiku calls.
        Test now uses caplog to capture the log record.
        """
        import logging

        subprocess_result = {
            "text": "ok",
            "tokens": {"in": 5, "out": 3, "cache_read": 0, "cache_creation": 0},
            "cost_usd": 0.0001,
            "duration_ms": 100,
        }
        captured_kwargs: list[dict] = []

        def _spy_subprocess(**kwargs):
            captured_kwargs.append(kwargs)
            return subprocess_result

        monkeypatch.setattr(providers_mod, "_call_claude_subprocess", _spy_subprocess)

        with caplog.at_level(logging.DEBUG, logger="lib._providers"):
            result = _call_anthropic(
                "sonnet-4-6", "claude-sonnet-4-6",
                "sys", "usr",
                max_tokens=512,      # non-default → triggers warning
                temperature=0.7,     # non-default → triggers warning
                timeout_s=30.0,
            )

        # subprocess must have been called
        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["model"] == "claude-sonnet-4-6"

        # result passes through
        assert result["text"] == "ok"

        # debug log must mention v1.0.3 and dropped params
        log_text = " ".join(r.getMessage() for r in caplog.records)
        assert "v1.0.3" in log_text
        assert "max_tokens" in log_text or "temperature" in log_text
