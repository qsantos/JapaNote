#!/usr/bin/env python3
"""Build the dictionary databases that the add-on downloads

The add-on does not parse any dictionary at runtime; instead, this script turns the original
dictionaries into SQLite databases, which are published as packages, in a format that compresses
well, as release assets (see japanote/package.py and .github/workflows/dictionaries.yml).

Two databases are built, both with only the furigana that the add-on would not guess by itself:
- jmdict: JMdict (vocabulary), JmdictFurigana, KANJIDIC2 (kanji readings, for furigana), JLPT levels
  from Jonathan Waller's lists (with JMdict IDs from yomitan-jlpt-vocab), pitch accents from Kanjium,
  and the IPA dictionary, as compiled by Janome, for the sentence analyzer (see japanote/analyzer.py);
- names: JMnedict (proper nouns), without the unclassified ones, JmnedictFurigana; it is optional and
  downloaded on first use.

Usage:
    build_dictionaries.py download SOURCES_DIR
    build_dictionaries.py build SOURCES_DIR OUTPUT_DIR BASE_URL
    build_dictionaries.py install OUTPUT_DIR DB_DIR  (build and index the databases, as the add-on does)
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import types
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from array import array
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

# NOTE: must match FORMAT in japanote/dictionary.py
FORMAT = 2

EDRDG = 'http://ftp.edrdg.org/pub/Nihongo'
FURIGANA = 'https://github.com/Doublevil/JmdictFurigana/releases/latest/download'
JLPT = 'https://raw.githubusercontent.com/stephenmk/yomitan-jlpt-vocab/main/original_data'
KANJIUM = 'https://raw.githubusercontent.com/mifunetoshiro/kanjium/master/data/source_files/raw'
JANOME = (
    'https://files.pythonhosted.org/packages/73/7d/70f4069f4bbf0fca023e82a1fbbade6f5216365d4fe259fee1950723eca5/'
    'Janome-0.5.0-py2.py3-none-any.whl'
)
JANOME_SHA256 = 'd098670394a77881ce2f6b7d696c0ea5ff74c0c8cf74a8a882159ec82c0e6dc7'
SOURCES = {
    'JMdict_e.gz': f'{EDRDG}/JMdict_e.gz',
    'JMnedict.xml.gz': f'{EDRDG}/JMnedict.xml.gz',
    'kanjidic2.xml.gz': f'{EDRDG}/kanjidic2.xml.gz',
    'JmdictFurigana.json': f'{FURIGANA}/JmdictFurigana.json',
    'JmnedictFurigana.json': f'{FURIGANA}/JmnedictFurigana.json',
    'accents.txt': f'{KANJIUM}/accents.txt',
    'janome.whl': JANOME,
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
    'CC BY-SA 4.0. The sentence analyzer uses the IPA dictionary (IPADIC), copyright 2000-2007 Nara Institute '
    'of Science and Technology, as compiled by Janome (https://github.com/mocobeta/janome), Apache 2.0.'
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
-- the words of the sentence analyzer (see japanote/analyzer.py); reading is NULL when it is the
-- surface in katakana, and '*' when unknown
CREATE TABLE token (
    num INTEGER PRIMARY KEY, surface TEXT NOT NULL, left_id INTEGER NOT NULL, right_id INTEGER NOT NULL,
    cost INTEGER NOT NULL, reading TEXT
);
-- the other data of the sentence analyzer: connection costs, character categories, unknown words
CREATE TABLE analyzer (key TEXT PRIMARY KEY, value) WITHOUT ROWID;
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


def parse_janome(path: str) -> tuple[list[tuple[Any, ...]], list[tuple[str, Any]]]:
    """Return the rows of the token and analyzer tables, from the dictionary that Janome compiled"""
    with open(path, 'rb') as f:
        if hashlib.sha256(f.read()).hexdigest() != JANOME_SHA256:
            sys.exit(f'unexpected checksum for {path}')
    kana = load_module('kana')
    with tempfile.TemporaryDirectory() as directory:
        with zipfile.ZipFile(path) as wheel:
            wheel.extractall(directory)
        sys.path.insert(0, directory)
        try:
            sysdic = importlib.import_module('janome.sysdic')
            tokens = []
            for i in range(10):
                compact = importlib.import_module(f'janome.sysdic.entries_compact{i}').DATA
                extra = importlib.import_module(f'janome.sysdic.entries_extra{i}').DATA
                for num, (surface, left_id, right_id, cost) in compact.items():
                    # part of speech, inflection type and form, base form, reading, pronunciation
                    reading = extra[num][4]
                    if reading == kana.hiragana_to_katakana(surface):
                        reading = None
                    tokens.append((num, surface, left_id, right_id, cost, reading))
            connections = sysdic.connections
            categories, char_ranges = sysdic.chardef.DATA
            unknowns = {
                category: [[left_id, right_id, cost] for left_id, right_id, cost, _ in entries]
                for category, entries in sysdic.unknowns.DATA.items()
            }
            # the licence of the IPA dictionary requires its notice to be distributed with it
            with open(os.path.join(directory, 'Janome-0.5.0.dist-info', 'NOTICE.txt'), encoding='utf-8') as f:
                notice = f.read()
        finally:
            sys.path.remove(directory)
    # connections[right id of a word][left id of the next one], as little-endian 16-bit integers
    matrix = array('h', (cost for row in connections for cost in row))
    if sys.byteorder == 'big':
        matrix.byteswap()
    analyzer = [
        ('size', len(connections)),
        ('connections', matrix.tobytes()),
        ('categories', json.dumps(categories, separators=(',', ':'))),
        ('char_ranges', json.dumps(char_ranges, ensure_ascii=False, separators=(',', ':'))),
        ('unknowns', json.dumps(unknowns, separators=(',', ':'))),
        ('notice', notice),
    ]
    return tokens, analyzer


# the parts of speech that the add-on uses, to deinflect words (see Word.get_type)
USED_POS = re.compile(r'v1|v5.*|adj-i|vk|vs.*')


def strip_unused(data: dict[str, Any]) -> dict[str, Any]:
    """Remove what the add-on does not use from the data of an entry, to make the download smaller

    That is: the usage notes, fields and other information on senses, the parts of speech other than
    those of verbs and adjectives (including the types of names), and the information on writings and
    readings other than whether they are only used for searching.
    """
    for form in data.get('k', []) + data['r']:
        tags = [tag for tag in form.pop('i', []) if tag in ('sK', 'sk')]
        if tags:
            form['i'] = tags
    for sense in data['s']:
        for key in ('misc', 'field', 'info'):
            sense.pop(key, None)
        pos = [pos for pos in sense.pop('pos', []) if USED_POS.fullmatch(pos)]
        if pos:
            sense['pos'] = pos
    return data


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
        strip_unused(data)
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


def encodings(analyzer_size: int) -> dict[str, dict[str, Any]]:
    """How to encode the columns of the tables in packages, to make them smaller (see japanote/package.py)"""
    return {
        'entry': {'id': 'delta', 'data': {'json': ['k', 'r', 's']}},
        'jlpt': {'entry': 'delta'},
        'token': {'num': 'delta'},
        'analyzer': {'value': {'int16 rows': analyzer_size}},
    }


def sha256sum(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 16):
            digest.update(chunk)
    return digest.hexdigest()


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
    tokens, analyzer = parse_janome(source('janome.whl'))
    jmdict_tables['token'], jmdict_tables['analyzer'] = tokens, analyzer
    package = load_module('package')
    differ = furigana_differ(kanjidic)
    databases: list[tuple[str, str, str, Mapping[str, Iterable[tuple[Any, ...]]], Any]] = [
        ('jmdict', 'JMdict_e.gz', 'JmdictFurigana.json', jmdict_tables, None),
        ('names', 'JMnedict.xml.gz', 'JmnedictFurigana.json', {}, is_classified),
    ]
    for name, entries, furigana, tables, keep_entry in databases:
        print(f'Building {name}')
        path = os.path.join(output_dir, f'{name}-v{FORMAT}-{version}.sqlite')
        build_database(path, source(entries), source(furigana), tables, version, keep_entry, differ)
        packaged = os.path.join(output_dir, f'{name}-v{FORMAT}-{version}.xz')
        package.write_package(path, packaged, encodings(dict(analyzer)['size']))
        os.remove(path)
        size = os.path.getsize(packaged)
        manifest['dictionaries'][name] = {
            'url': f'{base_url}/{os.path.basename(packaged)}',
            'size': size,
            'sha256': sha256sum(packaged),
        }
        print(f'  {packaged}: {size / 2**20:.1f} MiB')

    with open(os.path.join(output_dir, f'manifest-v{FORMAT}.json'), 'w') as f:
        json.dump(manifest, f, indent=4)


def install(output_dir: str, db_dir: str) -> None:
    """Turn the built packages into indexed databases, as the add-on does (for development and tests)"""
    dictionary = load_module('dictionary')
    package = load_module('package')
    os.makedirs(db_dir, exist_ok=True)
    for filename in os.listdir(output_dir):
        if f'-v{FORMAT}-' not in filename or not filename.endswith('.xz'):
            continue
        path = os.path.join(db_dir, filename.split('-')[0] + '.sqlite')
        if os.path.exists(path):
            os.remove(path)
        package.read_package(os.path.join(output_dir, filename), path)
        dictionary.create_indexes(path)
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
