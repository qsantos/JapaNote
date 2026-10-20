from __future__ import annotations

from html import escape
from typing import Any

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser, DeckBrowserContent
from aqt.utils import showInfo

from . import analyzer, config, resources
from .dictionary import sentence_word
from .model import add_notes, search_names, search_vocabulary
from .previewwindow import PreviewWindow
from .searchwindow import SearchWindow
from .settingswindow import SettingsWindow


def clear_input() -> None:
    assert mw is not None
    if mw.state == 'deckBrowser':
        mw.deckBrowser.web.eval('document.getElementById("japanote-input").value = "";')


def retry(text: str) -> None:
    """Try again once a download is done, clearing the input field if it worked"""
    if quick_add(text):
        clear_input()


def quick_add(text: str) -> bool:  # noqa: PLR0911
    """Add a note for text, or open a window to do so; return whether the input field can be cleared

    Look for text in the vocabulary first, then in the proper nouns; failing that, assume it is a
    sentence.
    """
    text = text.strip()
    if not text:
        return False
    if not config.get()['configured']:
        showInfo('Please check the settings first')
        SettingsWindow.open()
        return False

    if not resources.is_ready('jmdict'):
        resources.ensure('jmdict', lambda: retry(text))
        return False
    words = search_vocabulary(text)
    names = False
    if not words:
        if not resources.is_ready('names'):
            resources.ensure('names', lambda: retry(text))
            return False
        words = search_names(text)
        names = True
    if len(words) == 1:
        add_notes(words)
        return True
    if words:
        SearchWindow.open(text, names)
        return True

    # not in the dictionaries (e.g. a sentence): guess the furigana, and let the user check them
    if not resources.is_ready('analyzer'):
        resources.ensure('analyzer', lambda: retry(text))
        return False
    word = sentence_word(resources.jmdict, text, analyzer.tokenize(text))
    PreviewWindow.edit(word, 'Not found in the dictionary; please check the furigana.')
    return True


def search(text: str) -> None:
    """Open the search window, without adding anything"""
    if not resources.is_ready('jmdict'):
        resources.ensure('jmdict', lambda: search(text))
        return
    SearchWindow.open(text.strip())


def render(deck_browser: DeckBrowser, content: DeckBrowserContent) -> None:  # noqa: ARG001
    content.stats += f"""
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word or sentence</legend>
        <input style="height:2em; box-sizing:border-box; width:100%; margin:5px 0; padding:5px;"
            type="text" id="japanote-input" placeholder="あんき">
        <button onclick="japanoteAdd()" style="border:2px solid black">Add</button>
        <button onclick="japanoteSearch()">Search…</button>
        <button onclick="pycmd('japanote:settings')">Settings</button>
        <div id="japanote-status" style="margin-top:5px; color:gray">{escape(resources.status())}</div>
    </fieldset>
    <script>
    function japanoteAdd() {{
        const input = document.getElementById("japanote-input");
        pycmd("japanote:add:" + input.value, (added) => {{
            if (added) {{
                input.value = "";
            }}
        }});
    }}
    function japanoteSearch() {{
        pycmd("japanote:search:" + document.getElementById("japanote-input").value);
    }}
    document.getElementById("japanote-input").addEventListener("keydown", (event) => {{
        if (event.key === "Enter") {{
            japanoteAdd();
        }}
    }});
    </script>
    """


def on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if not isinstance(context, DeckBrowser) or not message.startswith('japanote:'):
        return handled
    command, _, argument = message[len('japanote:'):].partition(':')
    if command == 'add':
        return True, quick_add(argument)
    if command == 'search':
        search(argument)
        return True, None
    if command == 'settings':
        SettingsWindow.open()
        return True, None
    return handled


def on_profile_open() -> None:
    config.migrate()
    resources.on_profile_open()


def on_profile_close() -> None:
    for dictionary in resources.DICTIONARIES.values():
        dictionary.close()


def main() -> None:
    gui_hooks.deck_browser_will_render_content.append(render)
    gui_hooks.webview_did_receive_js_message.append(on_js_message)
    gui_hooks.profile_did_open.append(on_profile_open)
    gui_hooks.profile_will_close.append(on_profile_close)


if mw is not None:
    main()
