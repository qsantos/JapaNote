import json
from typing import Callable, TypeVar

from anki.hooks import wrap
from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import QObject, pyqtSlot
from aqt.utils import showInfo

from . import resources
from .model import add_notes, word_search
from .searchwindow import SearchWindow
from .settingswindow import SettingsWindow
from .view import refresh_deckBrowser


T = TypeVar('T')


def clear_input() -> None:
    assert mw is not None
    if mw.state == 'deckBrowser':
        mw.deckBrowser.web.eval('document.getElementById("quick-add-pattern").value = "";')


def retry(pattern: str, is_proper_noun: bool) -> None:
    """Try again once a download is done, clearing the input field if it worked"""
    if bridge.quickAdd(pattern, is_proper_noun):
        clear_input()


class JavaScriptBridge(QObject):
    @pyqtSlot(str, result=bool)
    @pyqtSlot(str, bool, result=bool)
    def quickAdd(self, pattern: str, is_proper_noun: bool = False) -> bool:
        pattern = pattern.strip()
        if not pattern:
            return False
        dictionary = 'names' if is_proper_noun else 'jmdict'
        if not resources.is_ready(dictionary):
            resources.ensure(dictionary, lambda: retry(pattern, is_proper_noun))
            return False
        word_search.is_proper_noun = is_proper_noun
        word_search.search(pattern)
        if not word_search.words:
            showInfo('No word found')
            return False
        elif len(word_search.words) > 1:
            SearchWindow.open(pattern)
            return True
        else:
            add_notes(word_search.words)
            return True

    @pyqtSlot()
    def showSettings(self) -> None:
        SettingsWindow.open()


bridge = JavaScriptBridge()


def render(self: DeckBrowser, _old: Callable[[DeckBrowser], str]) -> str:
    status = json.dumps(resources.status())
    return _old(self) + """
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word</legend>
        <input style="height:2em; box-sizing:border-box; width:100%; margin:5px; padding:5px;" type="text" id="quick-add-pattern" placeholder="あんき">
        <button onclick="quickAddWord()" style="border:2px solid black">Add Word</button>
        <button onclick="quickAddNoun()">Add Proper Noun</button>
        <button onclick="edict.showSettings()">Settings</button>
        <div id="japanote-status" style="margin-top:5px; color:gray"></div>
    </fieldset>
    <script type="text/javascript" src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
    if (typeof QWebChannel !== "undefined") {  // Qt5
        // yes, we really need setTimeout, or the channel breaks...
        setTimeout(function(){
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.edict = channel.objects.edict;
        })}, 100);
    }
    function quickAddWord() {
        edict.quickAdd(quickAddPattern.value).then(added => {
            if (added) {
                quickAddPattern.value = "";
            }
        });
    }
    function quickAddNoun() {
        edict.quickAdd(quickAddPattern.value, true).then(added => {
            if (added) {
                quickAddPattern.value = "";
            }
        });
    }
    document.getElementById("japanote-status").textContent = """ + status + """;
    const quickAddPattern = document.getElementById('quick-add-pattern');
    quickAddPattern.addEventListener('keypress', function(event) {
        if (event.keyCode == 13) { quickAddWord(); }
    });
    </script>"""


def main() -> None:
    assert mw is not None

    # display quick add form
    DeckBrowser._renderStats = wrap(DeckBrowser._renderStats, render, 'around')  # type: ignore

    # add bridge to JavaScript's namespace
    web_page = mw.deckBrowser.web.page()
    channel = web_page.webChannel()
    channel.registerObject('edict', bridge)

    gui_hooks.profile_did_open.append(resources.on_profile_open)
    gui_hooks.profile_will_close.append(on_profile_close)


def on_profile_close() -> None:
    for dictionary in resources.DICTIONARIES.values():
        dictionary.close()


main()
