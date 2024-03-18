from .furigana import match_from_kanji_kana
from .search import search_edict


def ruby_from_match(match):
    """Transform a kanji-kana match into HTML <ruby> tags

    For instance, for [(u'牛', u'ぎゅう'), (u'肉', u'にく')], it returns
    u'<ruby>牛<rt>ぎゅう</rt>肉<rt>にく</rt></ruby>'.
    """
    def _():
        ruby_open = False
        last_was_kana = False
        for kanji, kana in match:
            if kanji == kana:
                yield kana
            else:
                if last_was_kana and ruby_open:
                    yield u'</ruby>'
                    ruby_open = False
                if not ruby_open:
                    yield '<ruby>'
                    ruby_open = True
                yield u'{}<rt>{}</rt>'.format(kanji, kana)
            last_was_kana = kanji == kana
        if ruby_open:
            yield '</ruby>'
    return u''.join(_())


def ruby_from_kanji_kana(kanji, kana):
    matches = list(match_from_kanji_kana(kanji, kana))
    return ruby_from_match(matches[0])


def ruby_text(text):
    start = 0
    stop = len(text)
    ret = []
    while stop > start:
        try:
            word = next(search_edict(text[start:stop]))
        except StopIteration:
            stop -= 1
            continue
        ret.append(ruby_from_kanji_kana(word.kanji, word.kana))
        start = stop
        stop = len(text)
    return ''.join(ret)


def main():
    while True:
        try:
            line = input()
        except EOFError:
            break
        print(ruby_text(line))


if __name__ == '__main__':
    main()
