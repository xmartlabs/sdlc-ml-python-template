# ADR-0003: A project carries a harness level, not the whole catalog

- **Status:** Accepted
- **Date:** 2026-11-18
- **Deciders:** template maintainers (harness engineering)
- **Related:** ADR-0002; `docs/skills-management.md`; `docs/skills-guide.md`;
  harness lab ADR-0085 (skill profiles) and ADR-0086 (pruning never trades quality)

## Context

Every project built from this template carried every live skill: 25 projected
into four native views and listed in five adapter files. Each listed skill costs
context on every agent call, whether or not it is ever opened.

A 2026-11-18 review measured what three repositories built from this template
used. It covered agent transcripts (Claude Code) and 90 days of git history:

| Skill | Sessions that invoked it |
|---|---|
| `plan_and_execute_feature` | 11 |
| `systematic_debugging` | 5 |
| `verify_changes` | 3 |
| `research_current_info` | 2 |
| `requesting-code-review`, `brainstorm_quick` | 1 or more |

16 of 25 skills were never invoked. The pieces of the harness these projects used
most were not skills at all: project memory, ADRs and project-specific invariants.

The harness lab ran ablations on the same question and reached a rule this ADR
adopts. The harness exists to add quality on top of the model. Removing all
skills cost success on real SWE-bench work (100% → 80%), and easy cases at the
ceiling showed nothing either way. So a smaller *default* is justified by usage,
but no skill is "safe to delete" without evidence, and nothing is deleted here.

## Decision

1. **Two harness levels.** `full` is built in and means every live skill, exactly
   the behavior before this ADR. `minimal` is declared in the governed file
   `.github/harness-levels.toml`. It holds `plan_and_execute_feature`,
   `systematic_debugging`, `verify_changes`, `research_current_info`,
   `requesting-code-review`, `writing-plans` and `brainstorm_quick`: the skills
   real work used, plus `writing-plans`, which the operating playbook and `/plan`
   name. The format supports `extends`, so more levels can be added later.
2. **A project selects one in `harness.toml`** at its root:
   `[skills] level / include / exclude`. No `harness.toml` means `full`, with
   byte-identical generated output. `make init` writes `minimal` by default, and
   `make init LEVEL=full` selects full. `make skill-level [SET=]` lists or
   switches the level.
3. **Filter, never delete.** `.github/skills*/` stay complete. The selection is
   applied at one seam (`cli._skills` → `levels.apply_selection`). Link, render,
   route and check therefore agree on what the project carries:
   - native views hold exactly the selection;
   - adapters list only the selection;
   - the drift check flags both extra and missing native entries.

   The generated catalog keeps listing every skill and adds a *carried* /
   *optional* column.
4. **Naming: _level_, not _profile_.** `SkillMeta.profile` already labels a
   skill's domain (`core`, `python-ml`, `frontend`…). A level is a project-wide
   selection across those labels, so it gets its own word.
5. **No dangling routing.** An adapter must never route the agent to a skill the
   project does not carry. Under a level:
   - an `[[intent]]` whose skill is not carried is not rendered;
   - a routing rule that names any non-carried catalog skill is not rendered;
   - a legacy alias whose replacement is not carried is not rendered.

   Backticked words that are not skills (`execute_only`) never drop a rule. The
   hand-written playbook and `.claude/commands/` name a full-level skill only as
   "if this project's harness level carries it".
6. **Agents keep working at any level.** A governed agent reads its bound skills
   from `.github/skills*/`, which every level keeps. A minimal project's agents
   therefore never point at nothing, and they do not pull their skills into the
   adapter listing. A test asserts every bound skill exists in the sources.
7. **Sync ownership.** `.github/harness-levels.toml` is a governance path and
   travels with template syncs. `harness.toml` belongs to the project, and no sync
   lists or writes it. The engine change is platform.

## Consequences

- With `minimal`, every adapter shrinks by about 2.4 KB (`CLAUDE.md` 11.4 KB →
  8.8 KB), and every native view drops from 25 entries to 7.
- Switching an optional skill on is one line (`include = ["…"]`) plus
  `make sync-skills`. Switching back to `full` restores today's output byte for
  byte, as a test asserts.
- **Protocol stays 2; release is minor (2.1.0).** A protocol-2 consumer that
  receives `.github/harness-levels.toml` through a governance sync, without the
  engine change, ignores it: no `harness.toml` means `full`. Nothing breaks, so
  no protocol bump.
- A routing rule that mixes a minimal skill with a full-only skill disappears
  whole under `minimal`. Splitting such rules would keep more guidance under
  `minimal`. That is a wording change for the registry, deferred until usage
  shows it matters.
- Shrinking `minimal` further, or growing it, should rest on evidence that no
  quality is lost (lab ablations) or that a skill is used. Do not shrink it on
  token cost alone.
