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
    @pyqtSlot(str, result=bool)
    @pyqtSlot(str, bool, result=bool)
    def quickAdd(self, pattern: str, is_proper_noun: bool = False) -> bool:
        pattern = pattern.strip()
        if not pattern:
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
    return _old(self) + """
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word</legend>
        <input style="height:2em; box-sizing:border-box; width:100%; margin:5px; padding:5px;" type="text" id="quick-add-pattern" placeholder="あんき">
        <button onclick="quickAddWord()" style="border:2px solid black">Add Word</button>
        <button onclick="quickAddNoun()">Add Proper Noun</button>
        <button onclick="edict.showSettings()">Settings</button>
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
        edict.quickAdd(quickAddPattern.value);
        quickAddPattern.value = "";
    }
    function quickAddNoun() {
        edict.quickAdd(quickAddPattern.value, true);
        quickAddPattern.value = "";
    }
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


main()
