from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aqt import mw
from aqt.editor import Editor, EditorMode
from aqt.qt import QDialog, QDialogButtonBox, QKeySequence, QLabel, QShortcut, QVBoxLayout, QWidget

from . import config
from .model import add_filled_notes, new_note
from .view import window_to_front

if TYPE_CHECKING:
    from anki.notes import Note

    from .dictionary import Word


class PreviewWindow(QDialog):
    """Review, and edit, a note before adding it, in the editor of Anki"""
    instance: PreviewWindow | None = None

    @classmethod
    def edit(cls, word: Word, message: str = '') -> None:
        note = new_note(word)
        if note is None:
            # the settings cannot be used, which new_note told
            return
        if cls.instance is None:
            cls.instance = cls()
        cls.instance.set_note(word, note, message)
        window_to_front(cls.instance)

    def __init__(self) -> None:
        QDialog.__init__(self)
        self.setWindowTitle('JapaNote: add a note')
        self.resize(700, 650)
        self.word: Word | None = None
        self.note: Note | None = None

        layout = QVBoxLayout(self)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setOpenExternalLinks(True)
        layout.addWidget(self.message)

        # the fields, and the tags, as in the Add window of Anki, which does not save the note
        fields_area = QWidget()
        layout.addWidget(fields_area, 1)
        assert mw is not None
        self.editor = Editor(mw, fields_area, self, editor_mode=EditorMode.ADD_CARDS)

        buttons = QDialogButtonBox()
        self.add_button = buttons.addButton('Add', QDialogButtonBox.ButtonRole.AcceptRole)
        assert self.add_button is not None
        self.add_button.setDefault(True)
        self.add_button.setToolTip('Add (Ctrl+Enter)')
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.on_add)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        # like in the Add window of Anki, where Enter goes to the field being edited
        QShortcut(QKeySequence('Ctrl+Return'), self).activated.connect(self.on_add)

    def set_note(self, word: Word, note: Note, message: str) -> None:
        self.word = word
        self.note = note
        audio_field = config.get()['fields']['audio']
        if audio_field and word.id:
            what = 'A recording is looked up after adding the note'
            message += f'{"<br>" if message else ""}{what}, unless the {audio_field} field is filled.'
        self.message.setText(message)
        self.message.setVisible(bool(message))
        self.editor.set_note(note)
        # so that Enter adds the note, which is the most common
        self.add_button.setFocus()

    def on_add(self) -> None:
        # the editor saves the field being edited to the note before
        self.editor.call_after_note_saved(self.add)

    def add(self) -> None:
        if self.word is not None and self.note is not None and add_filled_notes([(self.word, self.note)]):
            self.close()

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: Any) -> None:
        self.editor.cleanup()
        type(self).instance = None
        event.accept()
