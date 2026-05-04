# AGENTS.md

## Rules

- Never install a new package without explicit user permission. Ask first.

## Commands

```bash
uv run taken               # run the CLI
task fmt                   # ruff check --fix + ruff format
task check                 # ruff check + pyright + ruff format --check
```

## Architecture

```
src/taken/
  main.py          # typer app + entrypoint
  commands/        # one file per command, one exported function each
  models/          # pydantic models, pure data, no I/O
  core/            # business logic, I/O, no CLI/typer concerns
  utils/console.py # shared Rich Console instances
```

- `commands/` imports from `core/` and `models/` — never the reverse
- `console` (stdout) for normal output, `err_console` (stderr) for errors/warnings
- YAML I/O uses `ruamel.yaml` (not PyYAML) — all reads/writes via `core/config.py` and `core/registry.py`
- `core/paths.py` exposes `TAKEN_HOME`; respects `TAKEN_HOME` env var for test isolation

## Tests

- Naming: `test_<command>__<what_is_being_tested>__<expected_result>`
- Always use `@pytest.mark.anyio` per function, not module-level `pytestmark`
- Always include `# Arrange / # Act / # Assert` comments in every test
- `tests/commands/conftest.py` autouse fixture patches `taken_paths.TAKEN_HOME` via `monkeypatch.setattr`
