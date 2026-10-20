import re

# NOTE: ゕ and ゖ (0x3095, 0x3096) are the last hiragana with a katakana counterpart at +0x60
_HIRAGANA = re.compile('[ぁ-ゖ]')
_KATAKANA = re.compile('[ァ-ヶ]')
# CJK Unified Ideographs, Extension A, Compatibility Ideographs, and the iteration marks 々 and 〆
_KANJI = re.compile('[㐀-䶿一-鿿豈-﫿々〆ヶ]')


def hiragana_to_katakana(s: str) -> str:
    return _HIRAGANA.sub(lambda m: chr(ord(m.group()) + 0x60), s)


def katakana_to_hiragana(s: str) -> str:
    # NOTE: must match tools/build_dictionaries.py
    return _KATAKANA.sub(lambda m: chr(ord(m.group()) - 0x60), s)


def has_kanji(s: str) -> bool:
    return _KANJI.search(s) is not None


def normalize(key: str) -> str:
    """Normalize a writing or reading for lookup (see tools/build_dictionaries.py)"""
    return katakana_to_hiragana(key)
