from aqt import mw
from aqt.qt import QApplication, Qt


def window_to_front(window):
    window.setWindowState(window.windowState() | Qt.WindowActive)
    window.activateWindow()
    window.raise_()


def set_combobox_from_config(combobox, elements, config_key):
    element = mw.col.conf.setdefault(config_key, elements[0])
    try:
        element_idx = elements.index(element)
    except ValueError:
        element_idx = 0
    combobox.setCurrentIndex(element_idx)


def immediate_redraw(widget):
    widget.update()
    app = QApplication.instance()
    app.processEvents()


def refresh_deckBrowser():
    mw.deckBrowser.web._domDone = True  # bypass Anki 2.1 weirdness
    mw.deckBrowser.refresh()
    mw.deckBrowser.web.update()
