"""Harness levels: which governed skills a project carries (ADR-0003).

A **harness level** is a named subset of the live catalog — ``minimal`` or the
built-in ``full``. A project selects one in ``harness.toml`` at its root; the
skills outside the selection stay in ``.github/skills*/`` as optional add-ons,
not linked into any native view and not listed in any adapter, until the
project names them in ``include``.

The word is *level*, not *profile*, on purpose: ``SkillMeta.profile`` already
means a per-skill grouping label (``core``, ``python-ml``, ``frontend``...). A
level is a project-wide selection across those labels.

Ownership: the level definitions (``.github/harness-levels.toml``) are
governance and travel with template syncs; ``harness.toml`` belongs to the
project and no sync ever writes it. No ``harness.toml`` means ``full`` — every
repository that predates levels keeps byte-identical output.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ml_python_base.skills_sync.errors import SkillsSyncError

if TYPE_CHECKING:
    from ml_python_base.skills_sync.models import Skill

LEVELS_FILE = Path(".github/harness-levels.toml")
SELECTION_FILE = Path("harness.toml")
FULL = "full"


class LevelError(SkillsSyncError):
    """A level definition or a project's selection is invalid."""


@dataclass(frozen=True)
class Level:
    name: str
    description: str
    # None only for the built-in ``full``: every live skill.
    skills: frozenset[str] | None


@dataclass(frozen=True)
class Selection:
    level: str = FULL
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    # Where the selection came from; empty when there is no harness.toml.
    source: str = ""

    @property
    def is_default(self) -> bool:
        return not self.source


def load_levels(root: Path) -> dict[str, Level]:
    """Every level a project can select, ``full`` first.

    A level may ``extends`` another; cycles, an unknown parent, declaring
    ``full`` or extending it are refused.
    """
    levels: dict[str, Level] = {FULL: Level(FULL, "Every live governed skill.", None)}
    path = root / LEVELS_FILE
    if not path.is_file():
        return levels
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8")).get("level", {})
    except tomllib.TOMLDecodeError as exc:
        raise LevelError(f"Invalid TOML in {LEVELS_FILE}: {exc}") from exc
    if FULL in raw:
        raise LevelError(f"'{FULL}' is built in; do not declare it in {LEVELS_FILE}.")

    def resolve(name: str, trail: tuple[str, ...]) -> frozenset[str]:
        if name in trail:
            raise LevelError(f"Level cycle: {' -> '.join((*trail, name))}")
        if name == FULL:
            raise LevelError(f"Level '{trail[-1]}' cannot extend '{FULL}'.")
        if name not in raw:
            raise LevelError(f"Level '{trail[-1]}' extends unknown level '{name}'.")
        body = raw[name]
        own = frozenset(str(s) for s in body.get("skills", []))
        parent = body.get("extends")
        return own | resolve(str(parent), (*trail, name)) if parent else own

    for name, body in raw.items():
        levels[name] = Level(
            name=name,
            description=str(body.get("description", "")),
            skills=resolve(name, ()),
        )
    return levels


def load_selection(root: Path) -> Selection:
    """The project's selection from ``harness.toml``; ``full`` when absent."""
    path = root / SELECTION_FILE
    if not path.is_file():
        return Selection()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8")).get("skills", {})
    except tomllib.TOMLDecodeError as exc:
        raise LevelError(f"Invalid TOML in {SELECTION_FILE}: {exc}") from exc
    return Selection(
        level=str(raw.get("level", FULL)),
        include=tuple(str(s) for s in raw.get("include", [])),
        exclude=tuple(str(s) for s in raw.get("exclude", [])),
        source=str(SELECTION_FILE),
    )


def carried_names(
    skills: list[Skill], levels: dict[str, Level], selection: Selection
) -> set[str]:
    """Names of the live skills the selection carries; raises on unknown names."""
    live = {skill.name for skill in skills if not skill.meta.is_legacy}
    if selection.level not in levels:
        raise LevelError(
            f"{selection.source or SELECTION_FILE}: unknown level "
            f"'{selection.level}'. Defined: {', '.join(sorted(levels))}."
        )
    level = levels[selection.level]
    named = set(level.skills or ()) | set(selection.include) | set(selection.exclude)
    unknown = sorted(named - live)
    if unknown:
        raise LevelError(
            f"Not a live skill: {', '.join(unknown)} "
            f"(level '{selection.level}' or {SELECTION_FILE} include/exclude)."
        )
    wanted = live if level.skills is None else set(level.skills)
    return (wanted | set(selection.include)) - set(selection.exclude)


def apply_selection(root: Path, skills: list[Skill]) -> list[Skill]:
    """``skills`` filtered to the project's selection, order preserved.

    Legacy skills pass through untouched: they are never projected anyway, and
    the adapters still need them to map an old name to its replacement.
    """
    selection = load_selection(root)
    if selection.is_default:
        return list(skills)
    carried = carried_names(skills, load_levels(root), selection)
    return [s for s in skills if s.meta.is_legacy or s.name in carried]


def write_selection(root: Path, level: str) -> Path:
    """Write a fresh ``harness.toml`` selecting ``level`` (bootstrap / CLI)."""
    path = root / SELECTION_FILE
    path.write_text(
        "# Which governed skills this project carries (ADR-0003).\n"
        "# Levels are defined in .github/harness-levels.toml. Skills outside the\n"
        "# selection stay in .github/skills*/ as optional add-ons: not linked into\n"
        "# native views and not listed in adapters. Edit, then `make sync-skills`.\n"
        "[skills]\n"
        f'level = "{level}"\n'
        "include = []   # optional skills to switch on\n"
        "exclude = []   # level skills to switch off\n",
        encoding="utf-8",
    )
    return path
