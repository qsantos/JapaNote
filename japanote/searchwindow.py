from typing import Optional

from aqt import mw
from aqt.qt import QMainWindow, Qt

from .collection import get_collection
from .model import add_notes, word_search
from .qt import QtGui, searchwindow
from .settingswindow import SettingsWindow
from .view import window_to_front


class SearchWindow(QMainWindow):
    instance = None

    @classmethod
    def open(cls, pattern: Optional[str] = None) -> None:
        if cls.instance is None:
            cls.instance = cls(pattern)
        else:
            window_to_front(cls.instance)

    def closeEvent(self, evt: QtGui.QCloseEvent) -> None:
        type(self).instance = None
        self.hide()
        evt.accept()

    def __init__(self, pattern: Optional[str] = None) -> None:
        QMainWindow.__init__(self)

        if pattern is None:
            col = get_collection()
            pattern = col.conf.get('japanote_pattern', '')

        self.form = searchwindow.Ui_MainWindow()
        self.form.setupUi(self)  # type: ignore[no-untyped-call]
        self.form.pattern.setText(pattern)
        self.form.resultTable.setModel(word_search)

        # events
        self.form.pattern.returnPressed.connect(self.update_search)
        self.form.searchButton.clicked.connect(self.update_search)
        self.form.addButton.clicked.connect(self.on_add_notes)
        self.form.settingsButton.clicked.connect(SettingsWindow.open)

        self.update_search()

        self.form.pattern.setClearButtonEnabled(True)

        self.show()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def update_search(self) -> None:
        # get settings
        pattern = self.form.pattern.text()
        # update results
        word_search.search(pattern)
        # save settings for persistence
        col = get_collection()
        col.conf['japanote_pattern'] = pattern

    def on_add_notes(self) -> None:
        rows = self.form.resultTable.selectionModel().selectedRows()
        words = [
            word_search.words[index.row()]
            for index in rows
        ]
        add_notes(words)
