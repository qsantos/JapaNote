"""Split sentences into words, with their readings, using Janome (https://github.com/mocobeta/janome)

Janome is a pure-Python morphological analyzer that bundles the IPA dictionary; as such, it works on
every platform without compiling anything. It is not shipped with the add-on since it is large, and
only needed for text that is not in the dictionary; instead, it is downloaded on first use.
"""
from __future__ import annotations

import os
import sys
from typing import Any

from .download import Progress, install_wheel, user_file

JANOME_VERSION = '0.5.0'
JANOME_URL = (
    'https://files.pythonhosted.org/packages/73/7d/70f4069f4bbf0fca023e82a1fbbade6f5216365d4fe259fee1950723eca5/'
    'Janome-0.5.0-py2.py3-none-any.whl'
)
JANOME_SHA256 = 'd098670394a77881ce2f6b7d696c0ea5ff74c0c8cf74a8a882159ec82c0e6dc7'
JANOME_SIZE = 19_654_103

_tokenizer: Any = None


def janome_path() -> str:
    return user_file(f'janome-{JANOME_VERSION}')


def is_installed() -> bool:
    return os.path.isdir(janome_path())


def is_loaded() -> bool:
    return _tokenizer is not None


def install(progress: Progress | None = None) -> None:
    install_wheel(JANOME_URL, JANOME_SHA256, janome_path(), progress)


def load() -> None:
    """Load Janome's dictionary; this takes a few seconds"""
    global _tokenizer  # noqa: PLW0603
    if _tokenizer is not None:
        return
    path = janome_path()
    if path not in sys.path:
        sys.path.append(path)
    from janome.tokenizer import Tokenizer  # type: ignore[import-not-found]
    _tokenizer = Tokenizer()


def tokenize(text: str) -> list[tuple[str, str | None]]:
    """Split text into (surface, reading) pairs; the reading is None when unknown"""
    assert _tokenizer is not None
    return [
        (token.surface, None if token.reading == '*' else token.reading)
        for token in _tokenizer.tokenize(text)
    ]
