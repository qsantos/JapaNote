# mypy: disable-error-code="union-attr, index, arg-type, attr-defined, assignment"
"""An add-on that drives JapaNote in a real Anki, and checks what it does

run.sh installs it next to JapaNote. Once the profile is open, it runs the steps below one after
the other, each one waiting until what it started is done (e.g. a download), then closes Anki. It
writes what it sees to harness.log in the base directory, with a line starting with FAIL for each
failed check; it also measures the longest time that the interface did not respond.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from typing import Any, Callable, Optional

from aqt import gui_hooks, mw
from aqt.qt import Qt, QTimer

import japanote.config as cfg
import japanote.download
import japanote.model
import japanote.resources as res
from japanote.batchwindow import BatchWindow, read_list
from japanote.previewwindow import PreviewWindow
from japanote.searchwindow import SearchWindow
from japanote.settingswindow import CreditsWindow, SettingsWindow

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
LOG = open(os.path.join(BASE_DIR, 'harness.log'), 'w', buffering=1)  # noqa: SIM115
# words in the long list to add
LONG_LIST = 1000
# above this, the interface feels frozen
MAX_FREEZE_MS = 300

japanote_init = sys.modules['japanote']
quick_add = japanote_init.quick_add


def log(*args: object, sep: str = ' ') -> None:
    print(*args, file=LOG, sep=sep)


def check(condition: object, what: str) -> None:
    log(('  ok: ' if condition else 'FAIL: ') + what)


# record the messages instead of showing them, since they would wait for a click
messages: list[str] = []


def fake_message(message: str, *_args: object, **_kwargs: object) -> None:
    messages.append(message)
    log('  message:', message)


japanote_init.showInfo = fake_message
japanote.model.showInfo = fake_message
japanote.model.tooltip = fake_message
res.tooltip = fake_message

# record the statuses below the input field, and take a screenshot of each progress bar
statuses: list[str] = []
screenshots: set[str] = set()
original_set_status = res.set_status


def spy_status(text: str, percent: int | None = None) -> None:
    if not statuses or statuses[-1] != text:
        statuses.append(text)
    original_set_status(text, percent)
    for word in ('Downloading', 'Preparing'):
        if text.startswith(word) and percent and percent >= 40 and word not in screenshots:
            screenshots.add(word)
            path = os.path.join(BASE_DIR, f'screenshot-{word}.png')
            QTimer.singleShot(100, lambda path=path: mw.grab().save(path))


res.set_status = spy_status

# record the full downloads, to tell them from the patches
full_downloads: list[str] = []
original_install_database = japanote.download.install_database


def spy_install_database(url: str, *args: Any, **kwargs: Any) -> str:
    full_downloads.append(url)
    return original_install_database(url, *args, **kwargs)


japanote.download.install_database = spy_install_database
res.install_database = spy_install_database

# the longest time the main thread did not run its event loop, by status
heartbeat = {'last': time.monotonic(), 'worst': 0.0}
freezes: dict[str, int] = {}


def beat() -> None:
    now = time.monotonic()
    gap = now - heartbeat['last']
    heartbeat['worst'] = max(heartbeat['worst'], gap)
    heartbeat['last'] = now
    if state.get('user action'):
        phase = 'user action'
    else:
        phase = (statuses[-1].split(' ')[0] or 'idle') if statuses else 'startup'
    freezes[phase] = max(freezes.get(phase, 0), round(gap * 1000))


beat_timer = QTimer()
beat_timer.timeout.connect(beat)
beat_timer.start(10)


def notes() -> list[tuple[Any, ...]]:
    col = mw.col
    summary = []
    for nid in col.find_notes('note:Japanese'):
        note = col.get_note(nid)
        decks = sorted({f"{card.template()['name']}→{col.decks.name(card.did)}" for card in note.cards()})
        fields = (note['Expression'], note['Reading'], note['Furigana'], note['Meaning'][:60], note['ID'])
        summary.append((*fields, decks))
    return summary


def proper_nouns() -> list[tuple[Any, ...]]:
    return [note for note in notes() if note[1] == 'すずきいちろう']


def find(expression: str) -> list[tuple[Any, ...]]:
    return [note for note in notes() if note[0] == expression]


# (name, function, timeout, whether the user waits for it); a step may return a function telling whether what it
# started is done
Wait = Optional[Callable[[], object]]
steps: list[tuple[str, Callable[[], Wait], float, bool]] = []
state: dict[str, Any] = {}


def step(
    name: str, timeout: float = 120, user_action: bool = False,
) -> Callable[[Callable[[], Wait]], Callable[[], Wait]]:
    def decorator(function: Callable[[], Wait]) -> Callable[[], Wait]:
        steps.append((name, function, timeout, user_action))
        return function
    return decorator


@step('the dictionary is downloaded at startup')
def _() -> Wait:
    config = mw.col.get_config('japanote')
    log('  config after migration:', json.dumps(config, ensure_ascii=False))
    check(config and config['deck'] == 'Vocab', 'the settings of JapaNote 1 are migrated')
    return lambda: res.is_ready('jmdict')


@step('settings: a deck for the Spelling cards')
def _() -> Wait:
    check(any(status.startswith('Downloading') and '%' in status for status in statuses), 'download progress shown')
    check(any(status.startswith('Preparing') and '%' in status for status in statuses), 'preparation progress shown')
    SettingsWindow.open()
    window = SettingsWindow.instance
    widgets = window.template_widgets
    rows = {widgets[i].text(): widgets[i + 1] for i in range(0, len(widgets), 2)}
    check(list(rows) == ['Recognition', 'Spelling'], f'a row per card type: {list(rows)}')
    rows['Spelling'].setCurrentText('Spelling')
    model = mw.col.models.by_name('Japanese')
    decks = {template['name']: template.get('did') and mw.col.decks.name(template['did'])
             for template in model['tmpls']}
    check(decks['Spelling'] == 'Spelling', f'deck override saved: {decks}')
    CreditsWindow.open()
    check(CreditsWindow.instance is not None, 'credits window opens')
    CreditsWindow.instance.close()
    window.close()
    return None


@step('settings: pitch, audio, example, kanji details and tags')
def _() -> Wait:
    model = mw.col.models.by_name('Japanese')
    for name in ('Pitch', 'Audio', 'Example', 'Kanji'):
        mw.col.models.add_field(model, mw.col.models.new_field(name))
    mw.col.models.update_dict(model)
    config = cfg.get()
    config['fields']['pitch'] = 'Pitch'
    config['fields']['audio'] = 'Audio'
    config['fields']['example'] = 'Example'
    config['fields']['kanji_details'] = 'Kanji'
    config['tags'] = 'japanote extra'
    cfg.save(config)
    return None


@step('a conjugated word: 食べました', timeout=30)
def _() -> Wait:
    log('  quick_add ->', quick_add('食べました'))
    check(messages[-1] == 'Added 食べる, from 食べました (polite past) (2 cards).', 'the dictionary form is named')
    added = find('食べる')
    check(added, f'added as 食べる: {added}')
    if not added:
        return None
    check(sorted(added[0][5]) == ['Recognition→Vocab', 'Spelling→Spelling'], 'cards in their decks')
    state['nid'] = mw.col.find_notes('Expression:食べる')[0]
    # the audio is downloaded in the background
    return lambda: mw.col.get_note(state['nid'])['Audio']


@step('tags, pitch, example, kanji details and audio of 食べる')
def _() -> Wait:
    note = mw.col.get_note(state['nid'])
    check('<b>食べ' in note['Example'] and '<br>' in note['Example'], f'example: {note["Example"]}')
    check(note['Kanji'].startswith('<b>食</b> eat'), f'kanji details: {note["Kanji"]}')
    check({'japanote', 'extra', 'common', 'JLPT::N5'} <= set(note.tags), f'tags: {note.tags}')
    check(note['Pitch'], f'pitch: {note["Pitch"]}')
    audio = note['Audio']
    check(audio.startswith('[sound:'), f'audio: {audio}')
    if audio.startswith('[sound:'):
        size = os.path.getsize(os.path.join(mw.col.media.dir(), audio[len('[sound:'):-1]))
        check(size > 1000, f'audio file: {size} bytes')
    return None


@step('the same word again')
def _() -> Wait:
    count = len(notes())
    log('  quick_add ->', quick_add('たべる'))
    check(len(notes()) == count, 'no duplicate')
    check(messages[-1] == 'There is already a note for 食べる', 'the message names the word')
    return None


@step('a word added by JapaNote 1')
def _() -> Wait:
    count = len(notes())
    word = res.jmdict.lookup('暗記')[0]
    log('  add_notes ->', japanote.model.add_notes([word]))
    check(len(notes()) == count, 'no duplicate (ID with an X suffix)')
    return None


@step('a word with several matches: かみ')
def _() -> Wait:
    log('  quick_add ->', quick_add('かみ'))
    window = SearchWindow.instance
    check(window is not None and len(window.model.words) > 1, 'the search window lists the matches')
    if window is not None:
        log('  matches:', [(word.kanji, word.id) for word in window.model.words[:4]])
        window.close()
    return None


@step('a proper noun: the names dictionary is downloaded on first use', timeout=180)
def _() -> Wait:
    log('  quick_add ->', quick_add('すずきいちろう'))
    return lambda: res.is_ready('names') and (SearchWindow.instance is not None or proper_nouns())


@step('the proper noun is added')
def _() -> Wait:
    window = SearchWindow.instance
    if window is not None:
        log('  matches:', [(word.kanji, word.kana, word.id) for word in window.model.words[:3]])
        window.table.selectRow(0)
        window.on_add()
        window.close()
    check(proper_nouns(), f'added: {proper_nouns()}')
    return None


@step('a sentence: the preview opens', timeout=60)
def _() -> Wait:
    log('  quick_add ->', quick_add('今日は大晦日なので、早く帰りました。'))
    return lambda: PreviewWindow.instance is not None


@step('the sentence is added')
def _() -> Wait:
    window = PreviewWindow.instance
    furigana = window.furigana.text()
    log('  preview:', window.message.text(), '|', window.kanji.text(), '|', window.kana.text(), '|', furigana)
    check('大[おお]晦日[みそか]' in furigana, 'furigana of the sentence')
    window.definition.setPlainText("Since it is New Year's Eve today, I went home early.")
    window.on_add()
    check(PreviewWindow.instance is None, 'the preview closes')
    check(find('今日は大晦日なので、早く帰りました。'), 'added')
    return None


@step('a technical word, from Wikipedia: 微分幾何学', timeout=30)
def _() -> Wait:
    log('  quick_add ->', quick_add('微分幾何学'))
    return lambda: PreviewWindow.instance is not None


@step('the technical word is added')
def _() -> Wait:
    window = PreviewWindow.instance
    log('  preview:', window.message.text(), '|', window.kana.text(), '|', window.definition.toPlainText())
    check(window.definition.toPlainText(), 'meaning from Wikipedia')
    window.on_add()
    check(find('微分幾何学'), 'added')
    return None


@step('the input field of the deck browser: neko, then Enter')
def _() -> Wait:
    mw.deckBrowser.refresh()

    def type_neko() -> None:
        mw.deckBrowser.web.eval("""
            const input = document.getElementById('japanote-input');
            input.value = 'neko';
            input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
        """)

    QTimer.singleShot(1500, type_neko)
    start = time.time()
    return lambda: time.time() - start > 4


@step('neko is added')
def _() -> Wait:
    check(find('猫'), 'added as 猫')
    mw.deckBrowser.web.evalWithCallback(
        "document.getElementById('japanote-input').value",
        lambda value: check(value == '', f'the input field is cleared: {value!r}'),
    )
    start = time.time()
    return lambda: time.time() - start > 1


@step('a list of words, pasted in the input field of the deck browser')
def _() -> Wait:
    mw.deckBrowser.web.eval("""
        const data = new DataTransfer();
        data.setData('text/plain', '食べました\\nかみ\\nみず\\tWater\\nxyzzy\\n');
        document.getElementById('japanote-input').dispatchEvent(
            new ClipboardEvent('paste', {clipboardData: data, cancelable: true}));
    """)
    return lambda: BatchWindow.instance is not None


@step('the list of words is checked, then added')
def _() -> Wait:
    window = BatchWindow.instance
    rows: dict[str, tuple[Any, ...]] = {}
    for row, line in enumerate(window.lines):
        cells = [window.table.item(row, column) for column in range(len(window.COLUMNS))]
        checked = cells[0].checkState() == Qt.CheckState.Checked
        texts = [cell.text() if cell else '' for cell in cells[2:]]
        box = window.table.cellWidget(row, 2)
        if box is not None:
            texts[0] = box.currentText()
        rows[line] = (checked, *texts)
        log(f'  {line}:', rows[line])
    check(list(rows) == ['食べました', 'かみ', 'みず', 'xyzzy'], 'a row per line, without what follows a tab')
    check(not rows['食べました'][0] and rows['食べました'][4].startswith('Already added'), '食べる is already added')
    check(rows['かみ'][0] and 'matches' in rows['かみ'][4], 'several matches for かみ')
    check(rows['みず'][0] and rows['みず'][1] == '水 【みず】', 'みず is 水')
    check(not rows['xyzzy'][0] and rows['xyzzy'][4].startswith('Not found'), 'xyzzy is not found')
    window.grab().save(os.path.join(BASE_DIR, 'screenshot-batch.png'))
    # the second match of かみ
    window.table.cellWidget(window.lines.index('かみ'), 2).setCurrentIndex(1)
    window.on_add()
    check(find('水') and find('神') and not find('紙'), 'the checked words are added')
    check(messages[-1] == 'Added 2 notes (4 cards).', f'message: {messages[-1]}')
    check(window.summary.text() == '3 of 4 found, 3 already added', f'summary: {window.summary.text()}')
    window.close()
    return None


@step('a long list, from a CSV file', user_action=True)
def _() -> Wait:
    # the most common words, as a CSV file, with their meanings in the second column
    path = os.path.join(BASE_DIR, 'words.csv')
    query = 'SELECT data FROM entry ORDER BY rank, id LIMIT ?'
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        for (data,) in res.jmdict.db.execute(query, (LONG_LIST,)):
            entry = json.loads(data)
            writer.writerow([(entry.get('k') or entry['r'])[0]['t'], entry['s'][0]['g'][0]])
    start = time.perf_counter()
    BatchWindow.open(read_list(path))
    elapsed = time.perf_counter() - start
    window = BatchWindow.instance
    check(len(window.lines) > LONG_LIST * 0.9, f'{len(window.lines)} lines, from the first column')
    check(elapsed < 3, f'looked up in {elapsed:.2f} s')
    window.close()
    return None


@step('a sentence split into lines')
def _() -> Wait:
    BatchWindow.open('今日は\n大晦日です。')
    BatchWindow.instance.on_sentence()
    check(BatchWindow.instance is None, 'the list window closes')
    preview = PreviewWindow.instance
    check(preview is not None and preview.kanji.text() == '今日は大晦日です。', 'the preview of the joined lines')
    if preview is not None:
        preview.close()
    return None


@step('an update, with patches', timeout=180)
def _() -> Wait:
    res.MANIFEST_URL = res.MANIFEST_URL.replace(f'manifest-v{res.FORMAT}.json', 'manifest-newer.json')
    with open(res._state_path(), 'w') as f:
        json.dump({'last_check': 0}, f)
    full_downloads.clear()
    state['versions'] = {name: dictionary.version() for name, dictionary in res.DICTIONARIES.items()}
    res.check_for_updates()
    return lambda: not res._busy


@step('the dictionaries are updated')
def _() -> Wait:
    versions = {name: dictionary.version() for name, dictionary in res.DICTIONARIES.items()}
    check(all(versions[name] != state['versions'][name] for name in versions), f'new versions: {versions}')
    check(not full_downloads, f'only the patches are downloaded: {full_downloads}')
    meanings = [meaning for word in res.jmdict.lookup('ねこ') if word.kanji == '猫' for meaning in word.meanings]
    check(any('updated by make_update.py' in str(meaning) for meaning in meanings), 'the change is applied')
    with open(res._state_path()) as f:
        check(json.load(f).get('last_check', 0) > 0, 'the time of the check is saved')
    return None


def finish() -> None:
    log('statuses:', [status for status in statuses if '%' not in status])
    log(f"longest freeze of the interface: {heartbeat['worst'] * 1000:.0f} ms; by status (ms): {freezes}")
    # Anki's own startup freezes the interface too, and so may what the user is waiting for (e.g. opening a
    # long list); only the work in the background is checked
    worst = max(gap for phase, gap in freezes.items() if phase not in ('startup', 'user action'))
    check(worst < MAX_FREEZE_MS, f'no freeze of more than {MAX_FREEZE_MS} ms')
    log('DONE')
    mw.close()


def run(i: int = 0) -> None:
    if i == len(steps):
        finish()
        return
    name, function, timeout, state['user action'] = steps[i]
    log(f'== {name}')
    try:
        wait = function()
    except Exception:  # noqa: BLE001
        log('FAIL: exception\n' + traceback.format_exc())
        wait = None
    start = time.time()

    def poll() -> None:
        if wait is not None and time.time() - start > timeout:
            log(f'FAIL: timeout after {timeout} s')
        elif wait is not None and not wait():
            QTimer.singleShot(200, poll)
            return
        QTimer.singleShot(300, lambda: run(i + 1))

    poll()


def on_profile_open() -> None:
    previous_hook = sys.excepthook

    def hook(*args: Any) -> None:
        log('FAIL: uncaught exception\n' + ''.join(traceback.format_exception(*args)))
        previous_hook(*args)

    sys.excepthook = hook
    QTimer.singleShot(500, run)


gui_hooks.profile_did_open.append(on_profile_open)
