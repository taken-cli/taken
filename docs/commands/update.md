# taken update

Re-copy the latest registry version of a skill into the current project.

## Usage

```bash
taken update                     # interactive fuzzy picker
taken update <namespace/skill>   # direct, non-interactive
```

## Behavior

For each selected skill, taken compares the current project copy against the registry version using file hashes and takes one of these paths:

| State | Action |
|-------|--------|
| Registry and project both unchanged | Reported as "already up to date" |
| Registry changed, project unchanged | Copies registry version into project |
| Registry unchanged, project has local edits | Suggests `taken save` — no overwrite |
| Registry changed, project also has local edits | Prompts before overwriting |

## GitHub refresh (floating skills)

For skills installed via [`taken install`](install.md) that are **not pinned**, `taken update` first checks GitHub for upstream changes before copying to the project:

1. Fetches the latest commit SHA from the default branch
2. Compares the upstream skill folder hash to the registry copy
3. Re-downloads the skill if the upstream version has changed
4. Then re-copies the (now updated) registry version into the project

Pinned skills (installed with `--pin`) are never auto-upgraded.

## Requirements

Must be run from a directory containing `.taken.yaml`.

## Example

```bash
taken update vercel-labs/react-best-practices
# ↑ vercel-labs/react-best-practices abc123 → def456  (refreshed from GitHub)
# ✓ vercel-labs/react-best-practices → .agents/skills/react-best-practices/
```
