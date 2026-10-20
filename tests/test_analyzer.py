from japanote.dictionary import Dictionary


def test_tokenize(jmdict: Dictionary) -> None:
    # same as Janome
    assert jmdict.analyzer.tokenize('今日は大晦日なので、早く帰りました。') == [
        ('今日', 'キョウ'), ('は', 'ハ'), ('大晦日', 'オオミソカ'), ('な', 'ナ'), ('ので', 'ノデ'), ('、', '、'),
        ('早く', 'ハヤク'), ('帰り', 'カエリ'), ('まし', 'マシ'), ('た', 'タ'), ('。', '。'),
    ]


def test_unknown_words(jmdict: Dictionary) -> None:
    # unknown words are grouped by category, and have no reading
    assert jmdict.analyzer.tokenize('ジャパノートです') == [('ジャパノート', None), ('です', 'デス')]
    assert jmdict.analyzer.tokenize('XYZ123です') == [('XYZ', None), ('123', None), ('です', 'デス')]
    assert jmdict.analyzer.tokenize('') == []
