from __future__ import annotations

from typing import Any

from aqt.qt import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QPushButton,
    Qt,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .model import WordSearchModel, add_notes
from .settingswindow import SettingsWindow
from .view import window_to_front


class SearchWindow(QMainWindow):
    instance: SearchWindow | None = None

    @classmethod
    def open(cls, text: str, names: bool = False) -> None:
        if cls.instance is None:
            cls.instance = cls()
        cls.instance.search(text, names)
        window_to_front(cls.instance)

    def __init__(self) -> None:
        QMainWindow.__init__(self)
        self.setWindowTitle('JapaNote: select a word')
        self.resize(900, 450)
        self.model = WordSearchModel()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top = QHBoxLayout()
        layout.addLayout(top)
        self.pattern = QLineEdit()
        self.pattern.setClearButtonEnabled(True)
        self.pattern.returnPressed.connect(self.update_search)
        top.addWidget(self.pattern)
        search_button = QPushButton('Search')
        search_button.clicked.connect(self.update_search)
        top.addWidget(search_button)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        add_button = QPushButton('Add selected')
        add_button.setDefault(True)
        add_button.clicked.connect(self.on_add)
        bottom.addWidget(add_button)
        bottom.addStretch()
        settings_button = QPushButton('Settings')
        settings_button.clicked.connect(SettingsWindow.open)
        bottom.addWidget(settings_button)

    def search(self, text: str, names: bool) -> None:
        self.model.names = names
        self.pattern.setText(text)
        self.update_search()

    def update_search(self) -> None:
        self.model.search(self.pattern.text())
        self.table.resizeRowsToContents()
        self.table.selectRow(0)

    def on_add(self) -> None:
        selection = self.table.selectionModel()
        assert selection is not None
        add_notes(self.model.words[index.row()] for index in selection.selectedRows())

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            QMainWindow.keyPressEvent(self, event)

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
