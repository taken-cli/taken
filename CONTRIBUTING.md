# Contributing to taken

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- Python 3.11+
- [Task](https://taskfile.dev/installation/) (recommended) — `brew install go-task`

## Setup

```bash
git clone https://github.com/taken-cli/taken.git
cd taken
task setup
```

`task setup` installs dev + test dependencies and configures pre-commit hooks.

## Development

```bash
uv run taken          # run the CLI
task test             # run tests
task fmt              # auto-fix lint + formatting
task check            # lint + type check + format check (runs on commit)
```

`task check` runs three things in sequence:
- `ruff check` — linting
- `pyrefly check` — strict type checking
- `ruff format --check` — formatting

This runs automatically as a pre-commit hook. PRs must pass it.

If you don't have Task installed, run the commands directly:

```bash
uv run pytest                          # test
uv run ruff check --fix . && uv run ruff format .        # fmt
uv run ruff check . && uv run pyrefly check && uv run ruff format --check --diff .  # check
```

## Git workflow

- Rebase onto `main` instead of merging: `git pull --rebase origin main`
- Squash fixup commits before opening a PR — keep history clean

## Submitting a PR

1. Fork the repo and create a branch
2. Make your changes with tests
3. Run `task check` — must pass before opening a PR
4. Open a PR against `main`

## Questions

Open a [GitHub issue](https://github.com/taken-cli/taken/issues) with the Question template.
