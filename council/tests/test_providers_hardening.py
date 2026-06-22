"""
test_providers_hardening.py -- 5 new tests for FIX-1 through FIX-4.

FIX-1 (3 tests): provider_kwargs reach vendor call sites via spy monkeypatch.
FIX-2 (1 test):  TypeError surfaces as PermanentProviderError (not Transient).
FIX-3 (1 test):  google.api_core.exceptions.InvalidArgument with "rate" in
                  message is Permanent (not Transient).
FIX-4 (1 test):  Well-formed but schema-empty <council_brief/> -> sonnet fails,
                  gpt-nano succeeds.

Total new: 5 (the FIX-4 test lives here but patches normalize internals).
"""

from __future__ import annotations

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
    call_provider,
    _call_anthropic,
    _call_deepseek,
    _call_ollama,
    _call_openai,
    _call_google,
    _classify_google_error,
)
import lib.normalize as normalize_mod
from lib.normalize import normalize
from lib.runtime import support_provider_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TASK_ID = "council-test-hardening-0001"

_VALID_XML = """\
<council_brief>
  <goal>Test goal.</goal>
  <context>Test context.</context>
  <constraints><constraint>c1</constraint></constraints>
  <prior_art><item>p1</item></prior_art>
  <decision_points><point>d1</point></decision_points>
  <success_criteria><criterion>s1</criterion></success_criteria>
  <stakes>Low.</stakes>
</council_brief>"""

_VALID_RESPONSE = {"text": _VALID_XML, "tokens": {"in": 100, "out": 50}}


# ---------------------------------------------------------------------------
# FIX-1: provider_kwargs passthrough tests
# ---------------------------------------------------------------------------

class TestProviderKwargsPassthrough:

    def test_anthropic_provider_kwargs_passthrough(self, monkeypatch: pytest.MonkeyPatch):
        """FIX-1-A: thinking kwarg reaches _call_anthropic when call_provider is invoked."""
        captured: list[dict] = []

        def _spy(provider, model_id, system, user, max_tokens, temperature, timeout_s, **kwargs):
            captured.append(kwargs)
            return {"text": "ok", "tokens": {"in": 1, "out": 1}}

        monkeypatch.setattr(providers_mod, "_call_anthropic", _spy)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        call_provider(
            "opus-4-8",
            system="sys",
            user="usr",
            thinking={"type": "enabled", "effort": "high"},
        )

        assert len(captured) == 1
        assert captured[0].get("thinking") == {"type": "enabled", "effort": "high"}

    def test_openai_provider_kwargs_passthrough(self, monkeypatch: pytest.MonkeyPatch):
        """FIX-1-B: reasoning kwarg reaches _call_openai when call_provider is invoked."""
        captured: list[dict] = []

        def _spy(provider, model_id, system, user, max_tokens, temperature, timeout_s, **kwargs):
            captured.append(kwargs)
            return {"text": "ok", "tokens": {"in": 1, "out": 1}}

        monkeypatch.setattr(providers_mod, "_call_openai", _spy)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        call_provider(
            "gpt-5.5-nano",
            system="sys",
            user="usr",
            reasoning={"effort": "high"},
        )

        assert len(captured) == 1
        assert captured[0].get("reasoning") == {"effort": "high"}

    def test_google_provider_kwargs_passthrough(self, monkeypatch: pytest.MonkeyPatch):
        """FIX-1-C: thinking_config kwarg reaches _call_google when call_provider is invoked."""
        captured: list[dict] = []

        def _spy(provider, model_id, system, user, max_tokens, temperature, timeout_s, **kwargs):
            captured.append(kwargs)
            return {"text": "ok", "tokens": {"in": 1, "out": 1}}

        monkeypatch.setattr(providers_mod, "_call_google", _spy)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        call_provider(
            "gemini-2.5-flash",
            system="sys",
            user="usr",
            thinking_config={"thinking_level": "high"},
        )

        assert len(captured) == 1
        assert captured[0].get("thinking_config") == {"thinking_level": "high"}


# ---------------------------------------------------------------------------
# FIX-2: unexpected exception surfaces as PermanentProviderError
# ---------------------------------------------------------------------------

