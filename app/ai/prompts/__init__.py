"""Prompt management: versioned Markdown files loaded by name."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> str:
    """Return the prompt text for ``name`` (``prompts/<name>.md``)."""
    path = (_DIR / f"{name}.md").resolve()
    if path.parent != _DIR.resolve() or not path.is_file():
        raise FileNotFoundError(f"No prompt named '{name}'")
    return path.read_text(encoding="utf-8").strip()
