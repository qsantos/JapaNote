from typing import Callable, TypeVar

from anki.hooks import wrap
from aqt import mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import QObject, pyqtSlot
from aqt.utils import showInfo

from .model import add_notes, word_search
from .searchwindow import SearchWindow
from .settingswindow import SettingsWindow
from .view import refresh_deckBrowser


T = TypeVar('T')


class JavaScriptBridge(QObject):
    @pyqtSlot(str)
    @pyqtSlot(str, bool)
    def quickAdd(self, pattern: str, is_proper_noun: bool = False) -> int:
        pattern = pattern.strip()
        if not pattern:
            return 0
        word_search.is_proper_noun = is_proper_noun
        word_search.search(pattern)
        if not word_search.words:
            showInfo('No word found')
            return 0
        elif len(word_search.words) > 1:
            SearchWindow.open(pattern)
            return 1
        else:
            add_notes(word_search.words)
            return 1

    @pyqtSlot()
    def showSettings(self) -> None:
        SettingsWindow.open()


bridge = JavaScriptBridge()


def render(self: DeckBrowser, _old: Callable[[DeckBrowser], str]) -> str:
    return _old(self) + """
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word</legend>
        <input style="height:1.8em" type="text" id="quick-add-pattern" placeholder="あんき" autofocus>
        <button id="quick-add-word">Add Word</button>
        <button id="quick-add-proper-noun">Add Proper Noun</button>
        <button id="quick-add-settings">Settings</button>
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
    (function(){
    const pattern = document.getElementById('quick-add-pattern');
    document.getElementById('quick-add-word').addEventListener('click', function(event) { edict.quickAdd(pattern.value); });
    document.getElementById('quick-add-proper-noun').addEventListener('click', function(event) { edict.quickAdd(pattern.value, true); });
    document.getElementById('quick-add-settings').addEventListener('click', function(event) { edict.showSettings() });
    pattern.addEventListener('keypress', function(event) { if (event.keyCode == 13) { edict.quickAdd(pattern.value) } });
    })();
    </script>"""


def main() -> None:
    assert mw is not None

    # display quick add form
    DeckBrowser._renderStats = wrap(DeckBrowser._renderStats, render, 'around')

    # add bridge to JavaScript's namespace
    web_page = mw.deckBrowser.web.page()
    channel = web_page.webChannel()
    channel.registerObject('edict', bridge)


main()
