"""The tests need the databases built by tools/build_dictionaries.py

Set JAPANOTE_DB_DIR to the directory containing jmdict.sqlite (and names.sqlite).
"""
import os
import sys
import types

import pytest

# the modules under test do not depend on Anki, but the package's __init__ does; so, register the
# package without running its __init__
package = types.ModuleType('japanote')
package.__path__ = [os.path.join(os.path.dirname(__file__), '..', 'japanote')]
sys.modules['japanote'] = package

from japanote.deinflect import Deinflector  # noqa: E402
from japanote.dictionary import Dictionary  # noqa: E402


def database(name: str) -> str:
    path = os.path.join(os.environ.get('JAPANOTE_DB_DIR', ''), f'{name}.sqlite')
    if not os.path.exists(path):
        pytest.skip(f'{name}.sqlite not found; set JAPANOTE_DB_DIR')
    return path


@pytest.fixture(scope='session')
def jmdict() -> Dictionary:
    return Dictionary(database('jmdict'), 'EntL')


@pytest.fixture(scope='session')
def names(jmdict: Dictionary) -> Dictionary:
    return Dictionary(database('names'), 'EntN', kanji_source=jmdict)


@pytest.fixture(scope='session')
def deinflector() -> Deinflector:
    return Deinflector()
