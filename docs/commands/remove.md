# taken remove

Remove a skill from your registry and delete its files from `~/.taken/`.

## Usage

```bash
taken remove                     # interactive fuzzy picker
taken remove <namespace/skill>   # direct, non-interactive
```

## Behavior

For each selected skill, taken asks for confirmation before removing:

```
Remove namespace/my-skill? [y/N]
```

On confirmation:

1. Deletes `~/.taken/skills/<namespace>/<skill-name>/`
2. Removes the entry from `registry.yaml`
3. Commits the change to `~/.taken/`

**Project copies are not affected.** Skills already copied into `.agents/skills/` in your projects remain untouched — `taken remove` only affects the registry.

!!! warning
    This is irreversible unless you have pushed `~/.taken/` to a remote and can restore from there. For GitHub-installed skills, you can always reinstall with `taken install`.
