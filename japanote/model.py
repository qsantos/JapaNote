from __future__ import annotations

from gettext import ngettext
from typing import TYPE_CHECKING, Any

from anki.collection import SearchNode
from anki.models import NotetypeDict
from anki.notes import Note
from aqt.qt import QAbstractTableModel, QModelIndex, Qt
from aqt.utils import showInfo, tooltip

from . import resources
from .collection import get_collection
from .dictionary import Word, search_words
from .settingswindow import SettingsWindow

if TYPE_CHECKING:
    from collections.abc import Iterable


def check_field(model: NotetypeDict, config_key: str) -> bool:
    col = get_collection()
    try:
        model_field = col.conf[config_key]
    except KeyError:
        return True
    if not model_field:
        return True
    for field in model['flds']:
        if field['name'] == model_field:
            return True
    showInfo(f'Field "{model_field}" not found')
    return False


def note_set_field(note: Note, config_key: str, value: str) -> None:
    col = get_collection()
    try:
        model_field = col.conf[config_key]
    except KeyError:
        return
    if not model_field:
        return
    try:
        note[model_field] = value if value is not None else ''
    except KeyError:
        model = col.models.get(note.mid)
        if model is None:
            showInfo(f'Model not found')
        else:
            showInfo(f'Note type "{model["name"]}" has no field "{model_field}"')


def find_by_id(field_name: str, word_id: str) -> bool:
    """Whether a note already has this JMdict ID; JapaNote 1 stored IDs like EntL1358280X"""
    col = get_collection()
    search = col.build_search_string(
        SearchNode(field=SearchNode.Field(field_name=field_name, text=word_id)),
        SearchNode(field=SearchNode.Field(field_name=field_name, text=word_id + 'X')),
        joiner='OR',
    )
    return bool(col.find_notes(search))


def add_notes(words: Iterable[Word]) -> None:
    col = get_collection()
    if not col.conf.get('japanote_hasopensettings'):
        showInfo('Please check the settings first')
        SettingsWindow.open()
        return

    # select deck
    deck_name = col.conf.get('japanote_deck')
    if deck_name is None:
        deck_id = col.decks.selected()
    else:
        deck_id = col.decks.id(deck_name) or col.decks.selected()
    deck = col.decks.get(deck_id)
    if deck is None:
        showInfo('Deck not found')
        return

    # select model
    try:
        model_name = col.conf['japanote_model']
    except KeyError:
        showInfo('Note type is not set')
        return
    model = col.models.by_name(model_name)
    if model is None:
        showInfo('Note type not found')
        return

    # check fields
    if not check_field(model, 'japanote_kanjiField'):
        return
    if not check_field(model, 'japanote_kanaField'):
        return
    if not check_field(model, 'japanote_furiganaField'):
        return
    if not check_field(model, 'japanote_definitionField'):
        return
    if not check_field(model, 'japanote_idField'):
        return

    n_newcards = 0
    for word in words:
        # create new note
        note = Note(col, model)
        # fill new note
        note_set_field(note, 'japanote_kanjiField', word.kanji)
        note_set_field(note, 'japanote_kanaField', word.kana)
        note_set_field(note, 'japanote_furiganaField', word.furigana)
        note_set_field(note, 'japanote_definitionField', word.definition_html())
        note_set_field(note, 'japanote_idField', word.id)

        # check for duplicates if id field is set
        idfield = col.conf.get('japanote_idField')
        if idfield and word.id and find_by_id(idfield, word.id):
            continue

        # NOTE: cards go to deck, unless their template has a deck override
        col.add_note(note, deck['id'])
        n_newcards += len(note.card_ids())

    if n_newcards == 0:
        showInfo('Note already exists')
    else:
        tooltip(ngettext('{} card added.', '{} cards added.', n_newcards).format(n_newcards))


class WordSearchModel(QAbstractTableModel):
    COLUMNS = ('Kanji', 'Kana', 'Furigana', 'JMdict ID', 'Definition')

    def __init__(self, names: bool = False) -> None:
        QAbstractTableModel.__init__(self)
        self.words: list[Word] = []
        self.names = names

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self.words)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: ARG002
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return QAbstractTableModel.headerData(self, section, orientation, role)
        return self.COLUMNS[section]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        word = self.words[index.row()]
        return (
            word.kanji,
            word.kana,
            word.furigana,
            word.id,
            '\n'.join(word.meanings),
        )[index.column()]

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if column not in (0, 1):
            return
        self.beginResetModel()
        self.words.sort(
            key=lambda word: word.kanji if column == 0 else word.kana,
            reverse=order == Qt.SortOrder.DescendingOrder,
        )
        self.endResetModel()

    def search(self, text: str) -> None:
        self.beginResetModel()
        self.words = search(text, self.names)
        self.endResetModel()


def search(text: str, names: bool) -> list[Word]:
    if names:
        return search_words(resources.names, text)
    return search_words(resources.jmdict, text, resources.deinflector)
