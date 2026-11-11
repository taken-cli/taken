# taken use

Copy a skill from your registry into the current project and mirror it into other agent directories.

## Usage

```bash
taken use                              # interactive fuzzy picker
taken use <namespace/skill>            # direct, non-interactive
taken use <namespace/skill> --mode copy   # override mirror mode for this project (remembered)
taken use <namespace/skill> -m .cursor/skills   # pick mirror folders without the prompt (repeatable)
taken use <namespace/skill> --no-mirror         # main copy only, no mirrors
```

## Behavior

1. If no argument is given, shows a fuzzy picker over your full registry (space/tab to select multiple, enter to confirm)
2. Copies the skill folder into the main skills dir — `.agents/skills/<skill-name>/` by default
3. Asks which mirror folders to link it into (see below)
4. Mirrors it into each chosen folder as a relative symlink or a full copy, and prints every link it made
5. Records the copy and the chosen folders in `~/.taken/projects.yaml`, keyed by the project path

Nothing taken-specific is written into the project — only the skill folders themselves. Tracking is personal and lives in `~/.taken/`.

## Choosing mirror folders

Every `taken use` shows a checkbox list of your mirror folders:

```
? Symlink into which folders? (space to toggle, enter to confirm — none is fine)
❯ ◉ .claude/skills
  ◉ .cursor/skills
```

- For a new skill, every folder is ticked. For a skill already in the project, the folders it used last time are ticked.
- The choice is saved per skill, so `taken update` and `taken save` keep using the same folders.
- Unticking a folder removes taken's link (or unedited copy) for that skill there. Anything you edited, or that taken didn't create, is left alone.
- `--mirror` / `-m` and `--no-mirror` skip the prompt. When there's no terminal (scripts, CI), it also skips the prompt and uses the same defaults.

The list of folders is managed with [`taken mirrors`](mirrors.md).

The output shows exactly where each skill went:

```
✓ me/my-skill → .agents/skills/my-skill/
  🔗 .claude/skills/my-skill → .agents/skills/my-skill
  🔗 .cursor/skills/my-skill → .agents/skills/my-skill
```

## Mirror mode

| Mode | What lands in `.claude/skills/<name>` |
|------|---------------------------------------|
| `symlink` (default) | A relative link to `../../.agents/skills/<name>` — one real copy, always in sync. Works after cloning. |
| `copy` | An independent full copy. `update` refreshes every copy; `save` picks up edits from whichever copy changed. |

The default comes from `skills.mirror_mode` in [`config.yaml`](../configuration.md) (chosen during `taken init`). `--mode` overrides it for the current project and is remembered for later commands. If a symlink cannot be created (e.g. on Windows without the right permissions), taken falls back to a copy and warns.

## Overwrite protection

If a skill already exists in the project and you've modified any of its copies, taken detects the change by comparing file hashes and prompts before overwriting:

```
⚠  my-skill has local changes in your project.
  Overwrite my-skill? [y/N]
```

If a mirror location (e.g. `.claude/skills/my-skill`) already exists and wasn't created by taken, it asks before replacing it.

Decline to keep your local edits. Use [`taken save`](save.md) to push them back to the registry first.

## Example

```bash
cd my-project
taken use
# → fuzzy picker → select react-best-practices, typescript
# → checkbox: which mirror folders? → .claude/skills
# → copies to .agents/skills/react-best-practices/ and .agents/skills/typescript/
# → links .claude/skills/react-best-practices/ and .claude/skills/typescript/
# → tracked in ~/.taken/projects.yaml
```
