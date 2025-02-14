import os.path
import re

default_kanjidic = os.path.join(os.path.dirname(__file__), 'kanjidic')


class Kanji:
    def __init__(self, character: str, readings: set[str], meanings: set[str]) -> None:
        self.character = character
        self.readings = readings
        self.meanings = meanings

    def __repr__(self) -> str:
        return f'.{self.character}.'


hiragana = [chr(i) for i in range(0x3040, 0x30A0)]
katakana = [chr(i) for i in range(0x30A0, 0x3100)]


def hiragana_to_katakana(s: str) -> str:
    return ''.join(katakana[hiragana.index(c)] if c in hiragana else c for c in s)


def katakana_to_hiragana(s: str) -> str:
    # NOTE: ignores ヷ ヸ ヹ ヺ
    return ''.join(hiragana[katakana.index(c)] if c in katakana else c for c in s)


assert hiragana_to_katakana('くぼ.む') == 'クボ.ム'
assert katakana_to_hiragana('クボ.ム') == 'くぼ.む'

dakutens = {
    'か': 'が', 'き': 'ぎ', 'く': 'ぐ', 'け': 'げ', 'こ': 'ご',
    'さ': 'ざ', 'し': 'じ', 'す': 'ず', 'せ': 'ぜ', 'そ': 'ぞ',
    'た': 'だ', 'ち': 'ぢ', 'つ': 'づ', 'て': 'で', 'と': 'ど',
    'は': 'ばぱ', 'ひ': 'びぴ', 'ふ': 'ぶぷ', 'へ': 'べぺ', 'ほ': 'ぼぽ',
}


def normalize_reading(reading: str) -> str:
    # strip okurigana (e.g. 'くぼ.む' → 'くぼ')
    reading = reading.split('.')[0] if '.' in reading else reading
    # remove prefix/suffix marker (e.g. 'もの-' → 'もの', '-かた' → 'かた')
    reading = reading.replace('-', '')
    # convert to hiragana (e.g. 'クボ' → 'くぼ')
    reading = katakana_to_hiragana(reading)
    # make ず and づ equivalent
    if reading.endswith('づ'):
        reading = reading[:-1] + 'ず'
    return reading


assert normalize_reading('くぼ.む') == 'くぼ'
assert normalize_reading('クボ.ム') == 'くぼ'
assert normalize_reading('もの-') == 'もの'
assert normalize_reading('-カタ') == 'かた'


def compound_readings(readings: set[str]) -> set[str]:
    gemination = {reading[:-1] + 'っ' for reading in readings}
    rendaku = {
        dakuten + reading[1:]
        for reading in readings
        for dakuten in dakutens.get(reading[0], set())
    }
    return gemination | rendaku


def load_kanjidic(filename: str = default_kanjidic) -> dict[str, Kanji]:
    with open(filename, mode='rb') as f:
        edict_data = f.read().decode('euc_jp')

    kanjidic = {}
    line_pattern = re.compile(r'(?m)^(.) (?:[0-9A-F]{4}) (?:(?:[A-Z]\S*) )*([^{]*?) (?:T[^{]*?)?((?:\{.*?\} )*\{.*?\})')
    meaning_pattern = re.compile(r'{(.*?)}')
    for character, readings, meanings in line_pattern.findall(edict_data):
        # gather kanji information
        meanings = meaning_pattern.findall(meanings)
        readings = {normalize_reading(reading) for reading in readings.split()}
        readings |= compound_readings(readings)
        kanji = Kanji(character, readings, meanings)

        # map character to kanji
        kanjidic[character] = kanji
    return kanjidic
