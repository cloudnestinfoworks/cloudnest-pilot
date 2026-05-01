# Contributing to Cloudnest Pilot

Thanks for considering a contribution! This document explains how to get
started.

## Quick start

```bash
git clone https://github.com/cloudnestinfoworks/cloudnest-pilot.git
cd cloudnest-pilot

# Create venv and install in editable mode with dev deps
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Run tests
pytest
```

## Ways to contribute

### Reporting bugs

Open an issue using the **Bug report** template. Include:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS, Python version, and Cloudnest Pilot version

### Suggesting features

Open an issue using the **Feature request** template. Be specific about
the use case — "deploy on Azure" is less helpful than "I have a client who
runs ARO and wants to use this for them too."

### Code contributions

For small fixes: just open a PR.

For larger changes: open an issue first to discuss the approach. We don't
want you to spend hours on a PR that doesn't fit the project direction.

## Development workflow

1. Fork the repo and clone your fork
2. Create a feature branch: `git checkout -b feature/some-thing`
3. Make changes with tests
4. Run linting and tests locally:
   ```bash
   ruff check .
   black --check .
   pytest
   ```
5. Commit using conventional commit messages:
   - `feat: add Azure cluster deployment`
   - `fix: handle empty AWS region gracefully`
   - `docs: clarify install steps for Windows`
   - `test: cover demo mode pattern matching`
6. Push to your fork and open a PR against `main`
7. CI will run tests and linting; address any failures

## Code style

- Python 3.10+ syntax (we use modern type hints)
- Format with `black` (100 char line length)
- Lint with `ruff` (config in `pyproject.toml`)
- Type-hint public APIs (private helpers can skip)
- Write docstrings for any non-obvious function
- Prefer composition over inheritance
- Keep functions short and pure when possible

## Adding a new tool

The agent's capabilities live in `tools/`. Here's how to add a new one:

1. Create `tools/your_tool.py`:

```python
from .registry import tool

@tool(
    name="your_tool_name",
    description="What this tool does, in plain English. Claude reads this.",
    input_schema={
        "type": "object",
        "properties": {
            "arg_name": {
                "type": "string",
                "description": "What this argument means",
            },
        },
        "required": ["arg_name"],
    },
    requires_confirmation=False,  # True if the tool changes anything
)
def your_tool_name(arg_name: str) -> str:
    """Do the thing. Return a string for Claude to read."""
    # ... your implementation ...
    return "result text for Claude"
```

2. Import it in `cloudnest_pilot/core.py` so the decorator runs:

```python
from tools import shell, filesystem, aws, ocp, your_tool  # noqa: F401
```

3. Add tests in `tests/test_your_tool.py`

4. Done. Claude will see your tool in its available tools list on the
   next turn.

## Adding a new cloud provider

Currently we support AWS via IPI. Adding Azure / GCP / OpenStack means:

1. Create `tools/azure.py` (or whichever) with provider-specific tools
   (`check_azure`, `list_azure_locations`, etc.)
2. Update `SYSTEM_PROMPT` in `cloudnest_pilot/core.py` to mention the new
   capability
3. Add demo responses in `cloudnest_pilot/demo.py`
4. Add documentation in `docs/`
5. Open a PR and we'll review

## Pull request review

- One maintainer must approve before merge
- All CI checks must pass
- Conventional commits are required for changelog generation
- Squash merge is the default

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
TLDR: be kind, be patient, assume good intent.

## Licensing

Cloudnest Pilot is Apache 2.0. By submitting a PR you agree to license
your contribution under the same terms.

## Getting help

- GitHub Discussions: https://github.com/cloudnestinfoworks/cloudnest-pilot/discussions (community chat)
- GitHub Discussions: for design questions and architecture topics
- Issues: for bugs and feature requests
- Email: connect@cloudnestinfoworks.com (for private concerns)

## Recognition

All contributors are acknowledged in:

- The CHANGELOG (per release)
- The README (Contributors section)
- Our `CONTRIBUTORS.md` file (auto-generated from git history)

Thanks for making Cloudnest Pilot better.
