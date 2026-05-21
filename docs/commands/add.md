# taken add

Create a new personal skill or adopt an existing skill folder into taken management.

## Usage

```bash
taken add <skill-name>       # create a new skill
taken add <path/to/folder>   # adopt an existing skill folder
```

## Create mode

When you pass a plain name, taken scaffolds a new skill under your namespace and opens it in your editor.

```bash
taken add my-skill
```

What happens:

1. Creates `~/.taken/skills/<username>/my-skill/SKILL.md`
2. Registers it as a `personal` skill
3. Opens `SKILL.md` in your `$VISUAL` / `$EDITOR` (falls back to `vim`)

**Name rules:** lowercase letters, numbers, hyphens, and underscores only. Must start with a letter or number. Do not include a namespace — your username is added automatically.

```bash
taken add react-best-practices   # ✓
taken add you/react-practices    # ✗ — namespace not allowed here
taken add my skill               # ✗ — no spaces
```

## Adopt mode

When you pass a path (absolute or relative, must point to a directory), taken copies it into `~/.taken/` and registers it.

```bash
taken add ./agents/my-skill/
taken add /path/to/skill-folder/
```

Taken detects the argument as a path if it starts with `/`, `./`, or `../`.

**Provenance detection:** if a `skills.sh` lock file (`.agents/skills.lock`) exists in the current project, taken reads it to determine the original source, namespace, and version of the skill automatically. Without a lock file, the skill is registered as personal under your namespace.

## Notes

- If the skill already exists in your registry, the command exits with an error.
- After adoption or creation, a git commit is made in `~/.taken/` automatically (if `auto_commit` is enabled).
