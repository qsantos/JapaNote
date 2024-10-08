from collections import deque
from typing import Iterator

from .kanji import load_kanjidic

kanjidic = None


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
    q = deque([([], kanji, kana)])
    while q:
        match_prefix, kanji, kana = q.popleft()
        if not kanji and not kana:
            yield match_prefix
        if not kanji or not kana:
            continue
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
        for reading in readings:
            if kana.startswith(reading):
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


assert furigana_from_kanji_kana('私', 'わたし') == '私[わたし]'
assert furigana_from_kanji_kana('牛肉', 'ぎゅうにく') == '牛[ぎゅう]肉[にく]'
assert furigana_from_kanji_kana('一二三四五六七八九十', 'いちにさんしごろくななはちきゅうじゅう') == '一[いち]二[に]三[さん]四[し]五[ご]六[ろく]七[なな]八[はち]九[きゅう]十[じゅう]'
assert furigana_from_kanji_kana('等々', 'などなど') == '等[など]々[など]'
assert furigana_from_kanji_kana('日帰り', 'ひがえり') == '日[ひ]帰[がえ]り'
