"""The format in which the dictionaries are published, and turned into SQLite databases once downloaded

A package is a text file compressed with xz. Its first line is a JSON header listing the tables,
with the SQL creating them and their number of rows; then, for each block of BLOCK_ROWS rows of each
table, each column is a line: a JSON array of its values. Columns compress much better than the pages
of SQLite, where the values of each row are mixed (e.g. 9 instead of 13 MB for the main dictionary),
and the database takes a few seconds to build. The blocks keep the lines short, since the add-on
reads them in a background thread, and parsing a long line would block Anki's interface meanwhile.

Some columns are encoded so that they compress better:
- 'delta': integers, as the differences with the previous ones (e.g. for sorted IDs);
- {'json': [fields]}: JSON objects, as one column per field (e.g. the writings, readings and senses
  of entries), with null for missing fields;
- {'int16 rows': width}: matrices of 16-bit integers (other values are kept as is), replaced by
  {'int16': height} and followed by one line per row, as the differences with the previous row; the
  add-on reads them as little-endian (see analyzer.py).

A patch, which updates a database from one version to the next, has the same format, but only lists
the rows that were added or changed in each table, and the primary keys of those that were removed.
"""
from __future__ import annotations

import json
import lzma
import sqlite3
import sys
from array import array
from collections.abc import Callable
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

BLOCK_ROWS = 16384
# called with the number of rows read so far, and the total
Progress = Callable[[int, int], None]


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _int16_array(data: bytes) -> array[int]:
    values = array('h')
    values.frombytes(data)
    if sys.byteorder == 'big':
        values.byteswap()
    return values


def _int16_bytes(values: array[int]) -> bytes:
    if sys.byteorder == 'big':
        values.byteswap()
    return values.tobytes()


def encode(values: list[Any], encoding: Any) -> list[str]:
    """Encode a column as lines"""
    if encoding is None:
        return [_dumps(values)]
    if encoding == 'delta':
        return [_dumps([value - previous for previous, value in zip([0, *values], values)])]
    if 'json' in encoding:
        objects = [json.loads(value) for value in values]
        return [_dumps([o.get(field) for o in objects]) for field in encoding['json']]
    if 'int16 rows' in encoding:
        width = encoding['int16 rows']
        encoded = []
        matrix_lines = []
        for value in values:
            if isinstance(value, bytes):
                matrix = _int16_array(value)
                height = len(matrix) // width
                encoded.append({'int16': height})
                # NOTE: the differences may not fit in 16 bits
                matrix_lines.extend(
                    _dumps([matrix[i] - (matrix[i - width] if i >= width else 0) for i in range(start, start + width)])
                    for start in range(0, height * width, width)
                )
            else:
                encoded.append(value)
        return [_dumps(encoded), *matrix_lines]
    msg = f'unknown encoding {encoding}'
    raise ValueError(msg)


def decode(lines: IO[str], encoding: Any) -> list[Any]:
    """Decode a column from the next lines"""
    if encoding is None:
        return list(json.loads(lines.readline()))
    if encoding == 'delta':
        values = json.loads(lines.readline())
        for i in range(1, len(values)):
            values[i] += values[i - 1]
        return list(values)
    if 'json' in encoding:
        fields = {field: json.loads(lines.readline()) for field in encoding['json']}
        return [
            _dumps({field: values[i] for field, values in fields.items() if values[i] is not None})
            for i in range(len(next(iter(fields.values()))))
        ]
    if 'int16 rows' in encoding:
        width = encoding['int16 rows']
        decoded = []
        for value in json.loads(lines.readline()):
            if isinstance(value, dict):
                matrix = array('h')
                previous = [0] * width
                for _ in range(value['int16']):
                    previous = [p + d for p, d in zip(previous, json.loads(lines.readline()))]
                    matrix.extend(previous)
                decoded.append(_int16_bytes(matrix))
            else:
                decoded.append(value)
        return decoded
    msg = f'unknown encoding {encoding}'
    raise ValueError(msg)


def write_package(db_path: str, path: str, encodings: dict[str, dict[str, Any]]) -> None:
    """Write the database at db_path as a package, with the encodings of the columns of each table"""
    db = sqlite3.connect(db_path)
    try:
        header: dict[str, Any] = {'tables': []}
        lines: list[str] = []
        tables = db.execute("SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY rowid").fetchall()
        for name, sql in tables:
            columns = [column[1] for column in db.execute(f'PRAGMA table_info({name})')]
            rows = db.execute(f'SELECT * FROM {name}').fetchall()
            table_encodings = encodings.get(name, {})
            header['tables'].append({
                'name': name, 'sql': sql, 'columns': columns, 'encodings': table_encodings, 'rows': len(rows),
            })
            lines.extend(_encode_rows(rows, columns, table_encodings))
    finally:
        db.close()
    with lzma.open(path, 'wt', encoding='utf-8', preset=9 | lzma.PRESET_EXTREME) as f:
        for line in [_dumps(header), *lines]:
            f.write(line + '\n')


def _encode_rows(rows: list[Any], columns: list[str], encodings: dict[str, Any]) -> Iterator[str]:
    for start in range(0, len(rows), BLOCK_ROWS):
        block = rows[start:start + BLOCK_ROWS]
        for i, column in enumerate(columns):
            yield from encode([row[i] for row in block], encodings.get(column))


