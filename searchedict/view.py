from aqt import mw
from aqt.qt import QApplication, QComboBox, Qt, QWidget

from .model import get_collection


def window_to_front(window: QWidget) -> None:
    window.setWindowState(window.windowState() | Qt.WindowActive)
    window.activateWindow()
    window.raise_()


def set_combobox_from_config(combobox: QComboBox, elements: list[str], config_key: str) -> None:
    col = get_collection()
    element = col.conf.setdefault(config_key, elements[0])
    try:
        element_idx = elements.index(element)
    except ValueError:
        element_idx = 0
    combobox.setCurrentIndex(element_idx)


def immediate_redraw(widget: QWidget) -> None:
    widget.update()
    app = QApplication.instance()
    assert app is not None
    app.processEvents()


def refresh_deckBrowser() -> None:
    mw.deckBrowser.web._domDone = True  # bypass Anki 2.1 weirdness
    mw.deckBrowser.refresh()
    mw.deckBrowser.web.update()
