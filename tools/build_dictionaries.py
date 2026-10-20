#!/usr/bin/env python3
"""Build the dictionary databases that the add-on downloads

The add-on does not parse any dictionary at runtime; instead, this script turns the original
dictionaries into SQLite databases that are ready to query, and that are published as release
assets (see .github/workflows/dictionaries.yml).

Two databases are built, both with only the furigana that the add-on would not guess by itself:
- jmdict: JMdict (vocabulary), JmdictFurigana, KANJIDIC2 (kanji readings, for furigana), JLPT levels
  from Jonathan Waller's lists (with JMdict IDs from yomitan-jlpt-vocab), pitch accents from Kanjium;
- names: JMnedict (proper nouns), without the unclassified ones, JmnedictFurigana; it is optional and
  downloaded on first use.

Usage:
    build_dictionaries.py download SOURCES_DIR
    build_dictionaries.py build SOURCES_DIR OUTPUT_DIR BASE_URL
    build_dictionaries.py install OUTPUT_DIR DB_DIR  (decompress and index, as the add-on does)
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib
import json
import lzma
import os
import re
import shutil
import sqlite3
import sys
import types
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

# NOTE: must match FORMAT in japanote/dictionary.py
FORMAT = 1

EDRDG = 'http://ftp.edrdg.org/pub/Nihongo'
FURIGANA = 'https://github.com/Doublevil/JmdictFurigana/releases/latest/download'
JLPT = 'https://raw.githubusercontent.com/stephenmk/yomitan-jlpt-vocab/main/original_data'
KANJIUM = 'https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw'
SOURCES = {
    'JMdict_e.gz': f'{EDRDG}/JMdict_e.gz',
    'JMnedict.xml.gz': f'{EDRDG}/JMnedict.xml.gz',
    'kanjidic2.xml.gz': f'{EDRDG}/kanjidic2.xml.gz',
    'JmdictFurigana.json': f'{FURIGANA}/JmdictFurigana.json',
    'JmnedictFurigana.json': f'{FURIGANA}/JmnedictFurigana.json',
    'accents.txt': f'{KANJIUM}/accents.txt',
    **{
        f'jlpt-n{level}.csv': f'{JLPT}/n{level}.csv'
        for level in range(1, 6)
    },
}

ATTRIBUTION = (
    'JMdict, JMnedict and KANJIDIC2 are the property of the Electronic Dictionary Research and '
    "Development Group (https://www.edrdg.org/), and are used in conformance with the Group's "
    'licence (CC BY-SA 4.0). Furigana from JmdictFurigana (https://github.com/Doublevil/JmdictFurigana), '
    'CC BY-SA 4.0. JLPT levels from Jonathan Waller (http://www.tanos.co.uk/jlpt/), CC BY, with JMdict IDs '
    'from yomitan-jlpt-vocab (https://github.com/stephenmk/yomitan-jlpt-vocab), CC BY-SA 4.0. The pitch accent '
    'notation was provided by Uros O. through his free database Kanjium (https://github.com/mifunetoshiro/kanjium), '
    'CC BY-SA 4.0.'
)

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;
-- data is a JSON object (see parse_entry)
CREATE TABLE entry (id INTEGER PRIMARY KEY, rank INTEGER NOT NULL, data TEXT NOT NULL);
-- NOTE: the key table, indexing the entries, is built after download (see japanote/dictionary.py)
-- segments is a JSON list of [base, reading] pairs, or [kana] for kana-only segments
CREATE TABLE furigana (
    text TEXT NOT NULL, reading TEXT NOT NULL, segments TEXT NOT NULL, PRIMARY KEY (text, reading)
) WITHOUT ROWID;
-- readings is a JSON list of the on, kun and nanori readings, as in KANJIDIC2
CREATE TABLE kanji (literal TEXT PRIMARY KEY, readings TEXT NOT NULL) WITHOUT ROWID;
-- level is 1 for N1 to 5 for N5; these lists are unofficial
CREATE TABLE jlpt (entry INTEGER PRIMARY KEY, level INTEGER NOT NULL);
-- accents is the list of the positions of the accent, separated by commas (e.g. '0' for 東京 [とうきょう])
CREATE TABLE pitch (
    text TEXT NOT NULL, reading TEXT NOT NULL, accents TEXT NOT NULL, PRIMARY KEY (text, reading)
) WITHOUT ROWID;
"""

