from __future__ import annotations

from gettext import ngettext
from typing import TYPE_CHECKING, Any

from anki.collection import SearchNode
from anki.notes import NoteFieldsCheckResult
from aqt.qt import QAbstractTableModel, QModelIndex, Qt
from aqt.utils import showInfo, tooltip

from . import config, resources
from .collection import get_collection
from .dictionary import Word, search_words
from .settingswindow import SettingsWindow

if TYPE_CHECKING:
    from collections.abc import Iterable


def find_by_id(field_name: str, word_id: str) -> bool:
    """Whether a note already has this JMdict ID; JapaNote 1 stored IDs like EntL1358280X"""
    col = get_collection()
    search = col.build_search_string(
        SearchNode(field=SearchNode.Field(field_name=field_name, text=word_id)),
        SearchNode(field=SearchNode.Field(field_name=field_name, text=word_id + 'X')),
        joiner='OR',
    )
    return bool(col.find_notes(search))


def settings_problem(conf: dict[str, Any]) -> str | None:
    """What prevents adding notes with these settings, if anything"""
    if not conf['configured']:
        return 'Please check the settings first'
    model = get_collection().models.by_name(conf['model'])
    if model is None:
        return f'Note type "{conf["model"]}" not found; please check the settings'
    field_names = {field['name'] for field in model['flds']}
    for name in conf['fields'].values():
        if name and name not in field_names:
            return f'Note type "{model["name"]}" has no field "{name}"; please check the settings'
    return None


def add_notes(words: Iterable[Word]) -> int:
    """Add a note for each word, and return the number of new cards"""
    col = get_collection()
    conf = config.get()
    problem = settings_problem(conf)
    if problem is not None:
        showInfo(problem)
        SettingsWindow.open()
        return 0
    model = col.models.by_name(conf['model'])
    assert model is not None
    fields = {role: name for role, name in conf['fields'].items() if name}

    deck_id = col.decks.id_for_name(conf['deck']) if conf['deck'] else None
    if deck_id is None:
        deck_id = col.decks.get_current_id()

    n_new_cards = 0
    n_duplicates = 0
    for word in words:
        note = col.new_note(model)
        values = {
            'kanji': word.kanji,
            'kana': word.kana,
            'furigana': word.furigana,
            'definition': word.definition_html(),
            'id': word.id,
        }
        for role, name in fields.items():
            note[name] = values[role]
        note.tags = conf['tags'].split()
        if conf['tag_jlpt'] and word.jlpt:
            note.tags.append(f'JLPT::N{word.jlpt}')
        if conf['tag_common'] and word.common:
            note.tags.append('common')

        if 'id' in fields and word.id:
            is_duplicate = find_by_id(fields['id'], word.id)
        else:
            is_duplicate = note.fields_check() == NoteFieldsCheckResult.DUPLICATE
        if is_duplicate:
            n_duplicates += 1
            continue

        # NOTE: cards go to deck_id, unless their template has a deck override (see settings)
        col.add_note(note, deck_id)
        n_new_cards += len(note.card_ids())

    if n_new_cards == 0:
        if n_duplicates:
            showInfo('Note already exists')
    else:
        tooltip(ngettext('{} card added.', '{} cards added.', n_new_cards).format(n_new_cards))
    return n_new_cards


class WordSearchModel(QAbstractTableModel):
    COLUMNS = ('Kanji', 'Kana', 'Furigana', 'JMdict ID', 'Definition')

    def __init__(self, names: bool = False) -> None:
        # whether to include proper nouns
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
        self.words = search_vocabulary(text)
        if self.names:
            self.words += search_names(text)
        self.endResetModel()


def search_vocabulary(text: str) -> list[Word]:
    return search_words(resources.jmdict, text, resources.deinflector)


def search_names(text: str) -> list[Word]:
    return search_words(resources.names, text)
