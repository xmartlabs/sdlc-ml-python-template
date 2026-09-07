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

## The docs-coverage gate only counts `docs/` — 2026-09-07

`make check-docs-coverage` fails any diff that touches `src/` or `tests/` without a
changed file under `docs/`. Updating `.github/skills/README.md` or `CONTRIBUTING.md`
does not satisfy it, even when those are the natural home for the prose.

**Why it matters:** `make check` passes and `make ci` still fails, so the gate is
easy to hit at the very end of a change that looked finished.
**How to apply:** When an engine change lands in `src/`, write the reference prose in
the matching `docs/` page (for the skills engine, `docs/skills-management.md`) and
let `.github/` docs point at it.
