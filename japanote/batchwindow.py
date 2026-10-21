from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aqt.qt import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import resources
from .model import add_notes, find_duplicates, search_names, search_vocabulary
from .previewwindow import PreviewWindow
from .settingswindow import SettingsWindow
from .view import window_to_front

if TYPE_CHECKING:
    from .dictionary import Word

# matches offered for each line
MAX_MATCHES = 10


def parse_lines(text: str) -> list[str]:
    """The words of a list, one per line, without what follows a tab (e.g. the meaning), nor repetitions"""
    words = (line.split('\t')[0].strip() for line in text.splitlines())
    return list(dict.fromkeys(word for word in words if word))


class BatchWindow(QMainWindow):
    """Add notes for a list of words (e.g. the vocabulary of a lesson), after checking what was found"""
    instance: BatchWindow | None = None
    COLUMNS = ('Add', 'Typed', 'Word', 'Kana', 'Definition', 'Note')

    @classmethod
    def open(cls, text: str = '') -> None:
        if cls.instance is None:
            cls.instance = cls()
        if text:
            cls.instance.input.setPlainText(text)
            cls.instance.look_up()
        window_to_front(cls.instance)

    def __init__(self) -> None:
        QMainWindow.__init__(self)
        self.setWindowTitle('JapaNote: add several words')
        self.resize(1000, 600)
        # for each row: its line, the words found for it, whether each one already has a note, and the chosen one
        self.lines: list[str] = []
        self.matches: list[list[Word]] = []
        self.duplicates: list[list[bool]] = []
        self.chosen: list[int] = []

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel('Words, one per line, in kanji, kana or romaji (what follows a tab is ignored):'))
        self.input = QPlainTextEdit()
        self.input.setMaximumHeight(150)
        layout.addWidget(self.input)
        top = QHBoxLayout()
        layout.addLayout(top)
        self.names = QCheckBox('Also look in proper nouns')
        top.addWidget(self.names)
        top.addStretch()
        look_up_button = QPushButton('Look up')
        look_up_button.clicked.connect(self.look_up)
        top.addWidget(look_up_button)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COLUMNS.index('Definition'), QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda index: self.on_edit(index.row()))
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        self.summary = QLabel()
        bottom.addWidget(self.summary)
        bottom.addStretch()
        settings_button = QPushButton('Settings')
        settings_button.clicked.connect(SettingsWindow.open)
        bottom.addWidget(settings_button)
        add_button = QPushButton('Add checked')
        add_button.clicked.connect(self.on_add)
        bottom.addWidget(add_button)

    def look_up(self) -> None:
        if self.names.isChecked() and not resources.is_ready('names'):
            resources.ensure('names', self.on_names_ready)
            return
        self.lines = parse_lines(self.input.toPlainText())
        self.matches = []
        for line in self.lines:
            words = search_vocabulary(line)
            if not words and self.names.isChecked():
                words = search_names(line)
            self.matches.append(words[:MAX_MATCHES])
        self.chosen = [0] * len(self.lines)

        self.table.setRowCount(0)
        self.table.setRowCount(len(self.lines))
        for row, (line, words) in enumerate(zip(self.lines, self.matches)):
            check = QTableWidgetItem()
            if words:
                check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            else:
                check.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(line))
            if len(words) > 1:
                box = QComboBox()
                box.addItems([f'{word.kanji} 【{word.kana}】' for word in words])
                box.currentIndexChanged.connect(lambda index, row=row: self.on_combo_box(row, index))
                self.table.setCellWidget(row, 2, box)
        self.refresh()
        self.table.resizeRowsToContents()

    def refresh(self) -> None:
        """Show which words already have a note"""
        duplicates = iter(find_duplicates([word for words in self.matches for word in words]))
        self.duplicates = [[next(duplicates) for _ in words] for words in self.matches]
        for row, index in enumerate(self.chosen):
            self.on_choose(row, index)
        self.update_summary()

    def on_names_ready(self) -> None:
        # the window may have been closed during the download
        if type(self).instance is self:
            self.look_up()

    def on_choose(self, row: int, index: int) -> None:
        """Show the chosen word of a row, checked unless it already has a note"""
        self.chosen[row] = index
        check = self.table.item(row, 0)
        assert check is not None
        words = self.matches[row]
        if not words:
            self.set_cells(row, '', '', '', 'Not found; add it alone to look it up on Wikipedia, or as a sentence')
            check.setCheckState(Qt.CheckState.Unchecked)
            return
        word = words[index]
        duplicate = self.duplicates[row][index]
        notes = []
        if duplicate:
            notes.append('already added')
        if word.inflection:
            notes.append(f'{word.inflection} of {word.kanji}')
        if len(words) > 1:
            notes.append(f'{len(words)} matches')
        if word.id.startswith('EntN'):
            notes.append('proper noun')
        kanji = '' if len(words) > 1 else word.kanji  # shown by the combo box
        notes_text = '; '.join(notes)
        self.set_cells(row, kanji, word.kana, '; '.join(word.meanings), notes_text[:1].upper() + notes_text[1:])
        check.setCheckState(Qt.CheckState.Unchecked if duplicate else Qt.CheckState.Checked)

    def on_combo_box(self, row: int, index: int) -> None:
        self.on_choose(row, index)
        self.update_summary()

    def set_cells(self, row: int, *texts: str) -> None:
        for column, text in enumerate(texts, start=2):
            self.table.setItem(row, column, QTableWidgetItem(text))

    def checked_rows(self) -> list[int]:
        rows = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            if check is not None and check.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def update_summary(self) -> None:
        found = sum(1 for words in self.matches if words)
        added = sum(1 for row, words in enumerate(self.duplicates) if words and words[self.chosen[row]])
        parts = [f'{found} of {len(self.lines)} found']
        if added:
            parts.append(f'{added} already added')
        self.summary.setText(', '.join(parts))

    def on_add(self) -> None:
        words = [self.matches[row][self.chosen[row]] for row in self.checked_rows()]
        if words and add_notes(words):
            self.refresh()

    def on_edit(self, row: int) -> None:
        if self.matches[row]:
            PreviewWindow.edit(self.matches[row][self.chosen[row]])

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            QMainWindow.keyPressEvent(self, event)

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