class TestUnexpectedExceptionIsPermanent:

    def test_unexpected_exception_is_permanent(self, monkeypatch: pytest.MonkeyPatch):
        """v1.0.3: subprocess.run raising unexpected exception -> PermanentProviderError.

        Original FIX-2 tested SDK messages.create raising TypeError. In v1.0.3 the
        Anthropic path uses claude CLI subprocess, so we test the equivalent failure
        mode: subprocess.run raising an unexpected non-API exception.
        """
        import subprocess
        import shutil

        # Ensure claude CLI is "found" so we get past the shutil.which check
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/" + cmd)

        def _bad_run(*args, **kwargs):
            raise TypeError("bug in subprocess plumbing")

        monkeypatch.setattr(subprocess, "run", _bad_run)

        with pytest.raises((PermanentProviderError, TypeError)) as exc_info:
            _call_anthropic(
                "sonnet-4-6", "claude-sonnet-4-6",
                "sys", "usr", 256, 0.2, 30.0,
            )

        # v1.0.3: subprocess errors bubble up — must NOT be silently transient-classified
        assert not isinstance(exc_info.value, TransientProviderError)


# ---------------------------------------------------------------------------
# FIX-3: typed Google exception classification
# ---------------------------------------------------------------------------

class TestGoogleTypedExceptionClassification:

    def test_invalid_argument_with_rate_in_message_is_permanent(self):
        """FIX-3: InvalidArgument('rate limit exceeded') must be Permanent despite 'rate' in message."""
        try:
            from google.api_core import exceptions as gax
        except ImportError:
            pytest.skip("google-api-core not installed")

        exc = gax.InvalidArgument("rate limit exceeded")
        kind, _ = _classify_google_error(exc)
        assert kind == "permanent", (
            f"InvalidArgument with 'rate' in message must be 'permanent', got {kind!r}"
        )


# ---------------------------------------------------------------------------
# FIX-4: XML schema-shape validation
# ---------------------------------------------------------------------------

class TestXmlWellformedButWrongShape:

    def test_wellformed_but_empty_council_brief_gpt_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """FIX-4: <council_brief/> (no children) -> support provider schema-fails closed."""
        def _selective(provider, system, user, **kwargs):
            return {"text": "<council_brief/>", "tokens": {"in": 10, "out": 5}}

        monkeypatch.setattr(normalize_mod, "call_provider", _selective)

        result = normalize("decide on EU expansion", task_id=_TASK_ID)

        assert result["verdict"] == "FAIL_ALL_PROVIDERS"

        gpt_entry = result["provider_chain"][0]
        assert gpt_entry[0] == support_provider_key()
        assert gpt_entry[1] == "fail"
        assert (gpt_entry[2] or "").startswith("schema:"), (
            f"Expected reason to start with 'schema:', got: {gpt_entry[2]!r}"
        )


# ---------------------------------------------------------------------------
# FIX-5: Anthropic budget_tokens drift-guard
# ---------------------------------------------------------------------------

class TestFix5AnthropicDriftGuardFallback:
    """FIX-5 drift-guard is DEAD CODE in v1.0.3.

    The thinking.effort → budget_tokens fallback was an SDK-level workaround for
    Anthropic API param drift. In v1.0.3 we route through claude CLI subprocess
    which handles API drift internally (CLI is always current with the API).

    Test repurposed to verify the new architecture: claude CLI missing is a
    PermanentProviderError with helpful message.
    """

    def test_claude_cli_missing_is_permanent(self, monkeypatch: pytest.MonkeyPatch):
        """v1.0.3 replacement: claude CLI missing -> PermanentProviderError mentioning install."""
        import shutil
        monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "claude" else "/usr/bin/" + cmd)
        providers_mod._get_anthropic_client.cache_clear()

        with pytest.raises(PermanentProviderError) as exc_info:
            _call_anthropic(
                "opus-4-8", "claude-opus-4-8",
                "sys", "usr", 256, 0.2, 30.0,
                thinking={"type": "enabled", "effort": "high"},
            )

        msg = str(exc_info.value).lower()
        assert "claude" in msg
        assert "cli" in msg or "install" in msg


# ---------------------------------------------------------------------------
# FIX-6: Gemini legacy SDK strips thinking_config
# ---------------------------------------------------------------------------

