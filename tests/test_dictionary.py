import sqlite3

import pytest

from japanote.deinflect import Deinflector
from japanote.dictionary import Dictionary, Example, Kanji, kanji_details_html, search_words


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


def test_search_inflection(jmdict: Dictionary, deinflector: Deinflector) -> None:
    word = search_words(jmdict, '食べさせられた', deinflector)[0]
    assert word.label() == '食べる, from 食べさせられた (causative, potential or passive, past)'
    word = search_words(jmdict, 'たべる', deinflector)[0]
    assert (word.label(), word.inflection) == ('食べる', '')


def test_search_romaji(jmdict: Dictionary, deinflector: Deinflector) -> None:
    assert search_words(jmdict, 'taberu', deinflector)[0].kanji == '食べる'


def test_search_common_first(jmdict: Dictionary, deinflector: Deinflector) -> None:
    assert search_words(jmdict, 'あんき', deinflector)[0].kanji == '暗記'


def test_names(names: Dictionary) -> None:
    words = search_words(names, 'とうきょう')
    assert any(w.kanji == '東京' and w.id.startswith('EntN') for w in words)
    assert all(w.meanings for w in words)



def test_tags(jmdict: Dictionary) -> None:
    word = jmdict.lookup('たべる')[0]
    assert word.jlpt == 5
    assert word.common
    word = jmdict.lookup('しんかんせん')[0]
    assert word.jlpt == 2
    word = jmdict.lookup('にわかあめ')[0]
    assert word.jlpt is None
    assert not word.common


def test_furigana_with_katakana_reading(names: Dictionary) -> None:
    assert names.furigana('爪哇島', 'ジャワとう') == '爪哇[ジャワ]島[とう]'


def test_example(jmdict: Dictionary) -> None:
    try:
        jmdict.db.execute('SELECT 1 FROM example')
    except sqlite3.OperationalError:
        pytest.skip('dictionary built before the examples')
    word = jmdict.lookup('あんき')[0]
    example = jmdict.example(word.id)
    assert example is not None
    assert example.form in example.japanese
    assert example.english
    assert jmdict.example('EntN5711355') is None


def test_example_html() -> None:
    example = Example('この詩を暗記しましょう。', "Let's learn this poem by heart.", '暗記')
    assert example.html() == "この詩を<b>暗記</b>しましょう。<br>Let's learn this poem by heart."
    # the form is not always in the sentence as is
    assert Example('<a>', 'b & c', 'x').html() == '&lt;a&gt;<br>b &amp; c'
    # as edited in the preview
    assert Example('', '', '暗記').html() == ''
    assert Example('', 'memorization', '').html() == 'memorization'
    assert Example('暗記した。', '', '').html() == '暗記した。'


def test_kanji(jmdict: Dictionary) -> None:
    try:
        jmdict.db.execute('SELECT info FROM kanji')
    except sqlite3.OperationalError:
        pytest.skip('dictionary built before the details of the kanji')
    details = jmdict.kanji('暗記した暗')
    assert [kanji.literal for kanji in details] == ['暗', '記']
    assert 'darkness' in details[0].meanings
    assert 'アン' in details[0].on
    assert 'くら.い' in details[0].kun


def test_kanji_text() -> None:
    kanji = Kanji('暗', ['darkness', 'shade'], ['アン'], ['くら.い', 'くら.む'])
    assert kanji.text() == '暗 darkness, shade (アン; くら.い, くら.む)'
    assert Kanji('々', ['repetition'], [], []).text() == '々 repetition'
    assert kanji_details_html([kanji.text(), '記 <scribe>']) == (
        '<b>暗</b> darkness, shade (アン; くら.い, くら.む)<br><b>記</b> &lt;scribe&gt;'
    )
