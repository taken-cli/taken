# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Taken?

A personal dotfile-style CLI for managing AI agent skills (`SKILL.md` files), compatible with the [skills.sh](https://skills.sh) ecosystem. Skills live in `~/.taken/skills/<namespace>/<skill-name>/`, git-backed, and can be linked into any project. Think chezmoi, but for agent skills.

## Commands

```bash
uv run taken               # run the CLI
task fmt                   # format: ruff check --fix + ruff format
task check                 # lint + typecheck: ruff check + pyright + ruff format --check
uv run ruff check .        # lint only
uv run pyright             # typecheck only
uv run ruff format .       # format only
```

No test suite yet — the project is in early implementation.

## Architecture

```
src/taken/
  main.py          # typer app, registers commands, exposes main() entrypoint
  commands/        # one file per CLI command; each file exports a single function
  models/          # pydantic models (pure data, no I/O)
  core/            # business logic (I/O, no CLI/typer concerns)
  utils/console.py # shared Rich Console instances
```

**Separation of concerns:** `commands/` handles CLI args and user-facing output; `core/` handles filesystem I/O and business logic; `models/` are pure data structures. Commands import from core and models — core never imports from commands.

**Two console instances** in `utils/console.py`: `console` (stdout) for normal output, `err_console` (stderr) for error panels and warnings. This keeps stdout pipeable.

**YAML I/O uses `ruamel.yaml`** (not PyYAML) to preserve comments on subsequent writes. All config and registry serialization goes through `core/config.py` and `core/registry.py`.

## Data model

- `~/.taken/config.yaml` — `TakenConfig`: username, taken_home, initialized_at, schema version
- `~/.taken/registry.yaml` — `Registry`: dict of `namespace/skill-name → RegistryEntry`
- `RegistryEntry` tracks provenance (`SkillSource`: personal/npx/taken), version, pin state, timestamps
- Skills on disk: `~/.taken/skills/<namespace>/<skill-name>/SKILL.md`
- Registry is the single source of truth for provenance; filesystem structure alone is not authoritative

## CLI commands planned

`init`, `add`, `install`, `use`, `update`, `list`, `remove` — see `docs/plan.md` for full spec. Only `init` is implemented so far; add new commands in `src/taken/commands/` and register them in `main.py` with `app.command("<name>")(<function>)`.
