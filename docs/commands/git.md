# taken git

Run any git command inside `~/.taken/`.

## Usage

```bash
taken git <git args>
```

## Description

A thin passthrough to `git` with `~/.taken/` as the working directory. Any valid git subcommand works.

## Examples

```bash
taken git status
taken git log --oneline
taken git remote add origin git@github.com:you/taken-skills.git
taken git push -u origin main
taken git pull
```

This is the recommended way to push your `~/.taken/` repository to a remote for backup or sharing across machines.
