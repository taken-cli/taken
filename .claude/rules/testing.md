---
paths:
  - "tests/**/*.py"
---

# Testing Patterns

Integration tests only — no unit tests. Every test invokes the real CLI via `CliRunner` and asserts on filesystem state, registry state, and exit codes. No mocking of business logic.

## File layout

```
tests/
  conftest.py              # global fixtures: taken_home, cli_runner, sample_config, sample_registry_entry
  fixtures/
    config.py              # TakenConfigFactory
    registry.py            # RegistryEntryFactory
  commands/
    conftest.py            # autouse patch_taken_home
    test_<command>.py      # one file per CLI command
```

## Per-function marker

Use `@pytest.mark.anyio` on each test function. Do not use the module-level `pytestmark` variable.

```python
@pytest.mark.anyio
async def test_something(...) -> None:
    ...
```

## Test function naming

Follow the three-part double-underscore pattern:

```
test_<command>__<what_is_being_tested>__<expected_result>
```

Examples:

```python
async def test_add__create_valid_skill__skill_scaffolded_and_registered(...)
async def test_use__local_changes_user_declines__skill_skipped(...)
async def test_list__not_initialized__exits_with_error(...)
```

- `<command>` — the CLI command under test (`init`, `add`, `list`, `use`)
- `<what_is_being_tested>` — the scenario or condition (snake_case, be specific)
- `<expected_result>` — the observable outcome (snake_case, what you assert)

## Test function signature

All tests are `async def`. Fixtures are declared as parameters:

```python
async def test_something(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
```

## Structure: Arrange / Act / Assert

Every test has exactly three sections marked with comments:

```python
# Arrange
write_config(sample_config)
write_registry(Registry(), taken_home)

# Act
result = cli_runner.invoke(app, ["add", "my-skill"])

# Assert
assert result.exit_code == 0
assert "Skill Created" in result.output
```

## Pack assertions — do not write thin tests

Assert everything relevant in one test rather than spreading across multiple. A single happy-path test should check:
- exit code
- output text (success panel title, key names)
- filesystem state (dirs, files exist)
- file contents where meaningful
- registry/config state read back via core functions

## Invoking the CLI

```python
result = cli_runner.invoke(app, ["command", "arg"])
result = cli_runner.invoke(app, ["command"], input="1\ny\n")  # for interactive prompts
```

Check `result.exit_code == 0` (success) or `== 1` (app error). Exit code `2` means Typer rejected the arguments — that is a test setup bug, not a valid app-level error path.

## Reading back state

Always verify state through the same public API the app uses — never inspect YAML directly:

```python
config = read_config(taken_home)
registry = read_registry(taken_home)
project_config = read_project_config(tmp_path)
```

## Isolating taken_home

`patch_taken_home` in `tests/commands/conftest.py` is autouse — it monkeypatches `taken.core.paths.TAKEN_HOME` to `taken_home` (a per-test `tmp_path` subdirectory) for every command test automatically. Never patch it manually in individual tests.

```python
# tests/commands/conftest.py
@pytest.fixture(autouse=True)
def patch_taken_home(taken_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taken_paths, "TAKEN_HOME", taken_home)
```

## Isolating the project working directory

Commands that use `Path.cwd()` (e.g. `use`, `add` adopt mode) need a controlled project root. Use `monkeypatch.chdir(tmp_path)` in the arrange section:

```python
monkeypatch.chdir(tmp_path)
result = cli_runner.invoke(app, ["use", "alice/my-skill"])
# .taken.yaml and .agents/skills/ will be created inside tmp_path
```

## Monkeypatching — use typed functions, not lambdas

Pyright rejects untyped lambdas in `monkeypatch.setattr`. Define module-level typed helpers instead:

```python
# correct
def _noop_editor(path: Path) -> None:
    pass

def _always_is_path(arg: str) -> bool:
    return True

monkeypatch.setattr("taken.commands.add.open_in_editor", _noop_editor)
monkeypatch.setattr("taken.commands.add.is_path_argument", _always_is_path)
```

Patch the name as it appears in the command module (where it was imported), not where it was defined:

```python
# open_in_editor is imported into add.py → patch taken.commands.add.open_in_editor
# Confirm is imported into use.py   → patch taken.commands.use.Confirm.ask
```

## Factory fixtures for parameterised helpers

When a test helper needs fixture state (e.g. `taken_home`) but also takes per-call arguments, use a factory fixture that returns a callable. Never write a plain function that takes `taken_home` as a parameter.

```python
# correct
@pytest.fixture
def scaffold_skill(taken_home: Path) -> Callable[[str, str], Path]:
    def _create(namespace: str, name: str) -> Path:
        skill_src = taken_home / "skills" / namespace / name
        skill_src.mkdir(parents=True)
        (skill_src / "SKILL.md").write_text(f"# {name}\noriginal content")
        return skill_src
    return _create

# usage in test
async def test_something(..., scaffold_skill: Callable[[str, str], Path]) -> None:
    skill_src = scaffold_skill("alice", "my-skill")
```

## Building test data

Use factories for model objects. Pass only the fields your test cares about; the rest are randomised:

```python
from tests.fixtures.registry import RegistryEntryFactory
from tests.fixtures.config import TakenConfigFactory

entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
config = TakenConfigFactory.build(taken_home=taken_home)
```

For registry state, always construct `Registry()`, call `.add()`, then `write_registry()`:

```python
registry = Registry()
registry.add(entry)
write_registry(registry, taken_home)
```

## Writing lock files for adopt tests

`lookup_lock_entry` reads `skills-lock.json` from `Path.cwd()`. Write a real file rather than mocking the reader:

```python
lock_data = {
    "skills": {
        "cool-skill": {"source": "acme-org/agent-skills", "sourceType": "github", "ref": "abc1234"}
    }
}
(tmp_path / "skills-lock.json").write_text(json.dumps(lock_data))
monkeypatch.chdir(tmp_path)
```

## Error path tests

Every command has a "not initialized" guard. Test it by leaving `taken_home` empty (no `write_config` call):

```python
async def test_foo__not_initialized__exits_with_error(taken_home: Path, cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["foo", "arg"])
    assert result.exit_code == 1
    assert "Not Initialized" in result.output
```

## What not to test

- Interactive fuzzy picker paths (InquirerPy) — too hard to drive via `CliRunner`
- Internal implementation details — assert on public state (files, registry, exit code), not on which internal function was called
