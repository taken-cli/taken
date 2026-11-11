# Configuration

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub personal access token. Set this to avoid API rate limits when using `taken install` or `taken update`. |
| `TAKEN_HOME` | Override the default `~/.taken/` location. Useful for testing or keeping multiple isolated taken environments. |
| `VISUAL` / `EDITOR` | Editor opened by `taken add` when scaffolding a new skill. Falls back to `vim` if neither is set. |

## config.yaml

`~/.taken/config.yaml` is written by `taken init` and read on every command. It is not currently editable via CLI — edit it directly if needed.

| Key | Description |
|-----|-------------|
| `username` | Your skill namespace (set during `taken init`). |
| `initialized_at` | ISO 8601 timestamp of last initialization. |
| `auto_commit` | If `true`, taken commits to `~/.taken/` automatically after mutating commands. Not yet CLI-exposed — defaults to `true`. |
| `auto_push` | If `true`, taken pushes after each auto-commit. Not yet CLI-exposed — defaults to `false`. |
| `skills.main_dir` | Main skills dir inside a project — the tracked copy. Defaults to `.agents/skills`. |
| `skills.mirror_dirs` | Mirror folders offered by `taken use`. Defaults to `[.claude/skills]`. Manage with [`taken mirrors`](commands/mirrors.md). |
| `skills.mirror_mode` | `symlink` (default) or `copy`. Chosen during `taken init`; override per project with `taken use --mode`. |

## projects.yaml

`~/.taken/projects.yaml` records which registry skills you copied into which project, keyed by absolute project path, along with a content hash used to detect local edits, the mirror folders chosen for each skill, and any per-project `mirror_mode` override. It is written by `use`, `save` and `update`.

It is machine-local, so taken adds it to `~/.taken/.gitignore` and it is never committed or pushed. Nothing taken-specific is written inside your projects.
