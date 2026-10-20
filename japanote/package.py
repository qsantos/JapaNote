"""The format in which the dictionaries are published, and turned into SQLite databases once downloaded

A package is a text file compressed with xz. Its first line is a JSON header listing the tables,
with the SQL creating them; then, for each table, each column is a line: a JSON array of its values.
Columns compress much better than the pages of SQLite, where the values of each row are mixed (e.g.
9 instead of 13 MB for the main dictionary), and the database takes a few seconds to build.

Some columns are encoded so that they compress better:
- 'delta': integers, as the differences with the previous ones (e.g. for sorted IDs);
- {'json': [fields]}: JSON objects, as one column per field (e.g. the writings, readings and senses
  of entries), with null for missing fields;
- {'int16 rows': width}: matrices of 16-bit integers (other values are kept as is), each row as the
  differences with the previous one; the add-on reads them as little-endian (see analyzer.py).
"""
from __future__ import annotations

import json
import lzma
import sqlite3
import sys
from array import array
from typing import IO, Any


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
        for value in values:
            if isinstance(value, bytes):
                matrix = _int16_array(value)
                # from the last row to the first, so that the previous rows are still the original ones
                for i in range(len(matrix) - 1, width - 1, -1):
                    matrix[i] -= matrix[i - width]
                encoded.append({'int16': matrix.tolist()})
            else:
                encoded.append(value)
        return [_dumps(encoded)]
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
                matrix = array('h', value['int16'])
                for i in range(width, len(matrix)):
                    matrix[i] += matrix[i - width]
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
            header['tables'].append({'name': name, 'sql': sql, 'columns': columns, 'encodings': table_encodings})
            for i, column in enumerate(columns):
                lines.extend(encode([row[i] for row in rows], table_encodings.get(column)))
    finally:
        db.close()
    with lzma.open(path, 'wt', encoding='utf-8', preset=9 | lzma.PRESET_EXTREME) as f:
        for line in [_dumps(header), *lines]:
            f.write(line + '\n')


def read_package(path: str, db_path: str) -> None:
    """Create the database at db_path from a package"""
    db = sqlite3.connect(db_path)
    try:
        with lzma.open(path, 'rt', encoding='utf-8') as lines:
            header = json.loads(lines.readline())
            for table in header['tables']:
                db.execute(table['sql'])
                columns = [decode(lines, table['encodings'].get(column)) for column in table['columns']]
                placeholders = ', '.join('?' * len(columns))
                db.executemany(f'INSERT INTO {table["name"]} VALUES ({placeholders})', zip(*columns))
        db.commit()
    finally:
        db.close()
