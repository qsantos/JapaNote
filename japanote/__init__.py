from __future__ import annotations

import json
from html import escape
from typing import Any

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser, DeckBrowserContent
from aqt.utils import showInfo

from . import resources
from .model import add_notes, word_search
from .searchwindow import SearchWindow
from .settingswindow import SettingsWindow


def clear_input() -> None:
    assert mw is not None
    if mw.state == 'deckBrowser':
        mw.deckBrowser.web.eval('document.getElementById("japanote-input").value = "";')


def retry(text: str, names: bool) -> None:
    """Try again once a download is done, clearing the input field if it worked"""
    if quick_add(text, names):
        clear_input()


def quick_add(text: str, names: bool = False) -> bool:
    """Add a note for text, or open a window to do so; return whether the input field can be cleared"""
    text = text.strip()
    if not text:
        return False

    dictionary = 'names' if names else 'jmdict'
    if not resources.is_ready(dictionary):
        resources.ensure(dictionary, lambda: retry(text, names))
        return False

    word_search.is_proper_noun = names
    word_search.search(text)
    if not word_search.words:
        showInfo('No word found')
        return False
    if len(word_search.words) > 1:
        SearchWindow.open(text)
        return True
    add_notes(word_search.words)
    return True


def render(deck_browser: DeckBrowser, content: DeckBrowserContent) -> None:  # noqa: ARG001
    content.stats += f"""
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word</legend>
        <input style="height:2em; box-sizing:border-box; width:100%; margin:5px 0; padding:5px;"
            type="text" id="japanote-input" placeholder="あんき">
        <button onclick="japanoteAdd(false)" style="border:2px solid black">Add Word</button>
        <button onclick="japanoteAdd(true)">Add Proper Noun</button>
        <button onclick="pycmd('japanote:settings')">Settings</button>
        <div id="japanote-status" style="margin-top:5px; color:gray">{escape(resources.status())}</div>
    </fieldset>
    <script>
    function japanoteAdd(names) {{
        const input = document.getElementById("japanote-input");
        const message = JSON.stringify({{text: input.value, names: names}});
        pycmd("japanote:add:" + message, (added) => {{
            if (added) {{
                input.value = "";
            }}
        }});
    }}
    document.getElementById("japanote-input").addEventListener("keydown", (event) => {{
        if (event.key === "Enter") {{
            japanoteAdd(false);
        }}
    }});
    </script>
    """


def on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if not isinstance(context, DeckBrowser) or not message.startswith('japanote:'):
        return handled
    command, _, argument = message[len('japanote:'):].partition(':')
    if command == 'add':
        request = json.loads(argument)
        return True, quick_add(request['text'], request['names'])
    if command == 'settings':
        SettingsWindow.open()
        return True, None
    return handled


def on_profile_close() -> None:
    for dictionary in resources.DICTIONARIES.values():
        dictionary.close()


def main() -> None:
    gui_hooks.deck_browser_will_render_content.append(render)
    gui_hooks.webview_did_receive_js_message.append(on_js_message)
    gui_hooks.profile_did_open.append(resources.on_profile_open)
    gui_hooks.profile_will_close.append(on_profile_close)


if mw is not None:
    main()
