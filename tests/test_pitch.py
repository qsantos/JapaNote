import pytest

from japanote.dictionary import Dictionary
from japanote.pitch import pitch_html, split_morae

HIGH = '<span style="border-top:1px solid">'
HIGH_DROP = '<span style="border-top:1px solid;border-right:1px solid">'


def test_split_morae() -> None:
    assert split_morae('きょうと') == ['きょ', 'う', 'と']
    assert split_morae('シャツ') == ['シャ', 'ツ']


@pytest.mark.parametrize(('kana', 'accent', 'expected'), [
    # heiban: low, then high without drop
    ('はし', 0, f'は{HIGH}し</span>'),
    # atamadaka: high, then low
    ('はし', 1, f'{HIGH_DROP}は</span>し'),
    # odaka: low, then high until the end, then drop
    ('はし', 2, f'は{HIGH_DROP}し</span>'),
    # nakadaka
    ('たべる', 2, f'た{HIGH_DROP}べ</span>る'),
    ('とうきょう', 0, f'と{HIGH}うきょう</span>'),
])
def test_pitch_html(kana: str, accent: int, expected: str) -> None:
    assert pitch_html(kana, accent) == expected


def test_lookup(jmdict: Dictionary) -> None:
    assert jmdict.lookup('とうきょう')[0].pitch == [0]
    assert jmdict.lookup('たべる')[0].pitch == [2]
    assert [w.pitch for w in jmdict.lookup('はし') if w.kanji == '箸'] == [[1]]