# priorities that make a word "common", like the (P) marker of EDICT
COMMON_PRIORITIES = {'news1', 'ichi1', 'spec1', 'spec2', 'gai1'}



def download(sources_dir: str) -> None:
    os.makedirs(sources_dir, exist_ok=True)
    for filename, url in SOURCES.items():
        print(f'Downloading {url}')
        path = os.path.join(sources_dir, filename)
        with urllib.request.urlopen(url) as response, open(path + '.part', 'wb') as f:
            shutil.copyfileobj(response, f)
        os.replace(path + '.part', path)


def read_xml(path: str) -> ET.Element:
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        data = f.read()
    # keep the names of the entities (e.g. "v5k") rather than their expansions (e.g. "Godan verb
    # with 'ku' ending"), as the original EDICT format did
    data = re.sub(r'&(?!(?:lt|gt|amp|quot|apos);)([\w-]+);', r'\1', data)
    return ET.fromstring(data)


def texts(element: ET.Element, tag: str) -> list[str]:
    return [child.text or '' for child in element.iter(tag)]


def compact(d: dict[str, Any]) -> dict[str, Any]:
    """Drop empty values, to keep the database small"""
    return {key: value for key, value in d.items() if value}


def parse_entry(entry: ET.Element) -> tuple[int, int, dict[str, Any]]:
    """Return the id, rank and data of a JMdict or JMnedict entry"""
    id_ = int(entry.findtext('ent_seq') or '')
    priorities: list[str] = []
    writings = []
    for k_ele in entry.iter('k_ele'):
        pri = texts(k_ele, 'ke_pri')
        priorities.extend(pri)
        writings.append(compact({
            't': k_ele.findtext('keb'),
            'i': texts(k_ele, 'ke_inf'),
            'p': bool(COMMON_PRIORITIES.intersection(pri)),
        }))
    readings = []
    for r_ele in entry.iter('r_ele'):
        pri = texts(r_ele, 're_pri')
        priorities.extend(pri)
        readings.append(compact({
            't': r_ele.findtext('reb'),
            'i': texts(r_ele, 're_inf'),
            'p': bool(COMMON_PRIORITIES.intersection(pri)),
            'restr': texts(r_ele, 're_restr'),
            'nokanji': r_ele.find('re_nokanji') is not None,
        }))
    senses = [
        compact({
            'pos': texts(sense, 'pos'),
            'g': texts(sense, 'gloss'),
            'misc': texts(sense, 'misc'),
            'field': texts(sense, 'field'),
            'info': texts(sense, 's_inf'),
            'stagk': texts(sense, 'stagk'),
            'stagr': texts(sense, 'stagr'),
        })
        for sense in entry.iter('sense')
    ]
    senses += [
        compact({'pos': texts(trans, 'name_type'), 'g': texts(trans, 'trans_det')})
        for trans in entry.iter('trans')
    ]

    # rank: lower is more common
    if COMMON_PRIORITIES.intersection(priorities):
        frequencies = [int(p[2:]) for p in priorities if p.startswith('nf')]
        rank = min(frequencies, default=49)
    elif priorities:
        rank = 50
    else:
        rank = 100

    return id_, rank, compact({'k': writings, 'r': readings, 's': senses})


def parse_furigana(path: str) -> Iterator[tuple[str, str, str]]:
    with open(path, encoding='utf-8-sig') as f:
        items = json.load(f)
    for item in items:
        segments = [[s['ruby'], s['rt']] if s.get('rt') else [s['ruby']] for s in item['furigana']]
        yield item['text'], item['reading'], json.dumps(segments, ensure_ascii=False, separators=(',', ':'))


