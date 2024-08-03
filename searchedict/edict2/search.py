import os.path
import re
from typing import Iterator, Optional, Tuple

from .furigana import furigana_from_kanji_kana

# default filenames
default_edict = os.path.join(os.path.dirname(__file__), 'edict2')
default_enamdict = os.path.join(os.path.dirname(__file__), 'enamdict')

# pre-compile regular expressions
edict_line_pattern = re.compile(r'(?m)^(\S*) (?:\[(\S*?)\] )?/(.*)/$')
common_marker = re.compile(r'\([^)]*\)')
gloss_pattern = re.compile(r'^(?:\(([^0-9]\S*)\) )?(?:\(([0-9]+)\) )?(.*)')


class Word:
    def __init__(self, writings: list[str], readings: list[str], glosses: str, edict_entry: str, edict_offset: Optional[int] = None) -> None:
        self.writings = writings
        self.readings = readings
        self.glosses = glosses
        self.edict_entry = edict_entry
        self.edict_offset = edict_offset

        self.kanji = self.writings[0]
        self.kana = self.readings[0] if self.readings else self.kanji

        self._furigana: Optional[str] = None

    def __repr__(self) -> str:
        return f'<{self.kanji}>'

    def get_sequence_number(self) -> Optional[str]:
        last_gloss = self.glosses.split('/')[-1]
        return last_gloss if last_gloss[:4] == 'EntL' else None

    def get_furigana(self) -> str:
        if self._furigana is None:
            kanji = self.kanji
            kana = self.kana
            self._furigana = furigana_from_kanji_kana(kanji, kana)
        return self._furigana

    def get_meanings(self) -> list[str]:
        # pre-parse glosses
        glosses = self.glosses.split('/')
        glosses = [
            gloss for gloss in glosses
            if gloss != '(P)' and not gloss.startswith('EntL')
        ]

        # regroup meanings
        meanings = []
        last_meaning = []
        for gloss in glosses:
            match = gloss_pattern.match(gloss)
            assert match is not None
            nature, meaning_id, meaning = match.groups()
            if meaning_id and last_meaning:
                meanings.append('; '.join(last_meaning))
                last_meaning = []
            last_meaning.append(meaning)
        meanings.append('; '.join(last_meaning))
        return meanings

    def get_meanings_html(self) -> str:
        meanings = self.get_meanings()
        if len(meanings) == 1:
            return meanings[0]
        items = ('<li>%s</li>' % meaning for meaning in meanings)
        list_ = '<ol>%s</ol>' % ''.join(items)
        return list_

    def get_type(self) -> int:
        """Return type mask for deinflections"""
        type_ = 1<<7
        if re.search(r'\bv1\b', self.glosses):
            type_ |= 1<<0
        if re.search(r'\bv5.\b', self.glosses):
            type_ |= 1<<1
        if re.search(r'\badj-i\b', self.glosses):
            type_ |= 1<<2
        if re.search(r'\bvk\b', self.glosses):
            type_ |= 1<<3
        if re.search(r'\bvs\b', self.glosses):
            type_ |= 1<<4
        return type_


class Edict:
    def __init__(self, filename: str = default_edict):
        self.words: dict[str, Word | list[Word]] = {}
        with open(filename) as f:
            lines = iter(f)
            next(lines)  # skip header
            for line in lines:
                match = edict_line_pattern.match(line)
                if not match:
                    continue

                # gather information for new word
                swritings, sreadings, glosses = match.groups()
                writings = common_marker.sub('', swritings).split(';')
                readings = common_marker.sub('', sreadings).split(';') if sreadings else []
                word = Word(writings, readings, glosses, line)

                # map writings and reading to word
                for key in writings + readings:
                    try:
                        entries = self.words[key]
                    except KeyError:
                        self.words[key] = word
                    else:
                        if isinstance(entries, list):
                            entries.append(word)
                        else:
                            self.words[key] = [entries, word]

    def search(self, word: str) -> Iterator[Word]:
        try:
            entries = self.words[word]
        except KeyError:
            return
        else:
            if isinstance(entries, list):
                yield from entries
            else:
                yield entries


edict = Edict(default_edict)
enamdict = Edict(default_enamdict)