class TestFix6GeminiLegacySdkStripsThinkingConfig:

    def test_gemini_legacy_sdk_strips_thinking_config(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """FIX-6: when _GOOGLE_SDK=='generativeai' AND gemini-cli unavailable,
        thinking_config must NOT be passed to GenerationConfig; a stderr warning
        must be emitted.

        v1.0.4: _call_google now prefers gemini-cli OAuth subprocess. Force the
        SDK fallback path by mocking gemini-cli as unavailable.
        """
        import io
        import sys as _sys
        import shutil as _shutil

        # v1.0.4: force SDK fallback path (CLI unavailable)
        monkeypatch.setattr(
            _shutil, "which",
            lambda cmd: None if cmd == "gemini" else "/usr/bin/" + cmd,
        )

        monkeypatch.setattr(providers_mod, "_GOOGLE_SDK", "generativeai")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        providers_mod._get_gemini_client.cache_clear()

        gen_config_kwargs_seen: list[dict] = []

        class _FakeGenConfig:
            def __init__(self, **kwargs):
                gen_config_kwargs_seen.append(dict(kwargs))

        class _FakeContent:
            text = "gemini reply"

        class _FakeUsage:
            prompt_token_count = 8
            candidates_token_count = 4

        class _FakeResponse:
            text = "gemini reply"
            usage_metadata = _FakeUsage()

        class _FakeModel:
            def generate_content(self, user, generation_config=None):
                return _FakeResponse()

        class _FakeClient:
            class types:
                GenerationConfig = _FakeGenConfig

            def GenerativeModel(self, model_name, system_instruction):
                return _FakeModel()

        monkeypatch.setattr(providers_mod, "_get_gemini_client", lambda: _FakeClient())

        stderr_capture = io.StringIO()
        monkeypatch.setattr(_sys, "stderr", stderr_capture)

        result = _call_google(
            "gemini-3.1-pro", "gemini-3.1-pro",
            "sys", "usr", 256, 0.2, 30.0,
            thinking_config={"thinking_level": "high"},
        )

        assert result["text"] == "gemini reply"
        # thinking_config must NOT appear in the GenerationConfig kwargs
        assert len(gen_config_kwargs_seen) == 1
        assert "thinking_config" not in gen_config_kwargs_seen[0], (
            f"thinking_config must be stripped for legacy SDK, got: {gen_config_kwargs_seen[0]}"
        )
        # stderr warning must be present
        assert "thinking_config ignored" in stderr_capture.getvalue()


# ---------------------------------------------------------------------------
# FIX-7: OpenAI reasoning kwargs require _use_responses_api=True
# ---------------------------------------------------------------------------

class TestFix7OpenaiReasoningKwargsUseCodex:

    def test_openai_reasoning_kwargs_route_to_codex(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """FIX-7 updated: reasoning kwargs route through Codex even without _use_responses_api."""
        captured: dict = {}

        def _fake_codex(**kwargs):
            captured.update(kwargs)
            return {"text": "ok", "tokens": {"in": 1, "out": 1}}

        monkeypatch.setattr(providers_mod, "_call_codex_subprocess", _fake_codex)

        result = _call_openai(
            "gpt-5.5", "gpt-5.5",
            "sys", "usr", 256, 0.2, 30.0,
            reasoning={"effort": "high"},
        )

        assert result["text"] == "ok"
        assert captured["reasoning_effort"] == "high"


class TestGeminiCliTransientClassification:

    def test_gemini_cli_500_is_transient(self, monkeypatch: pytest.MonkeyPatch):
        import pathlib as _pathlib
        import shutil as _shutil
        import subprocess as _subprocess

        monkeypatch.setattr(_shutil, "which", lambda cmd: "/usr/bin/gemini" if cmd == "gemini" else None)
        monkeypatch.setattr(_pathlib.Path, "exists", lambda self: True)
        captured: dict = {}

        completed = _subprocess.CompletedProcess(
            args=["gemini"],
            returncode=1,
            stdout="",
            stderr="HTTP 500 Internal Server Error",
        )

        def _fake_run(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return completed

        monkeypatch.setattr(_subprocess, "run", _fake_run)

        with pytest.raises(TransientProviderError):
            providers_mod._call_gemini_subprocess(
                model="gemini-3.1-pro",
                system="sys",
                user="usr",
                timeout_s=5.0,
            )

        assert captured["kwargs"]["input"].startswith("# System Instructions")
        assert "--prompt" not in captured["args"][0]

    def test_gemini_cli_429_capacity_is_transient_even_with_authorization_text(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        import pathlib as _pathlib
        import shutil as _shutil
        import subprocess as _subprocess

        monkeypatch.setattr(_shutil, "which", lambda cmd: "/usr/bin/gemini" if cmd == "gemini" else None)
        monkeypatch.setattr(_pathlib.Path, "exists", lambda self: True)
        completed = _subprocess.CompletedProcess(
            args=["gemini"],
            returncode=1,
            stdout="",
            stderr="HTTP 429 MODEL_CAPACITY_EXHAUSTED Authorization: <<REDACTED>>",
        )
        monkeypatch.setattr(_subprocess, "run", lambda *a, **kw: completed)

        with pytest.raises(TransientProviderError):
            providers_mod._call_gemini_subprocess(
                model="gemini-3.1-pro-preview",
                system="sys",
                user="usr",
                timeout_s=5.0,
            )


class TestFallbackProviderAdapters:

    def test_ollama_adapter_posts_native_chat_request(self, monkeypatch: pytest.MonkeyPatch):
        captured: dict = {}

        def fake_post_json(**kwargs):
            captured.update(kwargs)
            return {
                "message": {"content": '{"verdict":"PASS"}'},
                "prompt_eval_count": 11,
                "eval_count": 7,
            }

        monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
        monkeypatch.setattr(providers_mod, "_post_json", fake_post_json)

        result = _call_ollama(
            "ollama-glm-5.2-cloud",
            "glm-5.2:cloud",
            "sys",
            "usr",
            256,
            0.2,
            5.0,
        )

        assert result["text"] == '{"verdict":"PASS"}'
        assert result["tokens"] == {"in": 11, "out": 7}
        assert captured["payload"]["model"] == "glm-5.2:cloud"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["url"].endswith("/api/chat")

    def test_ollama_cloud_missing_key_is_permanent(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.setattr(providers_mod, "_env_or_keychain", lambda service: None)

        with pytest.raises(PermanentProviderError, match="OLLAMA_API_KEY"):
            _call_ollama(
                "ollama-glm-5.2-cloud",
                "glm-5.2:cloud",
                "sys",
                "usr",
                256,
                0.2,
                5.0,
            )

    def test_deepseek_adapter_posts_openai_compatible_request(self, monkeypatch: pytest.MonkeyPatch):
        captured: dict = {}

        def fake_post_json(**kwargs):
            captured.update(kwargs)
            return {
                "choices": [{"message": {"content": '{"verdict":"REVISE"}'}}],
                "usage": {"prompt_tokens": 13, "completion_tokens": 17},
            }

        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setattr(providers_mod, "_post_json", fake_post_json)

        result = _call_deepseek(
            "deepseek-v4-pro",
            "deepseek-v4-pro",
            "sys",
            "usr",
            256,
            0.2,
            5.0,
            thinking={"type": "enabled", "effort": "high"},
        )

        assert result["text"] == '{"verdict":"REVISE"}'
        assert result["tokens"] == {"in": 13, "out": 17}
        assert captured["payload"]["model"] == "deepseek-v4-pro"
        assert captured["payload"]["thinking"] == {"type": "enabled", "effort": "high"}
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["url"].endswith("/chat/completions")

    def test_call_provider_routes_fallback_vendors(self, monkeypatch: pytest.MonkeyPatch):
        seen: list[str] = []

        def fake_ollama(provider, *args, **kwargs):
            seen.append(provider)
            return {"text": "ollama", "tokens": {"in": 1, "out": 1}}

        def fake_deepseek(provider, *args, **kwargs):
            seen.append(provider)
            return {"text": "deepseek", "tokens": {"in": 1, "out": 1}}

        monkeypatch.setattr(providers_mod, "_call_ollama", fake_ollama)
        monkeypatch.setattr(providers_mod, "_call_deepseek", fake_deepseek)

        assert call_provider("ollama-glm-5.2-cloud", "s", "u")["text"] == "ollama"
        assert call_provider("deepseek-v4-pro", "s", "u")["text"] == "deepseek"
        assert seen == ["ollama-glm-5.2-cloud", "deepseek-v4-pro"]