def parse_kanjidic(path: str) -> Iterator[tuple[str, str]]:
    root = read_xml(path)
    for character in root.iter('character'):
        literal = character.findtext('literal') or ''
        readings = [
            reading.text or ''
            for reading in character.iter('reading')
            if reading.get('r_type') in ('ja_on', 'ja_kun')
        ]
        readings += texts(character, 'nanori')
        yield literal, json.dumps(readings, ensure_ascii=False, separators=(',', ':'))


def parse_jlpt(paths: dict[int, str]) -> Iterator[tuple[int, int]]:
    levels: dict[int, int] = {}
    for level, path in paths.items():
        with open(path, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                # a few entries (e.g. single kanji) have no matching JMdict entry
                if not row['jmdict_seq']:
                    continue
                # when a word is on several lists, keep the easiest level
                id_ = int(row['jmdict_seq'])
                levels[id_] = max(levels.get(id_, 0), level)
    yield from levels.items()


def parse_accents(path: str) -> Iterator[tuple[str, str, str]]:
    # for instance:
    # 東京\tとうきょう\t0
    # ああ\t\t0  (no reading for words in kana)
    # ２つ\tふたつ\t(副)0,(名)3  (accents by part of speech)
    pitches: dict[tuple[str, str], str] = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            text, reading, accents = line.rstrip('\n').split('\t')
            positions = dict.fromkeys(re.findall(r'[0-9]+', accents))
            pitches.setdefault((text, reading or text), ','.join(positions))
    for (text, reading), accents in pitches.items():
        yield text, reading, accents


def is_classified(data: dict[str, Any]) -> bool:
    """Whether a name has a type (e.g. surname, place), unlike the vaguest ones"""
    return any(pos != 'unclass' for sense in data['s'] for pos in sense.get('pos', []))


def load_module(name: str) -> types.ModuleType:
    """Import a module of the add-on, without the package's __init__, which needs Anki"""
    if 'japanote' not in sys.modules:
        package = types.ModuleType('japanote')
        package.__path__ = [os.path.join(os.path.dirname(__file__), '..', 'japanote')]
        sys.modules['japanote'] = package
    return importlib.import_module(f'japanote.{name}')


def furigana_differ(kanjidic: Iterable[tuple[str, str]]) -> Callable[[str, str, str], bool]:
    """Return whether the known furigana of a text differ from those the add-on would guess

    Most furigana can be guessed from the readings of the kanji (94% for JMdict, 97% for JMnedict),
    so they need not be stored.
    """
    furigana = load_module('furigana')
    readings = {
        literal: furigana.kanji_readings_from_kanjidic(json.loads(kanji_readings))
        for literal, kanji_readings in kanjidic
    }

    def differ(text: str, reading: str, segments: str) -> bool:
        known = [(s[0], s[-1]) for s in json.loads(segments)]
        guessed = furigana.word_segments(text, reading, lambda c: readings.get(c, []))
        return bool(furigana.format_furigana(guessed) != furigana.format_furigana(known))
    return differ


def build_database(  # noqa: PLR0913
    path: str,
    entries_path: str,
    furigana_path: str,
    tables: Mapping[str, Iterable[tuple[Any, ...]]],
    version: str,
    keep_entry: Callable[[dict[str, Any]], bool] | None = None,
    keep_furigana: Callable[[str, str, str], bool] | None = None,
) -> None:
    """Build a database of entries, with the rows of tables that are specific to it"""
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    root = read_xml(entries_path)
    for entry in root.iter('entry'):
        id_, rank, data = parse_entry(entry)
        if keep_entry is not None and not keep_entry(data):
            continue
        db.execute(
            'INSERT INTO entry VALUES (?, ?, ?)',
            (id_, rank, json.dumps(data, ensure_ascii=False, separators=(',', ':'))),
        )
    db.executemany(
        'INSERT OR IGNORE INTO furigana VALUES (?, ?, ?)',
        (row for row in parse_furigana(furigana_path) if keep_furigana is None or keep_furigana(*row)),
    )
    for table, rows in tables.items():
        for row in rows:
            db.execute(f'INSERT INTO {table} VALUES ({", ".join("?" * len(row))})', row)
    db.executemany('INSERT INTO meta VALUES (?, ?)', [
        ('format', str(FORMAT)),
        ('version', version),
        ('attribution', ATTRIBUTION),
    ])
    db.commit()
    db.execute('VACUUM')
    db.close()


def compress(path: str) -> tuple[str, int, str]:
    """Compress path with xz, and return the new path, its size and its SHA-256"""
    # xz makes the databases a third smaller than gzip, and Python can decompress it (lzma)
    compressed = path + '.xz'
    with open(path, 'rb') as src, lzma.open(compressed, 'wb', preset=9 | lzma.PRESET_EXTREME) as dst:
        shutil.copyfileobj(src, dst)
    digest = hashlib.sha256()
    with open(compressed, 'rb') as f:
        while chunk := f.read(1 << 16):
            digest.update(chunk)
    return compressed, os.path.getsize(compressed), digest.hexdigest()


def build(sources_dir: str, output_dir: str, base_url: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    version = datetime.now(timezone.utc).strftime('%Y%m%d')

    def source(filename: str) -> str:
        return os.path.join(sources_dir, filename)

    manifest: dict[str, Any] = {'format': FORMAT, 'version': version, 'dictionaries': {}}
    kanjidic = list(parse_kanjidic(source('kanjidic2.xml.gz')))
    jmdict_tables: dict[str, Iterable[tuple[Any, ...]]] = {
        'kanji': kanjidic,
        'jlpt': parse_jlpt({level: source(f'jlpt-n{level}.csv') for level in range(1, 6)}),
        'pitch': parse_accents(source('accents.txt')),
    }
    differ = furigana_differ(kanjidic)
    databases: list[tuple[str, str, str, Mapping[str, Iterable[tuple[Any, ...]]], Any]] = [
        ('jmdict', 'JMdict_e.gz', 'JmdictFurigana.json', jmdict_tables, None),
        ('names', 'JMnedict.xml.gz', 'JmnedictFurigana.json', {}, is_classified),
    ]
    for name, entries, furigana, tables, keep_entry in databases:
        print(f'Building {name}')
        path = os.path.join(output_dir, f'{name}-v{FORMAT}-{version}.sqlite')
        build_database(path, source(entries), source(furigana), tables, version, keep_entry, differ)
        compressed, size, sha256 = compress(path)
        os.remove(path)
        manifest['dictionaries'][name] = {
            'url': f'{base_url}/{os.path.basename(compressed)}',
            'size': size,
            'sha256': sha256,
        }
        print(f'  {compressed}: {size / 2**20:.1f} MiB')

    with open(os.path.join(output_dir, f'manifest-v{FORMAT}.json'), 'w') as f:
        json.dump(manifest, f, indent=4)


def install(output_dir: str, db_dir: str) -> None:
    """Decompress the built databases, and index them as the add-on does (for development and tests)"""
    dictionary = load_module('dictionary')
    os.makedirs(db_dir, exist_ok=True)
    for filename in os.listdir(output_dir):
        if filename.endswith('.sqlite.xz'):
            path = os.path.join(db_dir, filename.split('-')[0] + '.sqlite')
            if os.path.exists(path):
                os.remove(path)
            with lzma.open(os.path.join(output_dir, filename)) as src, open(path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            dictionary.create_keys(path)
            print(f'Installed {path}')


def main() -> None:
    command, *args = sys.argv[1:] or ['']
    if command == 'download' and len(args) == len(['SOURCES_DIR']):
        download(*args)
    elif command == 'build' and len(args) == len(['SOURCES_DIR', 'OUTPUT_DIR', 'BASE_URL']):
        sources_dir, output_dir, base_url = args
        build(sources_dir, output_dir, base_url.rstrip('/'))
    elif command == 'install' and len(args) == len(['OUTPUT_DIR', 'DB_DIR']):
        install(*args)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
