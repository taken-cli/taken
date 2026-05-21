# taken init

First-time setup for taken. Creates `~/.taken/`, prompts for your skill namespace, and initializes a git repository.

## Usage

```bash
taken init
```

No arguments or flags.

## Behavior

### Username selection

taken needs a namespace to store your personal skills under (`~/.taken/skills/<username>/`). On first run it offers three choices:

1. **System username** — the result of `whoami` (always available)
2. **Git config name** — pulled from `git config user.name` (shown only if set)
3. **Enter manually** — free-text prompt for any name you prefer

The default is option 1. Press Enter to accept it or pick another option.

### What gets created

After you choose a username, `taken init` creates:

| Path | Description |
|------|-------------|
| `~/.taken/skills/<username>/` | Your personal skill namespace directory |
| `~/.taken/config.yaml` | Config file with your username and initialization timestamp |
| `~/.taken/registry.yaml` | Empty skill registry (source of truth for all managed skills) |
| `~/.taken/.git/` | Git repository with an initial commit |

### Example output

```
╭─────────────────────────────────────╮
│                                     │
│    Welcome to Taken                 │
│    A very particular set of         │
│    skills, managed.                 │
│                                     │
╰─────────────────────────────────────╯

Choose your skill namespace username:
  1  System username   → alice
  2  Git config name   → Alice Smith
  3  Enter manually

Pick an option [1/2/3] (1):

╭─── Taken Initialized ───────────────╮
│ ✓ Initialized at ~/.taken/          │
│ ✓ Username set to alice             │
│                                     │
│ Your personal skills namespace:     │
│ alice/<skill-name>                  │
╰─────────────────────────────────────╯
```

## Reinitializing

Running `taken init` when `~/.taken/` already exists triggers a reinitialization flow.

taken will ask whether you want to proceed, then offer two reset modes:

| Mode | What it does |
|------|-------------|
| **Reset config only** (default) | Overwrites `config.yaml` with new username/timestamp. Skills and registry are preserved. |
| **Full wipe** | Deletes `~/.taken/` entirely, then reinitializes from scratch. Requires a second confirmation. |

!!! warning
    Full wipe is irreversible if you have not pushed your `~/.taken/` git repository to a remote.
