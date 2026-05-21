# taken save

Push project skill edits back to your `~/.taken/` registry.

## Usage

```bash
taken save                       # interactive fuzzy picker
taken save <namespace/skill>     # direct, non-interactive
```

## Behavior

`taken save` is the reverse of [`taken use`](use.md). After refining a skill while working in a project, use this command to promote those edits back to the registry so they propagate to future projects.

For each selected skill:

- If the file hash matches what was originally copied — reported as "no changes", nothing written
- If the hash differs — the project copy is copied back to `~/.taken/skills/<ns>/<name>/`, the registry and `.taken.yaml` are updated, and a git commit is made in `~/.taken/`

## Requirements

- Must be run from a directory containing `.taken.yaml` (i.e., a project where `taken use` was previously run)
- The skill must be tracked in that `.taken.yaml`

## Example

```bash
# Edit a skill in the project
vim .agents/skills/my-skill/SKILL.md

# Push the edit back to registry
taken save my-namespace/my-skill
# ✓ my-namespace/my-skill → ~/.taken/skills/my-namespace/my-skill/
```
