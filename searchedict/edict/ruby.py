from .furigana import match_from_kanji_kana


def ruby_from_match(match):
    """Transform a kanji-kana match into HTML <ruby> tags

    For instance, for [('牛', 'ぎゅう'), ('肉', 'にく')], it returns
    '<ruby>牛<rt>ぎゅう</rt>肉<rt>にく</rt></ruby>'.
    """
    def _():
        ruby_open = False
        last_was_kana = False
        for kanji, kana in match:
            if kanji == kana:
                yield kana
            else:
                if last_was_kana and ruby_open:
                    yield '</ruby>'
                    ruby_open = False
                if not ruby_open:
                    yield '<ruby>'
                    ruby_open = True
                yield '{}<rt>{}</rt>'.format(kanji, kana)
            last_was_kana = kanji == kana
        if ruby_open:
            yield '</ruby>'
    return ''.join(_())


def ruby_from_kanji_kana(kanji, kana):
    matches = list(match_from_kanji_kana(kanji, kana))
    return ruby_from_match(matches[0])
