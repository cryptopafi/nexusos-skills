"""
test_scaffold.py -- Smoke tests for the advisor-council skill scaffold.

10 test cases covering args parsing, VK emission, and workspace creation.
Uses tmp_path and monkeypatch.setenv(HOME=...) to avoid touching real ~/.nexus/.
"""

import importlib
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup: allow importing from lib/ without installing the package.
# ---------------------------------------------------------------------------

_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from lib import args as args_mod
from lib import vk as vk_mod
from lib import workspace as ws_mod


# ---------------------------------------------------------------------------
# Helper: reload workspace module so _council_base() re-reads HOME.
# ---------------------------------------------------------------------------

def _reload_ws(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> object:
    """Patch HOME to tmp_path, reload workspace so Path.home() picks it up."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Force Path.home() cache to refresh by reloading module.
    import importlib
    import lib.workspace as ws
    importlib.reload(ws)
    return ws


# ===========================================================================
# args.py tests
# ===========================================================================

class TestParseArgs:

    def test_defaults(self):
        """Case 1: minimal invocation returns expected defaults."""
        result = args_mod.parse_args(["target.md"])
        assert result["target"] == "target.md"
        assert result["depth"] == "standard"
        assert result["no_debate"] is False
        assert result["force"] is False
        assert result["min_quorum"] == 3
        assert result["keep_chains"] is False
        assert result["force_test"] is False

    def test_depth_deep_and_no_debate(self):
        """Case 2: --depth deep and --no-debate flag."""
        result = args_mod.parse_args(["target.md", "--depth", "deep", "--no-debate"])
        assert result["depth"] == "deep"
        assert result["no_debate"] is True

    def test_equals_syntax(self):
        """Case 3: equals-syntax for --depth= and --min-quorum=."""
        result = args_mod.parse_args(["target.md", "--depth=quick", "--min-quorum=2"])
        assert result["depth"] == "quick"
        assert result["min_quorum"] == 2

    def test_unknown_flag_raises(self):
        """Case 4: unknown flag raises ValueError mentioning the bad flag."""
        with pytest.raises(ValueError) as exc_info:
            args_mod.parse_args(["--bad-flag"])
        # argparse error message will be captured in the ValueError
        assert "bad-flag" in str(exc_info.value) or "Argument parse error" in str(exc_info.value)

    def test_missing_target_raises(self):
        """Case 5: no target raises ValueError about target being required."""
        with pytest.raises(ValueError) as exc_info:
            args_mod.parse_args([])
        assert "target" in str(exc_info.value).lower()


# ===========================================================================
# vk.py tests
# ===========================================================================

_VK_PATTERN = re.compile(
    r"^VK:STEP=triage STATE=entered TS=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z "
    r"TASK=council-\d{8}-\d{4}-[a-z0-9]{4}$"
)

class TestVkEmit:

    def test_basic_emit_matches_regex(self, capsys: pytest.CaptureFixture):
        """Case 6: basic emit matches canonical VK format regex."""
        vk_mod.emit("triage", "entered", "council-20260519-1453-a7b2")
        captured = capsys.readouterr()
        line = captured.out.strip()
        assert _VK_PATTERN.match(line), f"VK line did not match pattern: {line!r}"

    def test_extra_kwargs_appended(self, capsys: pytest.CaptureFixture):
        """Case 7: extra kwargs appear as key=value at end of line."""
        vk_mod.emit("triage", "completed", "council-20260519-1453-a7b2", score=72)
        captured = capsys.readouterr()
        line = captured.out.strip()
        assert "score=72" in line

    def test_invalid_state_raises(self):
        """Case 8: invalid state raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            vk_mod.emit("triage", "bogus", "council-20260519-1453-a7b2")
        assert "bogus" in str(exc_info.value) or "state" in str(exc_info.value).lower()


# ===========================================================================
# workspace.py tests
# ===========================================================================

class TestWorkspace:

    def test_create_makes_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Case 9a: create() produces directory; second call with same id raises FileExistsError."""
        ws = _reload_ws(monkeypatch, tmp_path)

        task_id = "council-test-001"
        result = ws.create(task_id)

        assert result.exists()
        assert result.is_dir()

        # Second call must raise FileExistsError
        with pytest.raises(FileExistsError):
            ws.create(task_id)

    def test_generate_task_id_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Case 10: generate_task_id returns string matching expected pattern."""
        ws = _reload_ws(monkeypatch, tmp_path)
        task_id = ws.generate_task_id()
        pattern = re.compile(r"^council-\d{8}-\d{4}-[a-z0-9]{4}$")
        assert pattern.match(task_id), f"task_id did not match pattern: {task_id!r}"

    def test_create_retry_on_collision(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Case 11: create(task_id=None) retries on collision and succeeds with 'b' suffix."""
        ws = _reload_ws(monkeypatch, tmp_path)

        # Pre-create the "a" directory to force a collision on first two attempts.
        base = tmp_path / ".nexus" / "workspace" / "council"
        base.mkdir(parents=True, exist_ok=True)
        (base / "a").mkdir()

        ids = iter(["a", "a", "b"])
        monkeypatch.setattr(ws, "generate_task_id", lambda: next(ids))

        result = ws.create(task_id=None)
        assert result.name == "b"
        assert result.exists()

    def test_council_workspace_dir_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Case 11b: COUNCIL_WORKSPACE_DIR controls workspace placement."""
        ws = _reload_ws(monkeypatch, tmp_path)
        custom_base = tmp_path / "custom-council-workspaces"
        monkeypatch.setenv("COUNCIL_WORKSPACE_DIR", str(custom_base))

        result = ws.create("council-env-override")

        assert result == custom_base / "council-env-override"
        assert result.exists()


# ===========================================================================
# Additional vk.py tests
# ===========================================================================

class TestVkEmitExtra:

    def test_invalid_step_raises(self):
        """Case 12: invalid step raises ValueError mentioning the bad step name."""
        with pytest.raises(ValueError) as exc_info:
            vk_mod.emit("bogus_step", "entered", "council-20260519-1453-a7b2")
        assert "bogus_step" in str(exc_info.value)

    def test_vk_kwarg_space_rejected(self):
        """Case 13: kwarg value containing a space raises ValueError."""
        with pytest.raises(ValueError):
            vk_mod.emit("triage", "entered", "council-20260519-1453-a7b2", note="hello world")


# ===========================================================================
# Additional args.py tests
# ===========================================================================

class TestParseArgsExtra:

    def test_force_test_flag_true(self):
        """Case 14: --force-test flag sets force_test=True in returned dict."""
        result = args_mod.parse_args(["target.md", "--force-test"])
        assert result["force_test"] is True
