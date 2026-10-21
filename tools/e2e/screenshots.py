# mypy: disable-error-code="union-attr, index, arg-type, attr-defined, list-item"
"""An add-on that takes the screenshots of the listing of JapaNote on AnkiWeb

Run it like the harness, but with this file (see README.md); it sets up a note type with every field that JapaNote
fills, adds a few words, then saves the screenshots in the base directory, in the theme given by
JAPANOTE_SCREENSHOTS_THEME (light, the default, or dark).
"""
from __future__ import annotations

import os
import time
import traceback
from typing import Callable, Optional

from aqt import gui_hooks, mw
from aqt.qt import QTimer
from aqt.theme import Theme

import japanote
import japanote.config as cfg
import japanote.model
import japanote.resources as res
from japanote.batchwindow import BatchWindow
from japanote.previewwindow import PreviewWindow
from japanote.searchwindow import SearchWindow
from japanote.settingswindow import SettingsWindow

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
LOG = open(os.path.join(BASE_DIR, 'harness.log'), 'w', buffering=1)  # noqa: SIM115
THEME = os.environ.get('JAPANOTE_SCREENSHOTS_THEME', 'light')
# so that the decks have cards to review
WORDS = ['猫', '犬', '水', '学校', '先生', '電車', '天気', '友達', '勉強', '料理', '映画', '音楽']
# a sentence, whose furigana JapaNote guesses
SENTENCE = '明日は友達と一緒に映画を見に行きます。'
TRANSLATION = 'Tomorrow, I am going to see a movie with a friend.'
LIST = '漢字\nがっこう\nはし\nyomimasu\n'

FRONT = '<div class="expression">{{Expression}}</div>'
BACK = """{{FrontSide}}
<hr id="answer">
<div class="reading">{{furigana:Furigana}}</div>
<div class="pitch">{{Pitch}}</div>
<div class="meaning">{{Meaning}}</div>
<div class="example">{{Example}}</div>
<div class="kanji">{{Kanji}}</div>
{{Audio}}"""
CSS = """.card { font-family: sans-serif; font-size: 20px; text-align: center; }
.expression { font-size: 48px; }
.reading { font-size: 28px; }
.pitch { margin: 8px; }
.meaning { display: inline-block; margin: 16px; text-align: left; }
.example, .kanji { font-size: 16px; margin: 16px; }"""


def log(*args: object) -> None:
    print(*args, file=LOG)


def save(widget: object, name: str) -> None:
    path = os.path.join(BASE_DIR, f'{name}.png')
    widget.grab().save(path)
    log(f'  saved {path}')


def set_up() -> None:
    col = mw.col
    models = col.models
    model = models.new('Japanese vocabulary')
    for name in ['Expression', 'Reading', 'Furigana', 'Meaning', 'Pitch', 'Example', 'Kanji', 'Audio', 'ID']:
        models.add_field(model, models.new_field(name))
    for name, front, back in [
        ('Recognition', FRONT, BACK),
        ('Recall', '<div class="meaning">{{Meaning}}</div>', BACK.replace('{{FrontSide}}', FRONT)),
    ]:
        template = models.new_template(name)
        template['qfmt'] = front
        template['afmt'] = back
        models.add_template(model, template)
    model['css'] = CSS
    models.add(model)
    added = models.by_name('Japanese vocabulary')
    assert added is not None
    model = added
    model['tmpls'][1]['did'] = col.decks.id('Japanese::Recall')
    models.update_dict(model)
    col.decks.id('Japanese::Vocabulary')
    deck = col.decks.by_name('Japanese')
    deck['browserCollapsed'] = deck['collapsed'] = False
    col.decks.save(deck)
    # what make_profile.py made for the tests
    col.remove_notes(col.find_notes(''))
    for name in ['Vocab', 'Spelling']:
        col.decks.remove([col.decks.id(name, create=False)])

    config = cfg.get()
    config['configured'] = True
    config['deck'] = 'Japanese::Vocabulary'
    config['model'] = 'Japanese vocabulary'
    config['fields'] = {
        'kanji': 'Expression', 'kana': 'Reading', 'furigana': 'Furigana', 'definition': 'Meaning', 'id': 'ID',
        'pitch': 'Pitch', 'example': 'Example', 'kanji_details': 'Kanji', 'audio': '',
    }
    cfg.save(config)
    japanote.model.add_notes([res.jmdict.lookup(word)[0] for word in WORDS])
    # only for the word of the preview, rather than fetching a recording for each word
    config['fields']['audio'] = 'Audio'
    cfg.save(config)
    mw.set_theme(Theme.DARK if THEME == 'dark' else Theme.LIGHT)
    mw.resize(1000, 640)


