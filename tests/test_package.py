from __future__ import annotations

import sqlite3
from array import array
from typing import TYPE_CHECKING, Any

from japanote.package import read_package, write_package

if TYPE_CHECKING:
    from pathlib import Path

ENCODINGS: dict[str, dict[str, Any]] = {
    'entry': {'id': 'delta', 'data': {'json': ['k', 'r', 's']}},
    'analyzer': {'value': {'int16 rows': 3}},
}


def make_database(path: Path, version: str, entries: dict[int, str]) -> str:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;
        CREATE TABLE entry (id INTEGER PRIMARY KEY, rank INTEGER NOT NULL, data TEXT NOT NULL);
        CREATE TABLE analyzer (key TEXT PRIMARY KEY, value) WITHOUT ROWID;
    """)
    db.execute("INSERT INTO meta VALUES ('version', ?)", (version,))
    db.executemany('INSERT INTO entry VALUES (?, 1, ?)', entries.items())
    matrix = array('h', [1, -2, 3, 400, 5, -600, 7, 8, 32767])
    db.executemany('INSERT INTO analyzer VALUES (?, ?)', [('size', 3), ('connections', matrix.tobytes())])
    db.commit()
    db.close()
    return str(path)


def dump(path: str) -> dict[str, list[tuple[object, ...]]]:
    db = sqlite3.connect(path)
    tables = [name for (name,) in db.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")]
    content = {name: sorted(db.execute(f'SELECT * FROM {name}').fetchall(), key=repr) for name in tables}
    db.close()
    return content


ENTRIES = {
    1000: '{"k":[{"t":"猫"}],"r":[{"t":"ねこ"}],"s":[{"g":["cat"]}]}',
    1005: '{"r":[{"t":"ああ"}],"s":[{"g":["ah"]}]}',
}


def test_package(tmp_path: Path) -> None:
    # NOTE: the rows of the matrix differ by more than 16 bits
    original = make_database(tmp_path / 'original.sqlite', '1', ENTRIES)
    write_package(original, str(tmp_path / 'package.xz'), ENCODINGS)
    read_package(str(tmp_path / 'package.xz'), str(tmp_path / 'copy.sqlite'))
    assert dump(str(tmp_path / 'copy.sqlite')) == dump(original)
