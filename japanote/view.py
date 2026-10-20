from aqt.qt import Qt, QWidget


def window_to_front(window: QWidget) -> None:
    window.show()
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
    window.activateWindow()
    window.raise_()
