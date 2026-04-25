```markdown
taken/
├── pyproject.toml
├── README.md
├── .python-version
│
└── taken/
    ├── __init__.py
    ├── main.py              # entry point, app = typer.App()
    │
    ├── commands/            # one file per CLI command
    │   ├── __init__.py
    │   ├── init.py          # taken init
    │   ├── add.py           # taken add
    │   ├── install.py       # taken install
    │   ├── use.py           # taken use
    │   ├── update.py        # taken update
    │   ├── list.py          # taken list
    │   └── remove.py        # taken remove
    │
    ├── models/              # pydantic models
    │   ├── __init__.py
    │   ├── registry.py      # RegistryEntry, Registry
    │   └── config.py        # TakenConfig
    │
    ├── core/                # business logic, no CLI concerns
    │   ├── __init__.py
    │   ├── registry.py      # read/write registry.yaml
    │   ├── config.py        # read/write config.yaml
    │   ├── skill.py         # skill file operations
    │   └── linker.py        # symlink / copy logic for `taken use`
    │
    └── utils/
        ├── __init__.py
        ├── console.py       # rich console instance, shared
        └── fs.py            # filesystem helpers
```