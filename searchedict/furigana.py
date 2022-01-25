import re

pattern = re.compile(r'([^\s[]+)\[([^]]+)\]|(\S+)')


def kana(s: str) -> str:
    return ''.join(
        furigana or kana
        for kanji, furigana, kana in pattern.findall(s)
    )


def kanji(s: str) -> str:
    return ''.join(
        kanji or kana
        for kanji, furigana, kana in pattern.findall(s)
    )


def ruby(s: str) -> str:
    return '<ruby>' + ''.join(
        f'{kanji or kana}<rp>(</rp><rt>{furigana}</rt><rp>)</rp>'
        for kanji, furigana, kana in pattern.findall(s)
    ) + '</ruby>'


# tests
furigana = '私[わたし]は　日本語[にほんご]を 勉[べん]強[きょう]しています。'
assert kana(furigana) == 'わたしはにほんごをべんきょうしています。'
assert kanji(furigana) == '私は日本語を勉強しています。'
assert re.sub(r'<.*?>', '', ruby(furigana)) == '私(わたし)は()日本語(にほんご)を()勉(べん)強(きょう)しています。()'