Wait = Optional[Callable[[], object]]
steps: list[Callable[[], Wait]] = []
state: dict[str, object] = {}


def after(seconds: float) -> Callable[[], bool]:
    """Wait for the windows to be drawn"""
    deadline = time.monotonic() + seconds
    return lambda: time.monotonic() > deadline


@steps.append
def _() -> Wait:
    return lambda: res.is_ready('jmdict')


@steps.append
def _() -> Wait:
    set_up()
    mw.moveToState('deckBrowser')
    return after(2)


@steps.append
def _() -> Wait:
    mw.deckBrowser.web.eval("document.getElementById('japanote-input').value = 'tabemashita';")
    return after(1)


@steps.append
def _() -> Wait:
    save(mw, '1-main')
    japanote.quick_add('tabemashita')
    return after(2)


@steps.append
def _() -> Wait:
    preview = PreviewWindow.instance
    preview.resize(700, 900)
    return after(1)


@steps.append
def _() -> Wait:
    save(PreviewWindow.instance, '2-preview')
    PreviewWindow.instance.add()
    nid = mw.col.find_notes('Expression:食べる')[0]
    state['nid'] = nid
    # the recording is downloaded in the background
    return lambda: mw.col.get_note(nid)['Audio']


@steps.append
def _() -> Wait:
    # review the new word first
    col = mw.col
    note = col.get_note(state['nid'])
    col.sched.reposition_new_cards([card.id for card in note.cards()], 0, 1, randomize=False, shift_existing=True)
    col.decks.select(col.decks.id('Japanese::Vocabulary'))
    mw.moveToState('review')
    return after(2)


@steps.append
def _() -> Wait:
    mw.reviewer._showAnswer()
    return after(2)


@steps.append
def _() -> Wait:
    save(mw, '3-card')
    mw.moveToState('deckBrowser')
    SearchWindow.open('hashi')
    return after(1)


@steps.append
def _() -> Wait:
    window = SearchWindow.instance
    window.resize(900, 340)
    window.table.selectRow(0)
    return after(1)


@steps.append
def _() -> Wait:
    save(SearchWindow.instance, '4-search')
    SearchWindow.instance.close()
    BatchWindow.open(LIST)
    BatchWindow.instance.resize(1000, 420)
    return after(1)


@steps.append
def _() -> Wait:
    save(BatchWindow.instance, '5-list')
    BatchWindow.instance.close()
    SettingsWindow.open()
    return after(1)


@steps.append
def _() -> Wait:
    save(SettingsWindow.instance, '6-settings')
    SettingsWindow.instance.close()
    japanote.quick_add(SENTENCE)
    return lambda: PreviewWindow.instance is not None


@steps.append
def _() -> Wait:
    preview = PreviewWindow.instance
    # as the user would, since there is no definition for a sentence
    preview.note['Meaning'] = TRANSLATION
    # so that the card shows the furigana, rather than the details of every kanji
    preview.note['Kanji'] = ''
    preview.editor.loadNote()
    preview.resize(700, 560)
    return after(2)


@steps.append
def _() -> Wait:
    save(PreviewWindow.instance, '7-sentence')
    PreviewWindow.instance.add()
    col = mw.col
    note = col.get_note(col.find_notes(f'Expression:{SENTENCE}')[0])
    col.sched.reposition_new_cards([card.id for card in note.cards()], 0, 1, randomize=False, shift_existing=True)
    col.decks.select(col.decks.id('Japanese::Vocabulary'))
    mw.moveToState('review')
    return after(2)


@steps.append
def _() -> Wait:
    mw.reviewer._showAnswer()
    return after(2)


@steps.append
def _() -> Wait:
    save(mw, '8-sentence-card')
    return None


def run(i: int = 0) -> None:
    if i == len(steps):
        log('DONE')
        mw.close()
        return
    try:
        wait = steps[i]()
    except Exception:  # noqa: BLE001
        log('FAIL: exception\n' + traceback.format_exc())
        mw.close()
        return

    def poll() -> None:
        if wait is not None and not wait():
            QTimer.singleShot(200, poll)
            return
        run(i + 1)

    poll()


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, run))
