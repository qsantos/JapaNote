import pytest

from japanote.dictionary import Dictionary
from japanote.furigana import align, format_furigana, normalize_reading


def test_normalize_reading() -> None:
    assert normalize_reading('くぼ.む') == 'くぼ'
    assert normalize_reading('クボ.ム') == 'くぼ'
    assert normalize_reading('もの-') == 'もの'
    assert normalize_reading('-カタ') == 'かた'


@pytest.mark.parametrize(('text', 'reading', 'expected'), [
    ('私', 'わたし', '私[わたし]'),
    ('牛肉', 'ぎゅうにく', '牛[ぎゅう]肉[にく]'),
    (
        '一二三四五六七八九十', 'いちにさんしごろくななはちきゅうじゅう',
        '一[いち]二[に]三[さん]四[し]五[ご]六[ろく]七[なな]八[はち]九[きゅう]十[じゅう]',
    ),
    ('等々', 'などなど', '等[など]々[など]'),
    ('人々', 'ひとびと', '人[ひと]々[びと]'),
    ('日帰り', 'ひがえり', '日[ひ]帰[がえ]り'),
    ('判官', 'はんがん', '判[はん]官[がん]'),
    ('贔屓', 'ひいき', '贔[ひい]屓[き]'),
    ('判官贔屓', 'はんがんびいき', '判[はん]官[がん]贔[びい]屓[き]'),
    ('メッタ刺し', 'めったざし', 'メッタ 刺[ざ]し'),
    ('文字', 'もじ', '文[も]字[じ]'),
    ('楔形文字', 'くさびがたもじ', '楔[くさび]形[がた]文[も]字[じ]'),
    # lengthened readings have a lower priority; otherwise, this could give:
    # 人[ひと]を 呪[のろ]わ ば[ばあ] 穴[な]二[ふた]つ
    ('人を呪わば穴二つ', 'ひとをのろわばあなふたつ', '人[ひと]を 呪[のろ]わば 穴[あな]二[ふた]つ'),
])
def test_align(jmdict: Dictionary, text: str, reading: str, expected: str) -> None:
    assert format_furigana(align(text, reading, jmdict.kanji_readings)) == expected


@pytest.mark.parametrize(('text', 'reading', 'expected'), [
    # not known by JmdictFurigana; one kanji has an irregular reading
    ('三途の川', 'さんずのかわ', '三[さん]途[ず]の 川[かわ]'),
    ('土饅頭', 'どまんじゅう', '土[ど]饅[まん]頭[じゅう]'),
    # the の of 身の代 is not written
    ('身代金', 'みのしろきん', '身[み]代[のしろ]金[きん]'),
    # these do not align kanji by kanji, but are known by JmdictFurigana
    ('塩っぱい', 'しょっぱい', '塩[しょ]っぱい'),
    ('義理のお兄さん', 'ぎりのおにいさん', '義[ぎ]理[り]のお 兄[にい]さん'),
    ('黒後家蜘蛛', 'くろごけぐも', '黒[くろ]後[ご]家[け]蜘蛛[ぐも]'),
    ('大晦日', 'おおみそか', '大[おお]晦日[みそか]'),
    ('甲斐がある', 'かいがある', '甲斐[かい]がある'),
    ('泊りがけ', 'とまりがけ', '泊[とま]りがけ'),
    ('踵を返す', 'きびすをかえす', '踵[きびす]を 返[かえ]す'),
    ('詰る', 'なじる', '詰[なじ]る'),
])
def test_word_furigana(jmdict: Dictionary, text: str, reading: str, expected: str) -> None:
    assert jmdict.furigana(text, reading) == expected

