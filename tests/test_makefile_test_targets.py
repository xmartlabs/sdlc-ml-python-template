"""The Makefile test targets run pytest only and fail when pytest fails.

`make test` used to run `make format` and `make fix` first (mutating the tree)
and ended with `|| echo`, so a failing suite exited 0. These tests run the real
targets against a stub virtualenv: its `pytest` exits with a chosen code, and
its `pytest`, `ruff` and `nbstripout` record every call. The stub keeps the
check fast and hermetic, and stops `make test` from recursively running this
same suite.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed"),
    # The targets bootstrap `.venv` with `make install` when it is missing; a
    # test must never trigger that.
    pytest.mark.skipif(
        not (REPO_ROOT / ".venv").is_dir(), reason="no .venv in the repository"
    ),
]

# Variables an outer `make` exports to its recipes; drop them so the nested
# `make` behaves the same under `make check` as under a bare `pytest`.
_MAKE_ENV = {"MAKEFLAGS", "MFLAGS", "MAKELEVEL"}


def _stub_venv(root: Path, *, pytest_exit: int) -> tuple[Path, Path]:
    """A fake virtualenv whose `activate` puts stub tools first on PATH."""
    bin_dir = root / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    log = root / "calls.log"
    (bin_dir / "activate").write_text(f'export PATH="{bin_dir}:$PATH"\n')
    stubs = {
        "pytest": f"exit {pytest_exit}",
        "ruff": "exit 0",
        "nbstripout": "exit 0",
    }
    for name, tail in stubs.items():
        stub = bin_dir / name
        stub.write_text(
            f"#!/bin/sh\nprintf '%s' '{name}' >> '{log}'\n"
            f"printf ' [%s]' \"$@\" >> '{log}'\necho >> '{log}'\n{tail}\n"
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return root / "venv", log


def _make(target: str, venv: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in _MAKE_ENV}
    return subprocess.run(
        ["make", "--no-print-directory", target, f"VENV_DIR={venv}"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _calls(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


@pytest.mark.parametrize("target", ["test", "test-unit", "test-integration"])
def test_a_failing_suite_fails_the_target(tmp_path: Path, target: str) -> None:
    venv, log = _stub_venv(tmp_path, pytest_exit=1)

    result = _make(target, venv)

    assert result.returncode != 0, result.stdout + result.stderr
    assert any(call.startswith("pytest ") for call in _calls(log))


@pytest.mark.parametrize("target", ["test", "test-unit", "test-integration"])
def test_a_green_suite_passes_the_target(tmp_path: Path, target: str) -> None:
    venv, _log = _stub_venv(tmp_path, pytest_exit=0)

    result = _make(target, venv)

    assert result.returncode == 0, result.stdout + result.stderr


def test_make_test_runs_only_pytest(tmp_path: Path) -> None:
    # No `make format` / `make fix`: running the tests never mutates the tree.
    venv, log = _stub_venv(tmp_path, pytest_exit=0)

    _make("test", venv)

    calls = _calls(log)
    assert len(calls) == 1, calls
    assert calls[0].startswith("pytest [tests/] [--cov=src]"), calls


@pytest.mark.parametrize(
    ("target", "selection"),
    [
        ("test-unit", "[-m] [not integration]"),
        ("test-integration", "[-m] [integration]"),
    ],
)
def test_split_targets_select_by_the_integration_marker(
    tmp_path: Path, target: str, selection: str
) -> None:
    venv, log = _stub_venv(tmp_path, pytest_exit=0)

    _make(target, venv)

    (call,) = _calls(log)
    assert selection in call, call
