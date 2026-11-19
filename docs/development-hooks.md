# Development Hooks Setup

## Pre-commit bootstrap

The `setup-hooks` target ensures required tooling is available before hook installation.

### Command

```bash
make setup-hooks
```

### What it does

1. Verifies the virtual environment exists (`make install` if needed).
2. Syncs development dependencies with `uv sync --group dev`.
3. Installs two git hook types with
   `pre-commit install --hook-type pre-commit --hook-type commit-msg`.
   `.pre-commit-config.yaml` also sets
   `default_install_hook_types: [pre-commit, commit-msg]`, so a plain
   `pre-commit install` installs both as well.

This avoids failures like `Failed to spawn: pre-commit` when the binary is not yet installed.

## Hooks by stage

| Stage | Hooks | Effect |
|---|---|---|
| `pre-commit` | `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `ruff`, `ruff-format`, `nbstripout` | Format and lint the staged files |
| `commit-msg` | `commit-authorship` | Refuse a commit authored by, or attributed to, an AI agent |

Hooks that edit files are pinned to `stages: [pre-commit]` in
`.pre-commit-config.yaml`. At the `commit-msg` stage pre-commit passes the
commit message file to every hook whose stages include it, so an unpinned fixer
could rewrite the message. The read-only checks (`check-yaml`,
`check-added-large-files`) stay unpinned; they never modify a file.

## Commit authorship guard

`.github/standards.md` → Authorship: the developer is the sole author of every
commit and pull request. `scripts/check_commit_authorship.py` enforces it at the
`commit-msg` stage and refuses a commit when:

- the author or committer identity git resolves (`git var GIT_AUTHOR_IDENT` /
  `GIT_COMMITTER_IDENT`) is an AI agent: a name such as `Claude`, `Copilot` or
  `Codex`, or an `@anthropic.com` / `@openai.com` / `copilot@github.com` email.
  The usual cause is a stray `[user]` block an agent wrote into `.git/config`;
  remove it with `git config --local --unset-all user.name` and
  `git config --local --unset-all user.email`;
- the message carries a `Co-authored-by:` trailer naming an AI agent, or a
  "Generated with Claude / Copilot / Codex / OpenCode" line.

Naming a product in a message ("add the Claude-native transport") passes; only
attribution of authorship is refused. Lines starting with `#` are ignored, and
so is everything from the scissors line down (the diff `git commit -v` shows),
because git strips both after the hook ran. Tests:
`tests/test_check_commit_authorship.py`.

Run it by hand against a message file:

```bash
python3 scripts/check_commit_authorship.py .git/COMMIT_EDITMSG
```

Local hooks can be bypassed (`--no-verify`) or never installed. The guard
catches mistakes; it does not replace review.

## Optional: full quality gate as a git hook

The harness lab also runs `make ci` from a `local-quality-gate` hook on every
commit and push. This template does not ship it: every commit would pay the
full duration of `make ci`, which grows with the suite (in the harness lab,
about three minutes per commit). If a project wants it, add it to the
`local` repo in `.pre-commit-config.yaml`, preferably at the `pre-push` stage
only:

```yaml
      - id: local-quality-gate
        name: full local quality gate (make ci)
        entry: sh -c 'unset $(git rev-parse --local-env-vars); exec make ci'
        language: system
        stages: [pre-push]
        always_run: true
        pass_filenames: false
```

Then install the hook type with `pre-commit install --hook-type pre-push`.
The `unset` matters: git exports `GIT_DIR`, `GIT_INDEX_FILE` and similar
variables to hooks, and tests that create their own temporary repositories fail
if they inherit them.
