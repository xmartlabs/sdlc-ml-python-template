# Open Source Readiness Checklist

Use this checklist before making this repository — or any repository derived from it —
publicly available. Each item must be confirmed as clear before publishing.

## Secrets and credentials

- [x] No API keys, tokens, or passwords are committed anywhere in the repo.
- [x] `.env` is listed in `.gitignore` and not tracked.
- [x] `.env.example` contains only placeholder values (e.g., `sk-local-change-me`,
      `http://localhost:...`). Review it and confirm no real credentials are present.
- [x] No secrets appear in git history. If any were committed in the past, rotate them
      and consider using `git filter-repo` to purge the history.
      *(This repository starts from a squashed single commit; there is no prior
      history to scan.)*

## Client and company information

- [x] No client names, project names, or internal codenames appear in code, comments,
      docs, or commit messages.
- [x] No internal URLs, IP addresses, or hostnames (beyond `localhost` examples) are
      present.
- [x] No organization-specific infrastructure details (account IDs, bucket names,
      cluster names) are present.

## Sensitive rules and prompts

- [x] `.github/skills/` contains only generic, reusable skills safe for public use.
- [x] `.github/skills-external/` contains only vendored skills from public sources.
      Verify the license of each vendored skill allows redistribution.
      *(Verified 2026-08-20. Origin and licence for all 12 are declared in the
      `[external_skill]` table of `adapters/registry.toml`, emitted into
      `skills-lock.json`, and attributed in `NOTICE`. `make check` fails if any
      vendored skill has an UNKNOWN origin.)*
- [x] No commercially sensitive prompts, instructions, or business logic appear in
      governance files or adapter files.

## Workflows

- [x] `.github/workflows/` contains no jobs that push to internal registries, deploy to
      private infrastructure, or use organization-specific secrets.
      *(Both workflows are read-only and declare `permissions: contents: read`.)*
- [x] No GitHub Pages or publication workflows are present (this template explicitly
      excludes them).
- [x] CI workflows reference only public actions and public Docker images, or images
      that will remain accessible after the repo goes public.

## Generated and vendored content

- [x] `skills-lock.json` contains only public skill references (no private registry
      URLs), each carrying an `upstream` and a `license` field.
- [x] `uv.lock` pins only packages from public indexes.
- [x] No generated files contain embedded secrets or internal paths.

## Documentation

- [x] `README.md` is accurate and self-contained for a public audience.
- [x] `docs/` contains no internal design docs, meeting notes, or client-specific
      architecture diagrams.
- [x] `memory/` files (`context.md`, `learnings.md`, `patterns.md`) have been reviewed
      and contain no sensitive project context. Consider clearing or sanitizing them
      before publishing. *(Reset 2026-08-20. `learnings.md` is an empty template;
      `context.md` was already a placeholder; `patterns.md` documents this template's
      own conventions and carries no project or personal content.)*

## License

- [x] A `LICENSE` file is present at the repo root.
- [x] The chosen license is compatible with all vendored skills and dependencies.
      *(Apache-2.0 outbound. Inbound: MIT and Public Domain only — both flow into an
      Apache-2.0 distribution. No copyleft anywhere in the tree.)*
- [ ] The license is confirmed with the team or legal counsel before publishing.

---

## Status

Audited on **2026-08-20** against commit `4b7c471` (v0.7.0). Everything above is
confirmed except the one item that needs a human rather than a check: legal sign-off
on the licence.

> **Note:** This checklist is a starting point, not a legal guarantee. Consult your
> organization's security and legal teams for a full review before publishing.
