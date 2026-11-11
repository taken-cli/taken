# taken

> *"A very particular set of skills, acquired over a very long career."*

**taken** is a personal dotfile-style CLI for managing AI agent skills (`SKILL.md` files). Think [chezmoi](https://www.chezmoi.io/), but for agent skills — your skills live in `~/.taken/`, are git-backed, and can be linked into any project on demand.

Fully compatible with the [skills.sh](https://skills.sh) ecosystem (Claude Code, Cursor, OpenAI Codex, and 40+ agents).

---

## Install

```bash
uv tool install taken-cli
```

```bash
pipx install taken-cli
```

Or run it without installing, via [uvx](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx taken-cli init
uvx taken-cli use
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
```
Interactive fuzzy picker when multiple skills are found.

**5. Use a skill in a project**
```bash
taken use
```
Fuzzy-picks from your registry, copies the skill into `.agents/skills/` in the current project, and mirrors it into `.claude/skills/` (symlink or copy).

**6. Push edits back to registry**
```bash
taken save
```
Promotes refined project skills back to `~/.taken/` so they propagate to future projects.

**7. Update project skills**
```bash
taken update
```
Re-copies the latest registry version into the project.
