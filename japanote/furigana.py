"""Furigana in Anki's format (e.g. '牛[ぎゅう]肉[にく]')

When the dictionary knows a word, its furigana come from JmdictFurigana. Otherwise, the kanji are
aligned with the kana based on their known readings (see align).
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator
from typing import Optional

from .kana import has_kanji, hiragana_to_katakana, katakana_to_hiragana

# a base text with its reading; both are equal for kana and other characters without furigana
Segment = tuple[str, str]
KanjiReadings = Callable[[str], list[str]]
# returns the segments known for a text and its reading, if any
KnownFurigana = Callable[[str, str], Optional[list[Segment]]]

DAKUTENS = {
    'か': 'が', 'き': 'ぎ', 'く': 'ぐ', 'け': 'げ', 'こ': 'ご',
    'さ': 'ざ', 'し': 'じ', 'す': 'ず', 'せ': 'ぜ', 'そ': 'ぞ',
    'た': 'だ', 'ち': 'ぢ', 'つ': 'づ', 'て': 'で', 'と': 'ど',
    'は': 'ばぱ', 'ひ': 'びぴ', 'ふ': 'ぶぷ', 'へ': 'べぺ', 'ほ': 'ぼぽ',
}


def normalize_reading(reading: str) -> str:
    """Normalize a reading from KANJIDIC2 (e.g. 'くぼ.む' → 'くぼ', '-カタ' → 'かた')"""
    # strip okurigana
    reading = reading.split('.')[0]
    # remove prefix/suffix marker
    reading = reading.replace('-', '')
    reading = katakana_to_hiragana(reading)
    # make ず and づ equivalent
    if reading.endswith('づ'):
        reading = reading[:-1] + 'ず'
    return reading


def compound_readings(readings: Iterable[str]) -> set[str]:
    """Readings that a kanji may take in a compound (gemination and rendaku)"""
    gemination = {reading[:-1] + 'っ' for reading in readings if reading}
    rendaku = {
        dakuten + reading[1:]
        for reading in readings
        if reading
        for dakuten in DAKUTENS.get(reading[0], '')
    }
    return gemination | rendaku


def kanji_readings_from_kanjidic(kanjidic_readings: list[str]) -> list[str]:
    """All the readings a kanji may take, from its readings in KANJIDIC2, most likely first"""
    readings = [normalize_reading(reading) for reading in kanjidic_readings]
    readings.extend(sorted(compound_readings(readings)))
    # remove duplicates while keeping order
    return list(dict.fromkeys(reading for reading in readings if reading))


def lengthen_vowel(s: str) -> str | None:
    last_kana = s[-1]
    if last_kana in 'かさたなはまやらわがざだばぱか゚ら゚ゃ': return s + 'あ'  # noqa: E701
    if last_kana in 'きしちにひみ𛀆りゐぎじぢびぴき゚り゚': return s + 'い'  # noqa: E701
    if last_kana in 'くすつぬふむゆる𛄟ぐずづぶぷく゚る゚ゅ': return s + 'う'  # noqa: E701
    if last_kana in 'けせてねへめ𛀁れゑげぜでべぺけ゚れ゚': return s + 'え'  # noqa: E701
    if last_kana in 'こそとのほもよろをごぞどぼぽこ゚ろ゚ょ': return s + 'お'  # noqa: E701
    return None


def align(text: str, reading: str, kanji_readings: KanjiReadings) -> list[Segment]:
    """Match the characters of text against the kana of reading

    For instance, for '牛肉' and 'ぎゅうにく', return [('牛', 'ぎゅう'), ('肉', 'にく')]. When no
    match is found, return the whole text with the whole reading.
    """
    return next(iter_alignments(text, reading, kanji_readings), [(text, reading)])


def iter_alignments(text: str, reading: str, kanji_readings: KanjiReadings) -> Iterator[list[Segment]]:
    """Yield the alignments of text with reading"""
    q: deque[tuple[list[Segment], str, str]] = deque([([], text, reading)])
    while q:
        prefix, text, reading = q.popleft()
        if not text and not reading:
            yield prefix
        if not text or not reading:
            continue
        # look up readings of the next character
        c = text[0]
        if c == '々' and prefix:
            readings = [prefix[-1][1], *compound_readings([prefix[-1][1]])]
        else:
            readings = kanji_readings(c) or [c]
        # add lengthened readings (lower priority)
        lengthened = [r for r in map(lengthen_vowel, readings) if r is not None]
        # remove duplicates while maintaining order
        candidates = list(dict.fromkeys(readings + lengthened))
        for candidate in candidates:
            if hiragana_to_katakana(reading[0]) == candidate or reading.startswith(candidate):
                q.append(([*prefix, (c, candidate)], text[1:], reading[len(candidate):]))


def format_furigana(segments: Iterable[Segment]) -> str:
    """Transform segments into Anki's furigana format

    For instance, for [('牛', 'ぎゅう'), ('肉', 'にく')], return '牛[ぎゅう]肉[にく]'.
    """
    parts = []
    last_was_kana = False
    for base, reading in segments:
        if base == reading:
            parts.append(base)
        else:
            # Anki's furigana apply to the whole run of text before the brackets
            if last_was_kana:
                parts.append(' ')
            parts.append(f'{base}[{reading}]')
        last_was_kana = base == reading
    return ''.join(parts)


def word_segments(
    text: str,
    reading: str,
    kanji_readings: KanjiReadings,
    known_furigana: KnownFurigana | None = None,
) -> list[Segment]:
    reading = katakana_to_hiragana(reading)
    if not has_kanji(text):
        return [(text, text)]
    if known_furigana is not None:
        segments = known_furigana(text, reading)
        if segments is not None:
            return segments
    return align(text, reading, kanji_readings)


def word_furigana(
    text: str,
    reading: str,
    kanji_readings: KanjiReadings,
    known_furigana: KnownFurigana | None = None,
) -> str:
    return format_furigana(word_segments(text, reading, kanji_readings, known_furigana))

