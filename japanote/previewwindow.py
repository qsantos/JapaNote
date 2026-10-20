from __future__ import annotations

from dataclasses import replace
from typing import Any

from aqt.qt import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout

from .dictionary import Word
from .model import add_notes
from .view import window_to_front


class PreviewWindow(QDialog):
    """Review, and edit, a note before adding it"""
    instance: PreviewWindow | None = None

    @classmethod
    def edit(cls, word: Word, message: str = '') -> None:
        if cls.instance is None:
            cls.instance = cls()
        cls.instance.set_word(word, message)
        window_to_front(cls.instance)

    def __init__(self) -> None:
        QDialog.__init__(self)
        self.setWindowTitle('JapaNote: add a note')
        self.setMinimumWidth(500)
        self.word = Word('', '', '')

        layout = QVBoxLayout(self)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setOpenExternalLinks(True)
        layout.addWidget(self.message)

        form = QFormLayout()
        layout.addLayout(form)
        self.kanji = QLineEdit()
        self.kana = QLineEdit()
        self.furigana = QLineEdit()
        self.definition = QPlainTextEdit()
        self.definition.setPlaceholderText('One meaning per line')
        form.addRow('Kanji', self.kanji)
        form.addRow('Kana', self.kana)
        form.addRow('Furigana', self.furigana)
        form.addRow('Definition', self.definition)

        buttons = QDialogButtonBox()
        add_button = buttons.addButton('Add', QDialogButtonBox.ButtonRole.AcceptRole)
        assert add_button is not None
        add_button.setDefault(True)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.on_add)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def set_word(self, word: Word, message: str) -> None:
        self.word = word
        self.message.setText(message)
        self.message.setVisible(bool(message))
        self.kanji.setText(word.kanji)
        self.kana.setText(word.kana)
        self.furigana.setText(word.furigana)
        self.definition.setPlainText('\n'.join(word.meanings))
        self.furigana.setFocus()

    def on_add(self) -> None:
        meanings = [line.strip() for line in self.definition.toPlainText().splitlines() if line.strip()]
        word = replace(
            self.word,
            kanji=self.kanji.text().strip(),
            kana=self.kana.text().strip(),
            furigana=self.furigana.text().strip(),
            meanings=meanings,
        )
        if add_notes([word]):
            self.close()

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
