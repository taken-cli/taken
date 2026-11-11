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
- If the hash differs — the edited copy is copied back to `~/.taken/skills/<ns>/<name>/`, the registry and `~/.taken/projects.yaml` are updated, and a git commit is made in `~/.taken/`

In `copy` mirror mode, taken checks every copy (e.g. `.agents/skills/<name>` and `.claude/skills/<name>`) and saves whichever one changed. If more than one copy was edited differently, it asks which to keep. After saving, all copies are brought back in sync.

## Requirements

- Must be run from a project where `taken use` was previously run (tracked in `~/.taken/projects.yaml`)
- The skill must be tracked for that project

## Example

```bash
# Edit a skill in the project
vim .agents/skills/my-skill/SKILL.md

# Push the edit back to registry
taken save my-namespace/my-skill
# ✓ my-namespace/my-skill → ~/.taken/skills/my-namespace/my-skill/
```
