"""Render the machine-managed skill region inside each tool's adapter file, and
the generated skills catalog document.

Only the text between the sentinels below is owned by the engine; the
surrounding governance prose stays hand-written. This guarantees the skill
lists across CLAUDE.md / AGENTS.md / OPENCODE.md / GEMINI.md / copilot can never
drift from the actual governed skills. The catalog document
(``[catalog].output`` in the registry) is generated whole.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ml_python_base.skills_sync.catalog import build_view
from ml_python_base.skills_sync.discovery import discover_skills
from ml_python_base.skills_sync.errors import SkillsSyncError
from ml_python_base.skills_sync.models import KIND_INTERNAL, Registry, Skill, ToolSpec

BEGIN_MARKER = "<!-- BEGIN GENERATED SKILLS (managed by skills_sync; do not edit) -->"
END_MARKER = "<!-- END GENERATED SKILLS -->"
TEMPLATES_DIR = Path("adapters/templates")
DEFAULT_TEMPLATE = "_skills_block.j2"
CATALOG_TEMPLATE = "skills_catalog.md.j2"
REFRESH_COMMAND = "make sync-skills"
# A backticked skill name inside a routing rule (`plan_and_execute_feature`).
_BACKTICKED = re.compile(r"`([A-Za-z0-9_:-]+)`")


def _environment(root: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(root / TEMPLATES_DIR)),
        # Templates render Markdown for local adapter files (no HTML/XSS surface);
        # select_autoescape leaves .j2 Markdown untouched while satisfying linters.
        autoescape=select_autoescape(default=False),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )


def carried_routing(
    registry: Registry, carried: list[Skill], catalog: list[Skill]
) -> tuple[list, list[str]]:
    """Intents and routing rules that name only skills the project carries.

    Under a harness level (ADR-0003) an adapter must never route the agent to
    a skill the project does not carry: an intent whose skill is optional here
    is dropped, and so is a rule that names any catalog skill outside
    ``carried``. A backticked word that is not a skill (a mode such as
    `execute_only`) never drops a rule. When ``carried`` is the whole catalog
    (``full``) nothing is dropped.
    """
    live = {s.name for s in carried if not s.meta.is_legacy}
    every_skill = {s.name for s in catalog}
    intents = [i for i in registry.catalog.intents if i.skill in live]
    rules = [
        rule
        for rule in registry.catalog.routing_rules
        if all(
            name in live for name in _BACKTICKED.findall(rule) if name in every_skill
        )
    ]
    return intents, rules


def _context(
    registry: Registry, skills: list[Skill], catalog: list[Skill] | None = None
) -> dict:
    """Template variables shared by the adapter block and the catalog page.

    ``catalog`` is the whole live catalog when it differs from ``skills`` (a
    project under a harness level): routing is filtered against what the
    project carries, and a rule naming any catalog skill it does not carry is
    dropped.
    """
    view = build_view(skills, registry)
    intents, rules = carried_routing(registry, skills, catalog or skills)
    if catalog is not None and len(catalog) != len(skills):
        # A legacy name mapped to a skill this project does not carry would
        # route the agent to nothing; under a level, keep only live mappings.
        live = {s.name for s in skills if not s.meta.is_legacy}
        view = replace(
            view, aliases=tuple(a for a in view.aliases if a.replacement in live)
        )
    return {
        "internal_skills": [s for s in skills if s.kind == KIND_INTERNAL],
        "external_skills": [s for s in skills if s.kind != KIND_INTERNAL],
        "view": view,
        "intents": intents,
        "policies": registry.catalog.policies,
        "routing_rules": rules,
        "small_model_note": registry.catalog.small_model_note,
        "catalog_path": registry.catalog.output,
        "governance": registry.governance,
        "refresh_command": REFRESH_COMMAND,
    }


def render_region(
    root: Path,
    registry: Registry,
    tool: ToolSpec,
    skills: list[Skill] | None = None,
    template_root: Path | None = None,
) -> str:
    """Render the managed region content (no surrounding markers).

    ``template_root`` separates *where the templates live* from *where the
    output goes*. They are the same root for an in-place sync; they differ when
    a governed harness is projected into a foreign repository, which owns
    neither ``adapters/templates`` nor ``.github/skills``.
    """
    catalog = discover_skills(template_root or root, registry=registry)
    skills = skills if skills is not None else catalog
    env = _environment(template_root or root)
    template_name = tool.adapter_template or DEFAULT_TEMPLATE
    template = env.get_template(template_name)
    context = _context(registry, skills, catalog)
    context.update({"tool": tool, "ref": tool.reference_prefix})
    return template.render(**context).strip()


def splice(existing: str, region: str) -> str:
    """Replace the content between the sentinels with ``region``."""
    if BEGIN_MARKER not in existing or END_MARKER not in existing:
        raise SkillsSyncError(
            "Adapter file is missing the generated-skills sentinels. Add:\n"
            f"  {BEGIN_MARKER}\n  {END_MARKER}\n"
            "around the skills section so the engine can manage it."
        )
    begin_at = existing.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end_at = existing.index(END_MARKER)
    return f"{existing[:begin_at]}\n{region}\n{existing[end_at:]}"


def expected_file(
    root: Path,
    registry: Registry,
    tool: ToolSpec,
    skills: list[Skill] | None = None,
) -> str | None:
    """Return what the adapter file should contain, or None if no adapter.

    ``skills`` is what the project carries (its harness level); omitted, the
    whole catalog — the behavior before levels existed.
    """
    if not tool.adapter_file:
        return None
    path = root / tool.adapter_file
    if not path.is_file():
        return None
    region = render_region(root, registry, tool, skills=skills)
    return splice(path.read_text(encoding="utf-8"), region)


def render_tool(
    root: Path,
    registry: Registry,
    tool: ToolSpec,
    skills: list[Skill] | None = None,
    template_root: Path | None = None,
) -> bool:
    """Write the managed region into the adapter file. Returns True if changed.

    ``skills`` overrides discovery for controlled experiments such as a
    per-run skill ablation. Omitting it preserves the normal authoritative
    discovery behavior. ``template_root`` is where the Jinja templates and the
    governed skills live when that is not ``root`` (a foreign projection).
    """
    if not tool.adapter_file:
        return False
    path = root / tool.adapter_file
    if not path.is_file():
        return False
    current = path.read_text(encoding="utf-8")
    updated = splice(
        current,
        render_region(root, registry, tool, skills=skills, template_root=template_root),
    )
    if updated == current:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


# --- Generated catalog document ------------------------------------------------


def render_catalog(
    root: Path,
    registry: Registry,
    skills: list[Skill] | None = None,
    carried: set[str] | None = None,
) -> str:
    """Render the human-facing catalog page from ``skills_catalog.md.j2``.

    The page always lists the whole catalog. ``carried`` (the names a project
    under a harness level carries) adds a column saying which skills are
    carried here and which are optional add-ons; None (``full``, the default)
    renders the page exactly as before levels existed.
    """
    skills = skills if skills is not None else discover_skills(root, registry=registry)
    template = _environment(root).get_template(CATALOG_TEMPLATE)
    context = _context(registry, skills)
    context["carried"] = carried
    return template.render(**context).strip() + "\n"


def catalog_path(root: Path, registry: Registry) -> Path | None:
    """Where the catalog document lives, or None when it cannot be rendered.

    None when the registry declares no ``[catalog].output`` or when the tree has
    no catalog template (a downstream repository that has not synced
    ``adapters/templates`` yet keeps working; the document simply is not
    generated there).
    """
    output = registry.catalog.output
    if not output or not (root / TEMPLATES_DIR / CATALOG_TEMPLATE).is_file():
        return None
    return root / output


def write_catalog(
    root: Path,
    registry: Registry,
    skills: list[Skill] | None = None,
    carried: set[str] | None = None,
) -> bool:
    """Write the catalog document. Returns True if it changed."""
    path = catalog_path(root, registry)
    if path is None:
        return False
    content = render_catalog(root, registry, skills, carried=carried)
    current = path.read_text(encoding="utf-8") if path.is_file() else None
    if current == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True
