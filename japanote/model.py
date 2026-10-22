from __future__ import annotations

from functools import partial
from gettext import ngettext
from html import escape
from typing import TYPE_CHECKING, Any

from anki.collection import SearchNode
from anki.notes import NoteFieldsCheckResult
from aqt import mw
from aqt.qt import QAbstractTableModel, QModelIndex, Qt
from aqt.utils import showInfo, tooltip

from . import audio, config, resources
from .collection import get_collection
from .dictionary import Word, search_words
from .pitch import pitches_html
from .settingswindow import SettingsWindow

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from concurrent.futures import Future

    from anki.models import NotetypeDict
    from anki.notes import Note, NoteId


# JMdict IDs searched at a time (see existing_ids); Anki fails with more than 1000 terms (twice as many)
SEARCH_BATCH = 200


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


def look_up_recording(word: Word, on_done: Callable[[str | None], None]) -> None:
    """Look for a recording of word in the background, then call on_done with its [sound:…] tag, or None"""
    def done(future: Future) -> None:
        try:
            recording = future.result()
        except Exception as e:  # noqa: BLE001
            # not worth interrupting the user
            print(f'JapaNote: could not fetch a recording: {e}')
            recording = None
        if recording is None:
            on_done(None)
            return
        filename = get_collection().media.write_data(*recording)
        on_done(f'[sound:{filename}]')

    assert mw is not None
    mw.taskman.run_in_background(lambda: audio.fetch([word.kanji, word.kana]), done)


def set_recording(note_id: NoteId, field_name: str, sound: str | None) -> None:
    """Put a recording in a note that was added, unless its field was filled in the meantime"""
    if sound is None:
        return
    col = get_collection()
    note = col.get_note(note_id)
    if not note[field_name].strip():
        note[field_name] = sound
        col.update_note(note)


def fill_note(note: Note, word: Word, fields: dict[str, str], conf: dict[str, Any]) -> None:
    """Fill the fields of note (given by role, see config.FIELDS), and set its tags"""
    values = {
        'kanji': word.kanji,
        'kana': word.kana,
        'furigana': word.furigana,
        'definition': word.definition_html(),
        'id': word.id,
        'pitch': pitches_html(word.kana, word.pitch),
        # filled later (see look_up_recording)
        'audio': '',
        'example': '',
        'kanji_details': '',
    }
    if 'kanji_details' in fields:
        values['kanji_details'] = '<br>'.join(kanji.html() for kanji in resources.jmdict.kanji(word.kanji))
    if 'example' in fields:
        example = resources.jmdict.example(word.id)
        values['example'] = example.html() if example else ''
    for role, name in fields.items():
        note[name] = values[role]
    note.tags = conf['tags'].split()
    if conf['tag_jlpt'] and word.jlpt:
        note.tags.append(f'JLPT::N{word.jlpt}')
    if conf['tag_common'] and word.common:
        note.tags.append('common')


def existing_ids(field_name: str, word_ids: list[str]) -> set[str]:
    """The JMdict IDs that a note already has (see find_by_id), with a search for many IDs at a time"""
    col = get_collection()
    found = set()
    for start in range(0, len(word_ids), SEARCH_BATCH):
        search = col.build_search_string(
            *(
                SearchNode(field=SearchNode.Field(field_name=field_name, text=text))
                for word_id in word_ids[start:start + SEARCH_BATCH]
                for text in (word_id, word_id + 'X')
            ),
            joiner='OR',
        )
        for note_id in col.find_notes(search):
            found.add(col.get_note(note_id)[field_name].strip().removesuffix('X'))
    return found


def is_duplicate(note: Note, fields: dict[str, str]) -> bool:
    """Whether another note has the JMdict ID of note, or else, the same first field"""
    if 'id' in fields and note[fields['id']].strip():
        return find_by_id(fields['id'], note[fields['id']].strip())
    return note.fields_check() == NoteFieldsCheckResult.DUPLICATE


def note_settings(show_problem: bool = True) -> tuple[dict[str, Any], NotetypeDict, dict[str, str]] | None:
    """The settings, note type, and fields (by role) of new notes, unless they are unusable"""
    conf = config.get()
    problem = settings_problem(conf)
    if problem is not None:
        if show_problem:
            showInfo(problem)
            SettingsWindow.open()
        return None
    model = get_collection().models.by_name(conf['model'])
    assert model is not None
    return conf, model, {role: name for role, name in conf['fields'].items() if name}


def new_note(word: Word) -> Note | None:
    """The note that would be added for word (see add_notes), unless the settings are unusable"""
    settings = note_settings()
    if settings is None:
        return None
    conf, model, fields = settings
    note = get_collection().new_note(model)
    fill_note(note, word, fields, conf)
    return note


def find_duplicates(words: list[Word]) -> list[bool]:
    """Whether each word already has a note (none, when no note can be added with the settings)"""
    settings = note_settings(show_problem=False)
    if settings is None:
        return [False] * len(words)
    conf, model, fields = settings
    ids = existing_ids(fields['id'], [word.id for word in words if word.id]) if 'id' in fields else set()
    duplicates = []
    for word in words:
        if 'id' in fields and word.id:
            duplicates.append(word.id in ids)
            continue
        note = get_collection().new_note(model)
        fill_note(note, word, fields, conf)
        duplicates.append(is_duplicate(note, fields))
    return duplicates


def add_notes(words: Iterable[Word]) -> int:
    """Add a note for each word, and return the number of new cards"""
    settings = note_settings()
    if settings is None:
        return 0
    conf, model, fields = settings
    notes = []
    for word in words:
        note = get_collection().new_note(model)
        fill_note(note, word, fields, conf)
        notes.append((word, note))
    return add_filled_notes(notes)


def wants_recording(note: Note, word: Word, fields: dict[str, str]) -> bool:
    # sentences (without ID) are never recorded, nor notes that already have a recording
    return 'audio' in fields and bool(word.id) and not note[fields['audio']].strip()


def add_filled_notes(notes: Iterable[tuple[Word, Note]], look_up_recordings: bool = True) -> int:
    """Add notes (e.g. as edited in the preview), each made for a word, and return the number of new cards

    Unless told not to (e.g. by the preview, which looks for it itself), look for the recording of each note.
    """
    col = get_collection()
    settings = note_settings()
    if settings is None:
        return 0
    conf, _, fields = settings
    deck_id = col.decks.id_for_name(conf['deck']) if conf['deck'] else None
    if deck_id is None:
        deck_id = col.decks.get_current_id()

    n_new_cards = 0
    added: list[Word] = []
    duplicates: list[Word] = []
    for word, note in notes:
        if is_duplicate(note, fields):
            duplicates.append(word)
            continue

        # NOTE: cards go to deck_id, unless their template has a deck override (see settings)
        col.add_note(note, deck_id)
        n_new_cards += len(note.card_ids())
        added.append(word)
        if look_up_recordings and wants_recording(note, word, fields):
            look_up_recording(word, partial(set_recording, note.id, fields['audio']))

    if n_new_cards == 0:
        if len(duplicates) == 1:
            showInfo(f'There is already a note for {duplicates[0].label()}')
        elif duplicates:
            showInfo('There are already notes for these words')
    else:
        # name the word, since it may not be the one expected (e.g. the dictionary form of a verb)
        what = escape(added[0].label(), quote=False) if len(added) == 1 else f'{len(added)} notes'
        cards = ngettext('{} card', '{} cards', n_new_cards).format(n_new_cards)
        tooltip(f'Added {what} ({cards}).')
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
