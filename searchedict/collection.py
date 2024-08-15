from aqt import Collection, mw


def get_collection() -> Collection:
    assert mw is not None
    col = mw.col
    assert col is not None
    return col
