"""Look up words in the dictionaries built by tools/build_dictionaries.py"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from html import escape
from typing import TYPE_CHECKING, Any

from . import romkan
from .furigana import (
    Segment,
    format_furigana,
    kanji_readings_from_kanjidic,
    reading_of,
    sentence_segments,
    word_furigana,
)
from .kana import normalize

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .deinflect import Deinflector

# NOTE: must match FORMAT in tools/build_dictionaries.py
FORMAT = 1


@dataclass
class Word:
    """What a note is made from"""
    kanji: str
    kana: str
    furigana: str
    meanings: list[str] = field(default_factory=list)
    # e.g. 'EntL1358280' for JMdict entries, or '' for words that are not in a dictionary
    id: str = ''
    # parts of speech (e.g. 'v1', 'n')
    pos: frozenset[str] = frozenset()
    # JLPT level (e.g. 3 for N3), from unofficial lists
    jlpt: int | None = None
    # marked as common in JMdict
    common: bool = False

    def __repr__(self) -> str:
        return f'<{self.kanji}>'

    def definition_html(self) -> str:
        if len(self.meanings) == 1:
            return escape(self.meanings[0], quote=False)
        if not self.meanings:
            return ''
        return '<ol>{}</ol>'.format(''.join(f'<li>{escape(meaning, quote=False)}</li>' for meaning in self.meanings))

    def get_type(self) -> int:
        """Return type mask for deinflections (see deinflect.py)"""
        type_ = 1 << 7
        for pos in self.pos:
            if pos == 'v1':
                type_ |= 1 << 0
            elif pos.startswith('v5'):
                type_ |= 1 << 1
            elif pos == 'adj-i':
                type_ |= 1 << 2
            elif pos == 'vk':
                type_ |= 1 << 3
            elif pos.startswith('vs'):
                type_ |= 1 << 4
        return type_


class Dictionary:
    def __init__(self, path: str, id_prefix: str, kanji_source: Dictionary | None = None) -> None:
        self.path = path
        self.id_prefix = id_prefix
        # the dictionary holding the kanji readings, used to align furigana
        self.kanji_source = kanji_source or self
        self._db: sqlite3.Connection | None = None
        self._kanji_readings: dict[str, list[str]] = {}

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True)
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def version(self) -> str:
        row = self.db.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
        return str(row[0])

    def kanji_readings(self, c: str) -> list[str]:
        try:
            return self._kanji_readings[c]
        except KeyError:
            pass
        row = self.db.execute('SELECT readings FROM kanji WHERE literal = ?', (c,)).fetchone()
        readings = kanji_readings_from_kanjidic(json.loads(row[0])) if row else []
        self._kanji_readings[c] = readings
        return readings

    def known_furigana(self, text: str, reading: str) -> list[Segment] | None:
        query = 'SELECT segments FROM furigana WHERE text = ? AND reading = ?'
        row = self.db.execute(query, (text, reading)).fetchone()
        if row is None:
            return None
        # kana segments have no separate reading
        return [(s[0], s[-1]) for s in json.loads(row[0])]

    def furigana(self, text: str, reading: str) -> str:
        return word_furigana(text, reading, self.kanji_source.kanji_readings, self.known_furigana)

    def lookup(self, key: str) -> list[Word]:
        """Words having key as a writing or as a reading, most common first"""
        key = normalize(key)
        query = """
            SELECT entry.id, entry.data FROM key JOIN entry ON entry.id = key.entry
            WHERE key.key = ? ORDER BY entry.rank, entry.id
        """
        return [self.make_word(id_, json.loads(data), key) for id_, data in self.db.execute(query, (key,))]

    def make_word(self, id_: int, data: dict[str, Any], key: str) -> Word:
        """Pick the writing and reading of an entry, preferring the ones that were looked up"""
        writings = [w['t'] for w in data.get('k', []) if 'sK' not in w.get('i', [])]
        kanji = next((w for w in writings if normalize(w) == key), writings[0] if writings else None)

        readings = [r for r in data['r'] if 'sk' not in r.get('i', [])] or data['r']
        if kanji is not None:
            readings = [
                r for r in readings
                if not r.get('nokanji') and kanji in r.get('restr', [kanji])
            ] or readings
        kana = next((r['t'] for r in readings if normalize(r['t']) == key), readings[0]['t'])
        if kanji is None:
            kanji = kana

        senses = [
            sense for sense in data.get('s', [])
            if kanji in sense.get('stagk', [kanji]) and kana in sense.get('stagr', [kana])
        ] or data.get('s', [])
        return Word(
            kanji=kanji,
            kana=kana,
            furigana=self.furigana(kanji, kana),
            meanings=['; '.join(sense.get('g', [])) for sense in senses],
            id=f'{self.id_prefix}{id_}',
            pos=frozenset(pos for sense in data.get('s', []) for pos in sense.get('pos', [])),
            jlpt=self.jlpt(id_),
            common=any(form.get('p') for form in data.get('k', []) + data['r']),
        )

    def jlpt(self, id_: int) -> int | None:
        row = self.db.execute('SELECT level FROM jlpt WHERE entry = ?', (id_,)).fetchone()
        return int(row[0]) if row else None


def search_words(dictionary: Dictionary, text: str, deinflector: Deinflector | None = None) -> list[Word]:
    """Words matching text, including its inflected forms when a deinflector is given"""
    text = romkan.to_hiragana(text.strip())  # type: ignore[no-untyped-call]
    if deinflector is None:
        return dictionary.lookup(text)
    words: dict[str, Word] = {}
    # the exact form comes first, then the deinflected ones
    candidates = dict.fromkeys(deinflector(text))
    for candidate in candidates:
        for word in dictionary.lookup(candidate.word):
            if word.get_type() & candidate.type_ and word.id not in words:
                words[word.id] = word
    return list(words.values())


def sentence_word(
    dictionary: Dictionary,
    text: str,
    tokens: Iterable[tuple[str, str | None]],
) -> Word:
    """A Word for text that is not in the dictionary, from its tokens (see analyzer.py)"""
    segments = sentence_segments(tokens, dictionary.kanji_readings, dictionary.known_furigana)
    return Word(kanji=text, kana=reading_of(segments), furigana=format_furigana(segments))
