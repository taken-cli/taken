# taken mirrors

Manage the agent folders that [`taken use`](use.md) can link skills into, such as `.claude/skills` or `.cursor/skills`.

## Usage

```bash
taken mirrors list                    # show main dir, mirror mode, and mirror folders
taken mirrors add <dir>               # offer a new folder in `taken use`
taken mirrors remove <dir>            # stop offering a folder
```

## Behavior

- Folders are relative to the project root. A trailing slash is ignored, so `.cursor/skills/` and `.cursor/skills` are the same folder.
- Absolute paths, `~`, `..`, and the main skills dir (`.agents/skills`) are rejected.
- The list is stored as `skills.mirror_dirs` in `~/.taken/config.yaml`, and each change is auto-committed in `~/.taken/`.
- `remove` only stops `taken use` from offering the folder. Links already in your projects stay. Re-run `taken use <skill>` in a project to drop them.

## Example

```bash
taken mirrors add .cursor/skills
# ✓ Added .cursor/skills — `taken use` will offer it from now on.

taken mirrors list
# Main dir:    .agents/skills
# Mirror mode: symlink
# Mirror dirs:
#   • .claude/skills
#   • .cursor/skills
```
