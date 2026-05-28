"""
test_oauth_providers.py -- 12 test cases for _oauth.py + OAuth-aware _providers.py paths.

v1.0.2 OAuth rewrite. All tests mock subprocess/filesystem — NO live API calls.

Cases:
  1.  test_anthropic_oauth_from_keychain
  2.  test_anthropic_oauth_falls_back_to_credentials_file
  3.  test_anthropic_oauth_falls_back_to_env
  4.  test_anthropic_oauth_all_paths_fail_raises
  5.  test_codex_auth_present_true
  6.  test_codex_auth_present_false_missing
  7.  test_codex_token_age_decode_valid_jwt
  8.  test_codex_token_age_decode_invalid_returns_none
  9.  test_call_codex_subprocess_happy_path
  10. test_call_codex_subprocess_401_permanent
  11. test_call_codex_subprocess_timeout_transient
  12. test_call_codex_subprocess_cli_missing_permanent
  13. test_call_openai_with_use_responses_api_routes_to_codex
  14. test_call_openai_without_flag_routes_to_codex
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

import lib._oauth as oauth_mod
from lib._oauth import (
    OAuthLoadError,
    codex_auth_present,
    codex_token_age_seconds,
    load_anthropic_oauth_token,
    load_gemini_api_key,
)
import lib._providers as providers_mod
from lib._providers import (
    PermanentProviderError,
    TransientProviderError,
    _call_codex_subprocess,
    _call_openai,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt_with_exp(exp_timestamp: int) -> str:
    """Build a minimal JWT token with an exp claim in the payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').rstrip(b"=").decode()
    payload_data = json.dumps({"exp": exp_timestamp, "sub": "user123"}).encode()
    payload = base64.urlsafe_b64encode(payload_data).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# Case 1: Anthropic OAuth from keychain (happy path)
# ---------------------------------------------------------------------------

