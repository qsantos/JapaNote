from japanote.deinflect import Deinflector
from japanote.dictionary import Dictionary, search_words


def test_lookup(jmdict: Dictionary) -> None:
    word = jmdict.lookup('たべる')[0]
    assert (word.kanji, word.kana, word.id) == ('食べる', 'たべる', 'EntL1358280')
    assert word.furigana == '食[た]べる'
    assert word.meanings[0] == 'to eat'
    assert word.definition_html().startswith('<ol><li>to eat</li>')


def test_lookup_katakana(jmdict: Dictionary) -> None:
    assert any(word.kanji == '食べる' for word in jmdict.lookup('タベル'))


def test_lookup_prefers_looked_up_forms(jmdict: Dictionary) -> None:
    word = jmdict.lookup('にっぽん')[0]
    assert (word.kanji, word.kana) == ('日本', 'にっぽん')
    word = jmdict.lookup('にほん')[0]
    assert (word.kanji, word.kana) == ('日本', 'にほん')


def test_search_deinflects(jmdict: Dictionary, deinflector: Deinflector) -> None:
    assert [w.kanji for w in search_words(jmdict, '食べました', deinflector)] == ['食べる']


def test_search_romaji(jmdict: Dictionary, deinflector: Deinflector) -> None:
    assert search_words(jmdict, 'taberu', deinflector)[0].kanji == '食べる'


def test_search_common_first(jmdict: Dictionary, deinflector: Deinflector) -> None:
    assert search_words(jmdict, 'あんき', deinflector)[0].kanji == '暗記'


def test_names(names: Dictionary) -> None:
    words = search_words(names, 'とうきょう')
    assert any(w.kanji == '東京' and w.id.startswith('EntN') for w in words)
    assert all(w.meanings for w in words)
