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
    def quickAdd(self, pattern: str) -> int:
        pattern = pattern.strip()
        if not pattern:
            return 0
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


class QuickAddModule:
    def __init__(self) -> None:
        assert mw is not None

        # display quick add form
        DeckBrowser._renderStats = wrap(DeckBrowser._renderStats, self.render, 'around')

        # add bridge to JavaScript's namespace
        self.bridge = JavaScriptBridge()
        web_page = mw.deckBrowser.web.page()
        channel = web_page.webChannel()
        channel.registerObject('edict', self.bridge)

    def render(self, args: T, _old: Callable[[T], str]) -> str:
        return _old(args) + """
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word</legend>
        <input style="height:1.8em" type="text" id="quick-add-pattern" placeholder="あんき" autofocus>
        <input style="width:120px;" type="button" id="quick-add-button" value="Add Japanese note">
        <input style="width:120px;" type="button" id="quick-add-settings" value="Settings">
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
    const quickadd = document.getElementById('quick-add-button');
    const pattern = document.getElementById('quick-add-pattern');
    const settings = document.getElementById('quick-add-settings');
    quickadd.addEventListener('click', function(event) { if (edict.quickAdd(pattern.value)) { pattern.value = ''; } });
    settings.addEventListener('click', function(event) { edict.showSettings() });
    pattern.addEventListener('keypress', function(event) { if (event.keyCode == 13) { edict.quickAdd(pattern.value) } });
    })();
    </script>"""


QuickAddModule()
