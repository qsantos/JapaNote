"""Make the dictionaries and the analyzer available, downloading and updating them in the background

The dictionaries are built and published by .github/workflows/dictionaries.yml. The main dictionary
is downloaded as soon as Anki starts; the names dictionary and the analyzer, only when first needed.
"""
from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any

from aqt import mw
from aqt.utils import tooltip

from . import analyzer
from .deinflect import Deinflector
from .dictionary import FORMAT, Dictionary
from .download import fetch_json, install_database, user_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Future

MANIFEST_URL = os.environ.get(
    'JAPANOTE_MANIFEST_URL',
    f'https://github.com/qsantos/JapaNote/releases/download/dictionaries/manifest-v{FORMAT}.json',
)
UPDATE_INTERVAL = 24 * 3600
# seconds between two updates of the progress of a download
PROGRESS_INTERVAL = 0.25

jmdict = Dictionary(user_file('jmdict.sqlite'), 'EntL')
names = Dictionary(user_file('names.sqlite'), 'EntN', kanji_source=jmdict)
deinflector = Deinflector()

DICTIONARIES = {'jmdict': jmdict, 'names': names}
LABELS = {
    'jmdict': 'the dictionary (about 20 MB)',
    'names': 'the names dictionary (about 35 MB)',
    'analyzer': 'the sentence analyzer (about 20 MB)',
}

_busy: set[str] = set()
# what to do once a resource is ready (only the last request is kept)
_pending: dict[str, Callable[[], None]] = {}
_status = ''


def status() -> str:
    return _status


def set_status(text: str) -> None:
    """Show text below the input field of the deck browser"""
    global _status  # noqa: PLW0603
    _status = text
    assert mw is not None
    if mw.state == 'deckBrowser':
        js = f"""
            var status = document.getElementById("japanote-status");
            if (status) {{ status.textContent = {json.dumps(text)}; }}
        """
        mw.deckBrowser.web.eval(js)


def _progress_reporter(label: str) -> Callable[[int, int], None]:
    """Report the progress of a download from a background thread, a few times per second"""
    last = 0.0

    def progress(done: int, total: int) -> None:
        nonlocal last
        now = time.monotonic()
        if now - last < PROGRESS_INTERVAL:
            return
        last = now
        percent = f' {100 * done // total}%' if total else ''
        text = f'Downloading {label}…{percent}'
        mw.taskman.run_on_main(lambda: set_status(text))
    return progress


def is_ready(name: str) -> bool:
    if name == 'analyzer':
        return analyzer.is_loaded()
    return os.path.exists(DICTIONARIES[name].path)


def ensure(name: str, then: Callable[[], None]) -> None:
    """Call then once the resource is ready, installing it first if needed"""
    if is_ready(name):
        then()
        return
    _pending[name] = then
    if name in _busy:
        return
    _busy.add(name)
    label = LABELS[name]
    set_status(f'Downloading {label}…')

    def task() -> str | None:
        progress = _progress_reporter(label)
        if name == 'analyzer':
            if not analyzer.is_installed():
                analyzer.install(progress)
            mw.taskman.run_on_main(lambda: set_status('Loading the sentence analyzer…'))
            analyzer.load()
            return None
        info = fetch_json(MANIFEST_URL)['dictionaries'][name]
        return install_database(info['url'], info['sha256'], DICTIONARIES[name].path, FORMAT, progress)

    def on_done(future: Future) -> None:
        _busy.discard(name)
        try:
            new = future.result()
        except Exception as e:  # noqa: BLE001
            _pending.pop(name, None)
            set_status(f'Could not download {label}: {e}')
            return
        if new is not None:
            dictionary = DICTIONARIES[name]
            dictionary.close()
            os.replace(new, dictionary.path)
        set_status('')
        callback = _pending.pop(name, None)
        if callback is not None:
            callback()

    mw.taskman.run_in_background(task, on_done)


def _state_path() -> str:
    return user_file('state.json')


def _load_state() -> dict[str, Any]:
    try:
        with open(_state_path()) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _save_state(state: dict[str, Any]) -> None:
    with open(_state_path(), 'w') as f:
        json.dump(state, f)


def check_for_updates() -> None:
    """Update the installed dictionaries, at most once a day"""
    state = _load_state()
    if time.time() - state.get('last_check', 0) < UPDATE_INTERVAL:
        return
    installed = {
        name: dictionary.version()
        for name, dictionary in DICTIONARIES.items()
        if os.path.exists(dictionary.path) and name not in _busy
    }
    if not installed:
        return
    _busy.update(installed)

    def task() -> dict[str, str]:
        manifest = fetch_json(MANIFEST_URL)
        updated = {}
        failed = False
        for name, version in installed.items():
            if manifest['version'] == version:
                continue
            info = manifest['dictionaries'][name]
            try:
                updated[name] = install_database(info['url'], info['sha256'], DICTIONARIES[name].path, FORMAT)
            except Exception as e:  # noqa: BLE001
                # keep the other updates; this one will be tried again on next start
                print(f'JapaNote: could not update {name}: {e}')
                failed = True
        if not failed:
            state['last_check'] = time.time()
            _save_state(state)
        return updated

    def on_done(future: Future) -> None:
        _busy.difference_update(installed)
        try:
            updated = future.result()
        except Exception as e:  # noqa: BLE001
            # not worth interrupting the user; it will be tried again on next start
            print(f'JapaNote: could not update the dictionaries: {e}')
            return
        for name, new in updated.items():
            dictionary = DICTIONARIES[name]
            dictionary.close()
            os.replace(new, dictionary.path)
        if updated:
            tooltip(f'JapaNote: dictionaries updated ({jmdict.version()})')

    mw.taskman.run_in_background(task, on_done)


def clean_up() -> None:
    """Remove files left by interrupted downloads"""
    for dictionary in DICTIONARIES.values():
        for suffix in ('.new', '.gz', '.gz.part'):
            path = dictionary.path + suffix
            if os.path.exists(path):
                os.remove(path)


def on_profile_open() -> None:
    clean_up()
    if is_ready('jmdict'):
        check_for_updates()
    else:
        ensure('jmdict', lambda: None)
