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
