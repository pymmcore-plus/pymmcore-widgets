# pymmcore-widgets

This project is a collection of Qt-based widgets providing control
and monitoring of the `pymmcore_plus.CMMCorePlus` object.

The key libraries that this project depends on is: `pymmcore-plus`, the core
programmatic library (which in turn wraps `pymmcore`: python bindings for the
C++ Micro-Manager core library).

## Commands

- Install: `uv sync`
- Test: `uv run pytest` (can use `uv run pytest -n 6` to run in parallel)
- Lint & Type check: `uv run prek -a`
- Install pre-commit hooks: `uv run prek install -f`

## Conventions & Project Principles

- Use `uv` for everything.
- PRs require passing CI before merge (`uv run prek -a && uv run pytest`).
- Resist using `setStyleSheet`.  Theming will be done application-wide.
- All qt library objects should be imported from qtpy instead of
  PyQt6/PySide6 directly.
