from __future__ import annotations

import sqlite3
from array import array
from typing import TYPE_CHECKING, Any

import pytest

from japanote import package
from japanote.package import PatchError, apply_patch, read_package, write_package, write_patch

if TYPE_CHECKING:
    from pathlib import Path

ENCODINGS: dict[str, dict[str, Any]] = {
    'entry': {'id': 'delta', 'data': {'json': ['k', 'r', 's']}},
    'analyzer': {'value': {'int16 rows': 3}},
}


def make_database(path: Path, version: str, entries: dict[int, str], extra_table: bool = False) -> str:
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
    if extra_table:
        db.execute('CREATE TABLE pitch (text TEXT NOT NULL, accents TEXT, PRIMARY KEY (text)) WITHOUT ROWID')
        db.execute("INSERT INTO pitch VALUES ('はし', '1')")
    db.commit()
    db.close()
    return str(path)


def dump(path: str) -> dict[str, list[tuple[object, ...]]]:
    db = sqlite3.connect(path)
    tables = [name for (name,) in db.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")]
    content = {name: sorted(db.execute(f'SELECT * FROM {name}').fetchall(), key=repr) for name in tables}
    db.close()
    return content


OLD = {
    1000: '{"k":[{"t":"猫"}],"r":[{"t":"ねこ"}],"s":[{"g":["cat"]}]}',
    1005: '{"r":[{"t":"ああ"}],"s":[{"g":["ah"]}]}',
    1010: '{"k":[{"t":"犬"}],"r":[{"t":"いぬ"}],"s":[{"g":["dog"]}]}',
}
NEW = {
    # 1005 removed, 1010 changed, 1020 added
    1000: OLD[1000],
    1010: '{"k":[{"t":"犬"}],"r":[{"t":"いぬ"}],"s":[{"g":["dog","hound"]}]}',
    1020: '{"k":[{"t":"鳥"}],"r":[{"t":"とり"}],"s":[{"g":["bird"]}]}',
}


def test_package(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    original = make_database(tmp_path / 'original.sqlite', '1', OLD)
    write_package(original, str(tmp_path / 'package.xz'), ENCODINGS)
    read_package(str(tmp_path / 'package.xz'), str(tmp_path / 'copy.sqlite'))
    assert dump(str(tmp_path / 'copy.sqlite')) == dump(original)


def test_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package, 'BLOCK_ROWS', 2)
    test_package(tmp_path / 'package')
    test_patch(tmp_path / 'patch')


def test_patch(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    old = make_database(tmp_path / 'old.sqlite', '1', OLD)
    new = make_database(tmp_path / 'new.sqlite', '2', NEW, extra_table=True)
    write_patch(old, new, str(tmp_path / 'patch.xz'), ENCODINGS)
    changes = apply_patch(str(tmp_path / 'patch.xz'), old)
    assert dump(old) == dump(new)
    assert sorted(changes['entry']) == [(1005,), (1010,), (1020,)]
    assert changes['analyzer'] == []

    # it only applies to the version it was made from
    with pytest.raises(PatchError):
        apply_patch(str(tmp_path / 'patch.xz'), old)
