# taken use

Copy a skill from your registry into the current project.

## Usage

```bash
taken use                        # interactive fuzzy picker
taken use <namespace/skill>      # direct, non-interactive
```

## Behavior

1. If no argument is given, shows a fuzzy picker over your full registry (space/tab to select multiple, enter to confirm)
2. Copies the skill folder into `.agents/skills/<skill-name>/` in the current working directory
3. Records the copy in `.taken.yaml` at the project root (created if it doesn't exist)

`.taken.yaml` is meant to be committed — it lets teammates use the skills without needing taken installed.

## Overwrite protection

If a skill already exists in the project and you've modified it locally, taken detects the change by comparing file hashes and prompts before overwriting:

```
⚠  my-skill has local changes in your project.
  Overwrite my-skill? [y/N]
```

Decline to keep your local edits. Use [`taken save`](save.md) to push them back to the registry first.

## Example

```bash
cd my-project
taken use
# → fuzzy picker → select react-best-practices, typescript
# → copies to .agents/skills/react-best-practices/ and .agents/skills/typescript/
# → updates .taken.yaml
```
