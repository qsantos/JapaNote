from __future__ import annotations

import pytest

from japanote.wikipedia import looks_like_term, parse_reading


@pytest.mark.parametrize(('title', 'extract', 'reading'), [
    ('機械学習', '機械学習（きかいがくしゅう、英: machine learning）とは、…', 'きかいがくしゅう'),
    ('量子コンピュータ', '量子コンピュータ （りょうしコンピュータ、英: …', 'りょうしコンピュータ'),
    ('ハッシュ関数', 'ハッシュ関数 (ハッシュかんすう、英語: hash function) あるいは…', 'ハッシュかんすう'),
    ('東京', '東京（とうきょう）は、…', 'とうきょう'),
    ('微分幾何学', '数学における微分幾何学（びぶんきかがく、ドイツ語: …', 'びぶんきかがく'),
    # no reading
    ('スクラム', 'スクラム（英: scrum）は、…', None),
    ('スクラム', 'スクラムは、…', None),
])
def test_parse_reading(title: str, extract: str, reading: str | None) -> None:
    assert parse_reading(title, extract) == reading


def test_looks_like_term() -> None:
    assert looks_like_term('形態素解析')
    assert not looks_like_term('猫が好きだと言った。')
    assert not looks_like_term('猫が好き、犬も')
