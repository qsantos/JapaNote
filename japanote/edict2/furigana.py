from collections import deque
from typing import Iterator, Optional, Deque

from .kanji import load_kanjidic

kanjidic = None


def hiragana_to_katakana(c: str) -> str:
    return chr(ord(c) - 0x3041 + 0x30a1)


assert hiragana_to_katakana('あ') == 'ア'
assert hiragana_to_katakana('っ') == 'ッ'


def lengthen_vowel(s: str) -> Optional[str]:
    last_kana = s[-1]
    if last_kana in 'かさたなはまやらわがざだばぱか゚ら゚ゃ': return s + 'あ'
    if last_kana in 'きしちにひみ𛀆りゐぎじぢびぴき゚り゚': return s + 'い'
    if last_kana in 'くすつぬふむゆる𛄟ぐずづぶぷく゚る゚ゅ': return s + 'う'
    if last_kana in 'けせてねへめ𛀁れゑげぜでべぺけ゚れ゚': return s + 'え'
    if last_kana in 'こそとのほもよろをごぞどぼぽこ゚ろ゚ょ': return s + 'お'
    return None


def furigana_from_kanji_kana(kanji: str, kana: str) -> str:
    matches = list(match_from_kanji_kana(kanji, kana))
    return furigana_from_match(matches[0])


def match_from_kanji_kana(kanji: str, kana: str) -> Iterator[list[tuple[str, str]]]:
    """Match kanji against kana

    Return a generator that yields all possible matches of kanji with the kana
    based on their known readings. For instance, for '牛肉' and 'ぎゅうにく',
    it yields the single match [('牛', 'ぎゅう'), ('肉', 'にく')].
    """
    global kanjidic
    if kanjidic is None:
        kanjidic = load_kanjidic()

    default = [(kanji, kana)]
    q: Deque[tuple[list[tuple[str, str]], str, str]] = deque([([], kanji, kana)])
    while q:
        match_prefix, kanji, kana = q.popleft()
        # skip not-kanji
        if not kanji and not kana:
            yield match_prefix
        if not kanji or not kana:
            continue
        # look up kanji readings
        c = kanji[0]
        if c == '々' and match_prefix:
            readings = [match_prefix[-1][1]]  # TODO: dakuten
        else:
            try:
                kanjiinfo = kanjidic[c]
            except KeyError:
                readings = [c]
            else:
                readings = kanjiinfo.readings
        # add lengthened readings (lower priority)
        lengthened_readings = []
        for reading in readings:
            lengthened = lengthen_vowel(reading)
            if lengthened is not None:
                lengthened_readings.append(lengthened)
        readings.extend(lengthened_readings)
        # remove duplicates while maintaining order
        readings = list(dict.fromkeys(readings))
        # recurse
        for reading in readings:
            if hiragana_to_katakana(kana[0]) == reading or kana.startswith(reading):
                new_prefixes = match_prefix + [(c, reading)]
                new_kanji = kanji[1:]
                new_kana = kana[len(reading):]
                new_element = (new_prefixes, new_kanji, new_kana)
                q.append(new_element)
    yield default


def furigana_from_match(match: list[tuple[str, str]]) -> str:
    """Transform a kanji-kana match into Anki-compatible furigana

    For instance, for [('牛', 'ぎゅう'), ('肉', 'にく')], it returns
    '牛[ぎゅう]肉[にく]'.
    """
    def _() -> Iterator[str]:
        last_was_kana = False
        for kanji, kana in match:
            if kanji == kana:
                yield kana
            else:
                if last_was_kana:
                    yield ' '
                yield f'{kanji}[{kana}]'
            last_was_kana = kanji == kana
    return ''.join(_())


def _test(kanji: str, kana: str, expected: str):
    """Test furigana_from_kanji_kana() against expected result"""
    furigana = furigana_from_kanji_kana(kanji, kana)
    if furigana != expected:
        print(f'ERROR: furigana_from_kanji_kana(repr({kanji}), repr({kana}) returns the wrong result')
        print(f'Output:   {repr(furigana)}')
        print(f'Expected: {repr(expected)}')
        raise AssertionError


_test('私', 'わたし', '私[わたし]')
_test('牛肉', 'ぎゅうにく', '牛[ぎゅう]肉[にく]')
_test('一二三四五六七八九十', 'いちにさんしごろくななはちきゅうじゅう', '一[いち]二[に]三[さん]四[し]五[ご]六[ろく]七[なな]八[はち]九[きゅう]十[じゅう]')
_test('等々', 'などなど', '等[など]々[など]')
_test('日帰り', 'ひがえり', '日[ひ]帰[がえ]り')
_test('判官', 'はんがん', '判[はん]官[がん]')
_test('贔屓', 'ひいき', '贔[ひい]屓[き]')
_test('判官贔屓', 'はんがんびいき', '判[はん]官[がん]贔[びい]屓[き]')
_test('メッタ刺し', 'めったざし', 'メッタ 刺[ざ]し')
_test('文字', 'もじ', '文[も]字[じ]')
_test('楔形文字', 'くさびがたもじ', '楔[くさび]形[がた]文[も]字[じ]')
