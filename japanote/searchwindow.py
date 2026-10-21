from __future__ import annotations

from typing import Any

from aqt.qt import (
    QAbstractItemView,
    QCheckBox,
    QEvent,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QModelIndex,
    QPushButton,
    Qt,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from . import resources
from .model import WordSearchModel, add_notes
from .previewwindow import PreviewWindow
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
        self.names = QCheckBox('Proper nouns')
        self.names.toggled.connect(self.on_toggle_names)
        top.addWidget(self.names)
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
        self.table.doubleClicked.connect(self.on_edit)
        # NOTE: the table handles Enter, which would not reach the window
        self.table.installEventFilter(self)
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        # checking the note first is the usual way; several words can be added at once as they are
        edit_button = QPushButton('Edit and add…')
        edit_button.setDefault(True)
        edit_button.clicked.connect(lambda: self.on_edit(self.table.currentIndex()))
        bottom.addWidget(edit_button)
        add_button = QPushButton('Add as-is')
        add_button.setToolTip('Add the selected words without editing them')
        add_button.clicked.connect(self.on_add)
        bottom.addWidget(add_button)
        bottom.addStretch()
        settings_button = QPushButton('Settings')
        settings_button.clicked.connect(SettingsWindow.open)
        bottom.addWidget(settings_button)

    def search(self, text: str, names: bool) -> None:
        self.pattern.setText(text)
        self.names.blockSignals(True)
        self.names.setChecked(names)
        self.names.blockSignals(False)
        self.on_toggle_names(names)

    def on_toggle_names(self, names: bool) -> None:
        if names and not resources.is_ready('names'):
            resources.ensure('names', self.on_names_ready)
            return
        self.model.names = names
        self.update_search()

    def on_names_ready(self) -> None:
        # the window may have been closed during the download
        if type(self).instance is self:
            self.on_toggle_names(self.names.isChecked())

    def update_search(self) -> None:
        self.model.search(self.pattern.text())
        self.table.resizeRowsToContents()
        self.table.selectRow(0)

    def on_add(self) -> None:
        selection = self.table.selectionModel()
        assert selection is not None
        add_notes(self.model.words[index.row()] for index in selection.selectedRows())

    def on_edit(self, index: QModelIndex) -> None:
        if index.isValid():
            PreviewWindow.edit(self.model.words[index.row()])

    def eventFilter(self, watched: Any, event: Any) -> bool:
        """Edit the current word on Enter, like on a double click"""
        if (
            watched is self.table and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self.on_edit(self.table.currentIndex())
            return True
        return bool(QMainWindow.eventFilter(self, watched, event))

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            QMainWindow.keyPressEvent(self, event)

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
