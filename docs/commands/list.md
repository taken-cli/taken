# taken list

Show all skills in your registry.

## Usage

```bash
taken list
```

## Output

Displays a table with four columns:

| Column | Description |
|--------|-------------|
| **Skill** | Full name in `namespace/skill-name` format |
| **Source** | How the skill was added — `personal`, `npx`, or `taken` |
| **Version** | First 8 characters of the commit SHA (for installed skills), or `1` for personal skills |
| **Date** | Creation date (personal) or install date (installed) |

A count of total skills is shown below the table.

## Source types

| Source | Meaning |
|--------|---------|
| `personal` | Created with `taken add` or adopted from a local path without a lock file |
| `npx` | Adopted from a project that used the skills.sh `npx` installer |
| `taken` | Installed from GitHub via `taken install` |
