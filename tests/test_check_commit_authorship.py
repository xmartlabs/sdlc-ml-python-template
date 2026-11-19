"""The commit-msg guard: a commit is the developer's, never an AI agent's.

The guard is a maintenance script (like scripts/harness_release.py), so it is
loaded by path rather than imported as a package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/check_commit_authorship.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_commit_authorship", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _load_script()

HUMAN = "Dana Developer <dana@example.com>"


@pytest.mark.parametrize(
    "message",
    [
        "feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n",
        "feat: x\n\nCo-authored-by: Claude Opus 5.5 <noreply@anthropic.com>\n",
        "fix: y\n\nco-authored-by: claude <claude@anthropic.com>",
        "feat: x\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n",
        "feat: x\n\nCo-authored-by: Copilot <copilot@github.com>\n",
        "feat: x\n\nCo-authored-by: someone <bot@openai.com>\n",
    ],
)
def test_ai_attribution_in_the_message_is_refused(message: str) -> None:
    assert guard.message_problems(message)


@pytest.mark.parametrize(
    "message",
    [
        "feat: add the Claude-native transport\n",
        "docs: explain how claude stream-json events are parsed\n",
        "feat: x\n\nCo-authored-by: Ana Pérez <ana@example.com>\n",
        "",
    ],
)
def test_a_human_message_that_mentions_claude_is_fine(message: str) -> None:
    # Products may be named in code and docs; only attribution of authorship
    # is refused.
    assert guard.message_problems(message) == []


@pytest.mark.parametrize(
    "ident",
    [
        "Claude <claude@anthropic.com>",
        "claude <someone@example.com>",
        "Dana <noreply@anthropic.com>",
        "Claude Code <x@y.z>",
    ],
)
def test_an_ai_identity_is_refused(ident: str) -> None:
    assert guard.identity_problems(ident, role="author")


def test_the_developers_identity_passes() -> None:
    assert guard.identity_problems(HUMAN, role="author") == []


def test_main_checks_the_message_file_and_both_identities(tmp_path, monkeypatch):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("feat: x\n")
    idents = {"GIT_AUTHOR_IDENT": HUMAN, "GIT_COMMITTER_IDENT": HUMAN}
    monkeypatch.setattr(guard, "git_ident", lambda var: idents[var])
    assert guard.main([str(message)]) == 0

    idents["GIT_COMMITTER_IDENT"] = "Claude <claude@anthropic.com>"
    assert guard.main([str(message)]) == 1


def test_main_ignores_comment_lines_git_strips(tmp_path, monkeypatch):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("feat: x\n# Co-authored-by: Claude <noreply@anthropic.com>\n")
    monkeypatch.setattr(guard, "git_ident", lambda _var: HUMAN)
    assert guard.main([str(message)]) == 0


def test_main_without_a_message_file_is_a_usage_error() -> None:
    assert guard.main([]) == 2
