# taken install

Install one or more skills from a GitHub repository.

## Usage

```bash
taken install <source> [options]
```

## Source formats

```bash
taken install vercel-labs/agent-skills                       # all skills (interactive picker)
taken install vercel-labs/agent-skills/react-best-practices  # specific skill by path
taken install https://github.com/vercel-labs/agent-skills    # full URL
```

## Options

| Flag | Description |
|------|-------------|
| `--skill <name>` | Install a specific skill by name (repeatable). Skips the interactive picker. |
| `--ref <branch\|tag\|sha>` | Install from a specific branch, tag, or commit SHA. Defaults to the repo's default branch. |
| `--pin` | Lock to the exact commit SHA — `taken update` will never auto-upgrade this skill. |

## Behavior

1. Resolves the ref to a commit SHA
2. Discovers all `SKILL.md` files in the repository
3. If multiple skills are found and no `--skill` filter is given, shows a fuzzy picker (space/tab to select, enter to confirm)
4. Downloads and registers each selected skill under `~/.taken/skills/<owner>/<skill-name>/`

Already-registered skills are skipped without error.

## Examples

```bash
# Install a single specific skill non-interactively
taken install vercel-labs/agent-skills --skill react-best-practices

# Install multiple skills at once
taken install vercel-labs/agent-skills --skill react-best-practices --skill typescript

# Install from a specific tag and pin it
taken install vercel-labs/agent-skills --ref v1.2.0 --pin
```

## GitHub rate limits

Unauthenticated requests are limited to 60/hour. Set `GITHUB_TOKEN` to avoid hitting limits:

```bash
export GITHUB_TOKEN=ghp_...
```
