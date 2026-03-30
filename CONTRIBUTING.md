# Contributing to AgentRoom

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/sparkvibe-io/AgentRoom.git
cd AgentRoom
uv sync
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Code Quality

We use **ruff** for linting and **pyright** for type checking (strict mode):

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run pyright src/
```

All code must pass lint and type checks before merging.

## Code Style

- Python 3.13+, line length 100 (enforced by ruff)
- Type annotations on all public functions
- Pydantic models for all data structures
- Async/await for I/O operations

## Pull Requests

1. Fork the repo and create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass and code is lint-clean
4. Keep PRs focused — one feature or fix per PR
5. Write a clear description of what changed and why

## Reporting Issues

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
