from gettext import ngettext
from typing import Iterable, Optional

from anki.models import NotetypeDict
from anki.notes import Note
from aqt import Collection
from aqt.qt import QAbstractTableModel, Qt
from aqt.utils import showInfo, tooltip

from . import romkan
from .collection import get_collection
from .edict2.deinflect import Deinflector
from .edict2.search import Word, edict, enamdict
from .qt import QtCore
from .settingswindow import SettingsWindow


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
    model['did'] = deck['id']  # update model's default deck

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
        note_set_field(note, 'japanote_furiganaField', word.get_furigana())
        note_set_field(note, 'japanote_definitionField', word.get_meanings_html())
        note_set_field(note, 'japanote_idField', word.get_sequence_number())

        # check for duplicates if id field is set
        idfield = col.conf.get('japanote_idField')
        if idfield and col.find_notes(f'{idfield}:{word.get_sequence_number()}'):
            continue

        # add card
        n_newcards += col.addNote(note)
    tooltip(ngettext('{} card added.', '{} cards added.', n_newcards).format(n_newcards))


class WordSearchModel(QAbstractTableModel):
    def __init__(self) -> None:
        QAbstractTableModel.__init__(self)
        self.words: list[Word] = []
        self.is_proper_noun = False

    def rowCount(self, parent: QtCore.QModelIndex = ...) -> int:
        return len(self.words)

    def columnCount(self, parent: QtCore.QModelIndex = ...) -> int:
        return 5

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> str:
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return QAbstractTableModel.headerData(self, section, orientation, role)  # type: ignore
        return [
            'Kanji',
            'Kana',
            'Template',
            'JMDict ID',
            'Definition',
        ][section]

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Optional[str]:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            row: int = index.row()
            word = self.words[row]
            column = index.column()
            if column == 0:
                return word.kanji
            elif column == 1:
                return word.kana
            elif column == 2:
                return word.get_furigana()
            elif column == 3:
                return word.get_sequence_number()
            elif column == 4:
                return '\n'.join(word.get_meanings())
            else:
                raise NotImplementedError
        else:
            return None

    def sort(self, column: int, order: Qt.SortOrder = QtCore.Qt.SortOrder.DescendingOrder) -> None:
        reverse = order == QtCore.Qt.SortOrder.DescendingOrder
        if column == 0:
            key = lambda word: word.kanji
        elif column == 1:
            key = lambda word: word.kana
        else:
            return
        self.modelAboutToBeReset.emit()
        self.words = sorted(self.words, key=key, reverse=reverse)
        self.modelReset.emit()

    def search(self, word: str) -> None:
        word = romkan.to_hiragana(word)
        self.modelAboutToBeReset.emit()
        if self.is_proper_noun:
            self.words = list(enamdict.search(word))
        else:
            self.words = []
            for candidate in set(deinflector(word)):
                for word2 in edict.search(candidate.word):
                    if word2.get_type() & candidate.type_:
                        self.words.append(word2)
        self.modelReset.emit()


deinflector = Deinflector()
word_search = WordSearchModel()