class TestAnthropicOAuthFromKeychain:

    def test_anthropic_oauth_from_keychain(self, monkeypatch: pytest.MonkeyPatch):
        """Keychain returns valid JSON creds → access_token extracted and returned."""
        creds_json = json.dumps({
            "tokens": {"access_token": "keychain-token-abc123"},
        })

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = creds_json

        with patch("lib._oauth.subprocess.run", return_value=mock_result):
            token = load_anthropic_oauth_token()

        assert token == "keychain-token-abc123"

    def test_anthropic_oauth_from_keychain_top_level_access_token(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Keychain JSON uses top-level access_token (not nested under tokens)."""
        creds_json = json.dumps({"access_token": "flat-token-xyz"})

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = creds_json

        with patch("lib._oauth.subprocess.run", return_value=mock_result):
            token = load_anthropic_oauth_token()

        assert token == "flat-token-xyz"


# ---------------------------------------------------------------------------
# Case 2: Anthropic OAuth falls back to credentials file
# ---------------------------------------------------------------------------

class TestAnthropicOAuthCredentialsFileFallback:

    def test_anthropic_oauth_falls_back_to_credentials_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Keychain fails (returncode != 0) → falls back to ~/.claude/.credentials.json."""
        # Make keychain fail
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        creds_file = tmp_path / ".credentials.json"
        creds_file.write_text(
            json.dumps({"tokens": {"access_token": "file-token-def456"}}),
            encoding="utf-8",
        )

        with patch("lib._oauth.subprocess.run", return_value=mock_result), \
             patch("lib._oauth.pathlib.Path.home", return_value=tmp_path / "home"):
            # Patch creds_file lookup to use our tmp path
            with patch.object(
                oauth_mod.pathlib.Path,
                "home",
                return_value=tmp_path,
            ):
                # Write to the expected path relative to tmp_path
                (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
                (tmp_path / ".claude" / ".credentials.json").write_text(
                    json.dumps({"tokens": {"access_token": "file-token-def456"}}),
                    encoding="utf-8",
                )
                token = load_anthropic_oauth_token()

        assert token == "file-token-def456"


# ---------------------------------------------------------------------------
# Case 3: Anthropic OAuth falls back to env var
# ---------------------------------------------------------------------------

class TestAnthropicOAuthEnvFallback:

    def test_anthropic_oauth_falls_back_to_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Both keychain and credentials file unavailable → ANTHROPIC_API_KEY env used."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-fallback-key-ghi789")

        with patch("lib._oauth.subprocess.run", return_value=mock_result), \
             patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            # No .credentials.json in tmp_path/.claude/
            token = load_anthropic_oauth_token()

        assert token == "env-fallback-key-ghi789"


# ---------------------------------------------------------------------------
# Case 4: All OAuth paths fail → OAuthLoadError
# ---------------------------------------------------------------------------

class TestAnthropicOAuthAllPathsFail:

    def test_anthropic_oauth_all_paths_fail_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """All 3 credential sources unavailable → OAuthLoadError mentioning setup-token."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("lib._oauth.subprocess.run", return_value=mock_result), \
             patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            with pytest.raises(OAuthLoadError) as exc_info:
                load_anthropic_oauth_token()

        assert "setup-token" in str(exc_info.value)
        assert "anthropic" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 5: codex_auth_present — true when file exists and non-empty
# ---------------------------------------------------------------------------

class TestCodexAuthPresent:

    def test_codex_auth_present_true(self, tmp_path: Path):
        """auth.json exists and has content → True."""
        (tmp_path / ".codex").mkdir()
        auth_file = tmp_path / ".codex" / "auth.json"
        auth_file.write_text(json.dumps({"access_token": "tok"}), encoding="utf-8")

        with patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            result = codex_auth_present()

        assert result is True

    def test_codex_auth_present_false_missing(self, tmp_path: Path):
        """auth.json does not exist → False."""
        with patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            result = codex_auth_present()

        assert result is False

    def test_codex_auth_present_false_empty(self, tmp_path: Path):
        """auth.json exists but is too small (≤10 bytes) → False."""
        (tmp_path / ".codex").mkdir()
        auth_file = tmp_path / ".codex" / "auth.json"
        auth_file.write_text("{}", encoding="utf-8")  # 2 bytes

        with patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            result = codex_auth_present()

        assert result is False


# ---------------------------------------------------------------------------
# Case 6: codex_token_age_seconds — valid JWT decode
# ---------------------------------------------------------------------------

class TestCodexTokenAge:

    def test_codex_token_age_decode_valid_jwt(self, tmp_path: Path):
        """Valid JWT with exp claim → age computed correctly."""
        # Set exp to 1000 seconds ago
        exp_ts = int(time.time()) - 1000
        jwt_token = _make_jwt_with_exp(exp_ts)
        auth_data = json.dumps({"tokens": {"access_token": jwt_token}})

        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "auth.json").write_text(auth_data, encoding="utf-8")

        with patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            age = codex_token_age_seconds()

        # Token expired 1000s ago → age ≈ +1000 (positive = expired)
        assert age is not None
        assert 990 < age < 1010, f"Expected age ~1000, got {age}"

    def test_codex_token_age_decode_invalid_returns_none(self, tmp_path: Path):
        """Auth file with non-JWT token → returns None without raising."""
        auth_data = json.dumps({"access_token": "not-a-jwt"})

        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "auth.json").write_text(auth_data, encoding="utf-8")

        with patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            age = codex_token_age_seconds()

        assert age is None

    def test_codex_token_age_missing_file_returns_none(self, tmp_path: Path):
        """auth.json missing → returns None."""
        with patch.object(oauth_mod.pathlib.Path, "home", return_value=tmp_path):
            age = codex_token_age_seconds()

        assert age is None


# ---------------------------------------------------------------------------
# Case 7: _call_codex_subprocess — happy path
# ---------------------------------------------------------------------------

class TestCallCodexSubprocessHappyPath:

    def test_call_codex_subprocess_happy_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Subprocess succeeds → returns dict with text and estimated tokens."""
        # Ensure codex_auth_present returns True
        with patch("lib._providers.codex_auth_present", return_value=True), \
             patch("lib._providers.shutil.which", return_value="/usr/local/bin/codex"):

            output_text = "This is the advisor response text."

            def _fake_run(cmd, stdin, capture_output, text, timeout):
                # Write output to the -o file argument
                o_index = cmd.index("-o")
                out_file = cmd[o_index + 1]
                Path(out_file).write_text(output_text, encoding="utf-8")
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            with patch("lib._providers.subprocess.run", side_effect=_fake_run):
                result = _call_codex_subprocess(
                    model="gpt-5.5",
                    system="You are an advisor.",
                    user="Should we expand to EU?",
                )

        assert result["text"] == output_text
        assert result["tokens"]["in"] > 0
        assert result["tokens"]["out"] > 0


# ---------------------------------------------------------------------------
# Case 8: _call_codex_subprocess — 401 auth failure → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallCodexSubprocess401Permanent:

    def test_call_codex_subprocess_401_permanent(self, monkeypatch: pytest.MonkeyPatch):
        """Subprocess returns rc=1 with '401' in stderr → PermanentProviderError."""
        with patch("lib._providers.codex_auth_present", return_value=True), \
             patch("lib._providers.shutil.which", return_value="/usr/local/bin/codex"):

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: 401 Unauthorized — token expired or invalid"

            with patch("lib._providers.subprocess.run", return_value=mock_result):
                with pytest.raises(PermanentProviderError) as exc_info:
                    _call_codex_subprocess(
                        model="gpt-5.5",
                        system="sys",
                        user="usr",
                    )

        assert exc_info.value.provider == "openai"
        assert "auth" in str(exc_info.value).lower() or "401" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Case 9: _call_codex_subprocess — timeout → TransientProviderError
# ---------------------------------------------------------------------------

class TestCallCodexSubprocessTimeoutTransient:

    def test_call_codex_subprocess_timeout_transient(self, monkeypatch: pytest.MonkeyPatch):
        """Subprocess raises TimeoutExpired → TransientProviderError."""
        with patch("lib._providers.codex_auth_present", return_value=True), \
             patch("lib._providers.shutil.which", return_value="/usr/local/bin/codex"):

            with patch(
                "lib._providers.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=240.0),
            ):
                with pytest.raises(TransientProviderError) as exc_info:
                    _call_codex_subprocess(
                        model="gpt-5.5",
                        system="sys",
                        user="usr",
                        timeout_s=240.0,
                    )

        assert exc_info.value.provider == "openai"
        assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 10: _call_codex_subprocess — codex CLI missing → PermanentProviderError
# ---------------------------------------------------------------------------

class TestCallCodexSubprocessCliMissing:

    def test_call_codex_subprocess_cli_missing_permanent(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """shutil.which returns None (codex not installed) → PermanentProviderError."""
        with patch("lib._providers.codex_auth_present", return_value=True), \
             patch("lib._providers.shutil.which", return_value=None):

            with pytest.raises(PermanentProviderError) as exc_info:
                _call_codex_subprocess(
                    model="gpt-5.5",
                    system="sys",
                    user="usr",
                )

        assert exc_info.value.provider == "openai"
        msg = str(exc_info.value).lower()
        assert "install" in msg or "not installed" in msg


# ---------------------------------------------------------------------------
# Case 11: _call_openai with _use_responses_api=True routes to codex subprocess
# ---------------------------------------------------------------------------

class TestCallOpenaiWithFlagRoutesToCodex:

    def test_call_openai_with_use_responses_api_routes_to_codex(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """_call_openai with _use_responses_api=True calls _call_codex_subprocess."""
        expected_result = {"text": "advisor says yes", "tokens": {"in": 50, "out": 20}}
        captured: list[dict] = []

        def _spy_codex(**kwargs):
            captured.append(kwargs)
            return expected_result

        monkeypatch.setattr(providers_mod, "_call_codex_subprocess", _spy_codex)

        result = _call_openai(
            "gpt-5.5", "gpt-5.5",
            "sys", "usr", 256, 0.2, 30.0,
            reasoning={"effort": "xhigh"},
            text={"verbosity": "high"},
            _use_responses_api=True,
        )

        assert result == expected_result
        assert len(captured) == 1
        assert captured[0]["model"] == "gpt-5.5"
        assert captured[0]["reasoning_effort"] == "xhigh"
        assert captured[0]["verbosity"] == "high"
        assert captured[0]["system"] == "sys"
        assert captured[0]["user"] == "usr"


# ---------------------------------------------------------------------------
# Case 12: _call_openai without flag routes to Codex
# ---------------------------------------------------------------------------

class TestCallOpenaiWithoutFlagRaisesPermanent:

    def test_call_openai_without_flag_routes_to_codex(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """_call_openai without _use_responses_api still routes through Codex."""
        captured = {}

        def _fake_codex(**kwargs):
            captured.update(kwargs)
            return {"text": "ok", "tokens": {"in": 1, "out": 1}}

        monkeypatch.setattr(providers_mod, "_call_codex_subprocess", _fake_codex)
        result = _call_openai(
            "gpt-5.5-nano", "gpt-5.5",
            "sys", "usr", 256, 0.2, 30.0,
        )

        assert result["text"] == "ok"
        assert captured["model"] == "gpt-5.5"

    def test_call_openai_without_flag_never_reaches_client(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """_call_openai without flag must not call _get_openai_client at all."""
        get_client_called = []
        monkeypatch.setattr(
            providers_mod, "_get_openai_client",
            lambda: get_client_called.append(1) or (_ for _ in ()).throw(AssertionError("should not be called")),
        )

        monkeypatch.setattr(
            providers_mod,
            "_call_codex_subprocess",
            lambda **kwargs: {"text": "ok", "tokens": {"in": 1, "out": 1}},
        )
        _call_openai("gpt-5.5-nano", "gpt-5.5", "sys", "usr", 256, 0.2, 30.0)

        assert len(get_client_called) == 0
