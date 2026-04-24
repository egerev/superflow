# Python Greenfield Template

## Directory Structure
```
├── src/
│   └── {project_name}/
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── .gitignore
├── .env.example
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## pyproject.toml
```toml
[project]
name = "{project_name}"
version = "0.1.0"
description = "{project_description}"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## .gitignore
```
__pycache__/
*.pyc
.env
.venv/
dist/
*.egg-info/
.worktrees/
.superflow/events.jsonl
.superflow/archive/
.superflow-state.json
CLAUDE.local.md
```

## README.md template
```markdown
# {project_name}

{project_description}

## Getting Started

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

## Development

- `pytest` — run tests
- `ruff check .` — lint code
- `ruff format .` — format code
- `mypy .` — type check
```