def _decode_rows(lines: IO[str], table: dict[str, Any]) -> Iterator[list[tuple[Any, ...]]]:
    """The rows of a table, by block"""
    for start in range(0, table['rows'], BLOCK_ROWS):
        columns = [decode(lines, table['encodings'].get(column)) for column in table['columns']]
        block = list(zip(*columns))
        if len(block) != min(BLOCK_ROWS, table['rows'] - start):
            msg = f'unexpected number of rows in table {table["name"]}'
            raise ValueError(msg)
        yield block


def read_package(path: str, db_path: str, progress: Progress | None = None) -> None:
    """Create the database at db_path from a package"""
    db = sqlite3.connect(db_path)
    try:
        with lzma.open(path, 'rt', encoding='utf-8') as lines:
            header = json.loads(lines.readline())
            total = sum(table['rows'] for table in header['tables'])
            done = 0
            for table in header['tables']:
                db.execute(table['sql'])
                placeholders = ', '.join('?' * len(table['columns']))
                for block in _decode_rows(lines, table):
                    db.executemany(f'INSERT INTO {table["name"]} VALUES ({placeholders})', block)
                    done += len(block)
                    if progress is not None:
                        progress(done, total)
        db.commit()
    finally:
        db.close()


class PatchError(Exception):
    pass


def _version(db: sqlite3.Connection) -> str:
    row = db.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
    return str(row[0]) if row else ''


def _primary_key(db: sqlite3.Connection, table: str) -> list[str]:
    columns = sorted((column[5], column[1]) for column in db.execute(f'PRAGMA table_info({table})') if column[5])
    if not columns:
        msg = f'table {table} has no primary key'
        raise PatchError(msg)
    return [name for _, name in columns]


def _tables(db: sqlite3.Connection) -> dict[str, str]:
    return dict(db.execute("SELECT name, sql FROM sqlite_schema WHERE type = 'table' ORDER BY rowid"))


def write_patch(old_path: str, new_path: str, path: str, encodings: dict[str, dict[str, Any]]) -> None:
    """Write the patch that turns the database at old_path into the one at new_path"""
    old = sqlite3.connect(old_path)
    new = sqlite3.connect(new_path)
    try:
        old_tables, new_tables = _tables(old), _tables(new)
        if any(name in new_tables and new_tables[name] != sql for name, sql in old_tables.items()):
            msg = 'the tables changed'
            raise PatchError(msg)
        header: dict[str, Any] = {'from': _version(old), 'to': _version(new), 'tables': []}
        lines: list[str] = []
        for name, sql in new_tables.items():
            columns = [column[1] for column in new.execute(f'PRAGMA table_info({name})')]
            key = _primary_key(new, name)
            indexes = [columns.index(column) for column in key]
            new_rows = {tuple(row[i] for i in indexes): row for row in new.execute(f'SELECT * FROM {name}')}
            old_rows = (
                {tuple(row[i] for i in indexes): row for row in old.execute(f'SELECT * FROM {name}')}
                if name in old_tables else {}
            )
            removed = [list(k) for k in old_rows if k not in new_rows]
            changed = [row for k, row in new_rows.items() if old_rows.get(k) != row]
            table_encodings = encodings.get(name, {})
            header['tables'].append({
                'name': name, 'sql': sql, 'columns': columns, 'key': key, 'encodings': table_encodings,
                'rows': len(changed), 'removed': removed,
            })
            lines.extend(_encode_rows(changed, columns, table_encodings))
        # tables that were removed are left as they are
    finally:
        old.close()
        new.close()
    with lzma.open(path, 'wt', encoding='utf-8', preset=9 | lzma.PRESET_EXTREME) as f:
        for line in [_dumps(header), *lines]:
            f.write(line + '\n')


def apply_patch(path: str, db_path: str) -> dict[str, list[tuple[Any, ...]]]:
    """Apply a patch to the database at db_path, and return the keys of the rows that changed, by table"""
    changes: dict[str, list[tuple[Any, ...]]] = {}
    db = sqlite3.connect(db_path)
    try:
        with lzma.open(path, 'rt', encoding='utf-8') as lines:
            header = json.loads(lines.readline())
            version = _version(db)
            if version != header['from']:
                msg = f'the patch is for version {header["from"]}, not {version}'
                raise PatchError(msg)
            for table in header['tables']:
                name, columns, key = table['name'], table['columns'], table['key']
                db.execute(table['sql'].replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS', 1))
                rows = [row for block in _decode_rows(lines, table) for row in block]
                removed = [tuple(k) for k in table['removed']]
                where = ' AND '.join(f'{column} = ?' for column in key)
                db.executemany(f'DELETE FROM {name} WHERE {where}', removed)
                placeholders = ', '.join('?' * len(columns))
                db.executemany(f'INSERT OR REPLACE INTO {name} VALUES ({placeholders})', rows)
                indexes = [columns.index(column) for column in key]
                changes[name] = removed + [tuple(row[i] for i in indexes) for row in rows]
            if _version(db) != header['to']:
                msg = f'the patch did not update the version to {header["to"]}'
                raise PatchError(msg)
        db.commit()
    finally:
        db.close()
    return changes
