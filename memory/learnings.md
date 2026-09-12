# Learnings

> Non-obvious facts discovered while working: gotchas, why-it-is-this-way, dead ends
> to avoid. Append new entries at the top. One fact per entry.
>
> Record a fact here the moment you learn something that would have saved you time.
> Skip anything already obvious from the code, the docs, or commit messages. Delete
> entries that turn out to be wrong rather than leaving them to mislead. See
> `memory/README.md` for the entry format and `/retro` to capture them at the end of
> a unit of work.

<!--
Template for a new entry — newest first, directly below this comment.

## <short title> — <YYYY-MM-DD>

<one or two sentences of fact>

**Why it matters:** <the consequence — why the next person should care>
**How to apply:** <what to do differently next time>
-->

## A vendored engine needs its extension points upstream, or it cannot be upgraded — 2026-09-12

Adopting catalog v3 in the harness lab failed 12 of its tests on the first pass, and
none was a governance regression: the lab had extended the `skills_sync` engine it
vendors with four things the template did not have — `link_tool(..., strategy=)`,
`linker.add_skills()`, `render_tool(..., template_root=)` and `cli.check_drift()`.
All four exist for the same shape (projecting a governed harness into a *foreign*
root, i.e. a cloned target repository), and without them a platform upgrade could
only be done by forking the engine — which silently loses the catalog rules (legacy
filtering, overlays) on the next change.

Upstreaming the four turned that platform upgrade from an unmergeable 3-way patch
into a plain directory copy plus the lab's own `projection.py`, and its suite went
from 255 passed / 12 failed to **1917 passed / 0 failed**.

**Why it matters:** a downstream that had to fork to extend will drift, and the drift
surfaces as "your release broke our tests" long after the release. The migration
contract is only real if the extension points a real consumer needs are part of the
published surface.
**How to apply:** when a downstream's tests break on a platform upgrade, classify each
failure before fixing anything — *intentional breaking change*, *API that should be
backward compatible* (fix upstream), *downstream extension that must migrate*, or
*real regression*. Only the first and third belong in the downstream's patch. Also: a
foreign-root projection means `Path.relative_to(root)` can raise —
`overlay._source_label` falls back to the governed path rather than leaking an
absolute one.

## Skills catalog v3: metadata rides the frontmatter, policy rides the projection — 2026-09-12

Reorganising the 27-skill flat catalog into entrypoints / primitives / optional /
hidden / legacy surfaced three constraints that shape any future skill change:

1. **Symlink projection means one frontmatter for every tool.** `.claude/skills/x/SKILL.md`
   is the governed file itself, so a per-tool key (`disable-model-invocation`, a
   Claude-only description) cannot be added at projection time — unless the projected
   `SKILL.md` becomes a *generated* file. That is what the overlay does for vendored
   skills with a policy or a description override; the vendor source, lock hash and
   NOTICE never change. Anything that assumed "every native entry is a symlink" must
   branch on content.
2. **Adapter templates are governance, the engine is platform.** A template that
   references a new variable breaks every downstream repo that governance-syncs it
   before adopting the engine (`StrictUndefined: 'intents' is undefined`, verified
   against the lab's vendored engine). Bump `template_sync.protocol` whenever a
   template needs a new engine capability; the lab's `harness-sync-preview` then
   blocks adoption (exit 4) until the platform is upgraded.
3. **The harness lab's engine copy has diverged** (`projection.py`, `check_drift`
   export, 7 shared modules differ). A platform upgrade there is a merge of the
   template's engine *diff*, never a copy of the directory. Its ablation path
   (`scripts/bench_run.py::build_effective_skills` / `restore_full_skill_views`) must
   also pass `registry=` to `discover_skills`, or a run regenerates views without
   overlays and leaves the tree dirty.

**Why it matters:** the three are invisible until a downstream sync or a lab run
fails; each was found by exercising the lab's own code against the new tree, not by
unit tests here.
**How to apply:** new skill → frontmatter metadata + one routing scenario; vendored
skill that instructs git mutations → `[policy.git-actions].applies_to` (a test
fails otherwise); retired name → `[alias.*]` (an alias that still finds a directory
projects it as legacy with a warning); any template change that needs engine support
→ protocol bump + CHANGELOG migration note. Source: skills catalog v3 work,
`docs/skills-catalog-v3-audit.md`, ADR-0002.

## The docs-coverage gate only counts `docs/` — 2026-09-07

`make check-docs-coverage` fails any diff that touches `src/` or `tests/` without a
changed file under `docs/`. Updating `.github/skills/README.md` or `CONTRIBUTING.md`
does not satisfy it, even when those are the natural home for the prose.

**Why it matters:** `make check` passes and `make ci` still fails, so the gate is
easy to hit at the very end of a change that looked finished.
**How to apply:** When an engine change lands in `src/`, write the reference prose in
the matching `docs/` page (for the skills engine, `docs/skills-management.md`) and
let `.github/` docs point at it.
