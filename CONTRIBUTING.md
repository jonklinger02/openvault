# Contributing to OpenVault

## Development Setup

1. Fork and clone the repo
2. `pip install -e ".[dev]"`
3. Run tests: `pytest`
4. Lint: `ruff check .`

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `test:` adding/updating tests
- `ci:` CI/CD changes
- `refactor:` code restructuring

## Pull Requests

- One logical change per PR
- All CI checks must pass
- Include tests for new features
