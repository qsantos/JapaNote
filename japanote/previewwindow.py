from __future__ import annotations

from dataclasses import replace
from typing import Any

from aqt.qt import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from . import config, resources
from .dictionary import Example, Word
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
        self.setMinimumWidth(650)
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
        self.example = QLineEdit()
        self.example.setPlaceholderText('No example sentence')
        self.translation = QLineEdit()
        self.kanji_details = QPlainTextEdit()
        self.kanji_details.setPlaceholderText('One kanji per line, starting with the kanji')
        self.kanji_details.setMaximumHeight(120)
        form.addRow('Kanji', self.kanji)
        form.addRow('Kana', self.kana)
        form.addRow('Furigana', self.furigana)
        form.addRow('Definition', self.definition)
        # rows of the optional fields, only shown when notes have them (see set_word)
        self.optional_rows: dict[str, list[QWidget]] = {}
        for role, label, widget in [
            ('example', 'Example', self.example),
            ('example', 'Translation', self.translation),
            ('kanji_details', 'Kanji details', self.kanji_details),
        ]:
            label_widget = QLabel(label)
            form.addRow(label_widget, widget)
            self.optional_rows.setdefault(role, []).extend([label_widget, widget])

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
        example = word.example or resources.jmdict.example(word.id) or Example('', '', '')
        self.example.setText(example.japanese)
        self.translation.setText(example.english)
        # e.g. 食べた for 食べる, to show it in bold
        self.example_form = example.form or word.kanji
        if word.kanji_details is None:
            self.kanji_details.setPlainText('\n'.join(kanji.text() for kanji in resources.jmdict.kanji(word.kanji)))
        else:
            self.kanji_details.setPlainText('\n'.join(word.kanji_details))
        fields = config.get()['fields']
        for role, widgets in self.optional_rows.items():
            for widget in widgets:
                widget.setVisible(bool(fields[role]))
        self.furigana.setFocus()

    def on_add(self) -> None:
        meanings = [line.strip() for line in self.definition.toPlainText().splitlines() if line.strip()]
        word = replace(
            self.word,
            kanji=self.kanji.text().strip(),
            kana=self.kana.text().strip(),
            furigana=self.furigana.text().strip(),
            meanings=meanings,
            example=Example(self.example.text().strip(), self.translation.text().strip(), self.example_form),
            kanji_details=[
                line.strip() for line in self.kanji_details.toPlainText().splitlines() if line.strip()
            ],
        )
        if add_notes([word]):
            self.close()

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
