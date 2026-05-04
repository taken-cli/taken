# taken

> *"A very particular set of skills, acquired over a very long career."*

**taken** is a personal dotfile-style CLI for managing AI agent skills (`SKILL.md` files). Think [chezmoi](https://www.chezmoi.io/), but for agent skills — your skills live in `~/.taken/`, are git-backed, and can be linked into any project on demand.

Fully compatible with the [skills.sh](https://skills.sh) ecosystem (Claude Code, Cursor, OpenAI Codex, and 40+ agents).

---

## Install

```bash
uv tool install taken
```

```bash
pip install taken
```

---

## Quick Start

**1. Initialize**
```bash
taken init
```
Sets up `~/.taken/`, prompts for your namespace, creates config and registry.

**2. Create a personal skill**
```bash
taken add my-skill
```
Scaffolds `~/.taken/skills/<you>/my-skill/SKILL.md` and opens it in your editor.

**3. Adopt an existing skill from a project**
```bash
taken add ./agents/my-skill/
```
Copies the skill folder into `~/.taken/` and registers it, detecting provenance from skills.sh lock files automatically.

**4. Install a skill from GitHub**
```bash
taken install vercel-labs/agent-skills
taken install vercel-labs/agent-skills/react-best-practices
taken install https://github.com/vercel-labs/agent-skills
```
Interactive fuzzy picker when multiple skills are found. Use `--skill` to install specific ones non-interactively, `--ref` to pin to a branch/tag/SHA, `--pin` to lock the version.

**5. Use a skill in a project**
```bash
taken use
```
Fuzzy-picks from your registry and copies the skill into `.agents/skills/` in the current project. Records state in `.taken.yaml` (committed to git — no taken dependency needed for teammates).

**6. Push edits back to registry**
```bash
taken save
```
If you refined a skill while working in a project, `save` promotes those edits back to `~/.taken/` so they propagate to future projects.

**7. Update project skills**
```bash
taken update
```
Re-copies the latest registry version into the project. Warns before overwriting if local edits are detected.

---

## Commands

| Command | Description |
|---|---|
| `taken init` | First-time setup — creates `~/.taken/`, prompts for namespace |
| `taken add <skill-name>` | Create a new personal skill, opens in editor |
| `taken add <path>` | Adopt an existing skill folder into taken management |
| `taken install <source>` | Install a skill from GitHub |
| `taken use [namespace/skill]` | Copy a skill from registry into the current project |
| `taken save [namespace/skill]` | Push project edits back to registry |
| `taken update [namespace/skill]` | Re-copy latest registry version into project |
| `taken list` | Show all skills in the registry |
| `taken remove <namespace/skill>` | Remove a skill from registry |

---

## How It Works

Skills live in `~/.taken/skills/<namespace>/<skill-name>/`. The registry at `~/.taken/registry.yaml` is the single source of truth for provenance — tracking whether a skill was created personally, adopted from a project, or installed from GitHub.

When you run `taken use`, the skill is copied (never symlinked) into `.agents/skills/` and tracked in `.taken.yaml` at the project root. This file is committed to git, making the project self-contained — teammates don't need taken installed to use the skills.

---

## Storage Layout

```
~/.taken/
  config.yaml       # username, preferences
  registry.yaml     # all skills + metadata
  skills/
    you/
      my-skill/
        SKILL.md
    vercel-labs/
      react-best-practices/
        SKILL.md
```
