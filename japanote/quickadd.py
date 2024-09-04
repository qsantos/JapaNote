from typing import Callable, TypeVar

from anki.hooks import wrap
from aqt import mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import QObject, pyqtSlot
from aqt.utils import showInfo

from .model import add_notes, word_search
from .searchwindow import SearchWindow
from .searchsettings import SearchSettingsWindow
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
        SearchSettingsWindow.open()


class QuickAddModule:
    def __init__(self) -> None:
        self.display_quickadd = False
        self.hooked_quickadd = False
        self.bridge = JavaScriptBridge()

    def display(self) -> None:
        assert mw is not None
        self.display_quickadd = True
        if not self.hooked_quickadd:
            # display quick add form
            DeckBrowser._renderStats = wrap(DeckBrowser._renderStats, self.render, 'around')
            self.hooked_quickadd = True

            # add bridge to JavaScript's namespace
            web_page = mw.deckBrowser.web.page()
            channel = web_page.webChannel()
            channel.registerObject('edict', self.bridge)

        col = mw.col
        if col is not None:
            refresh_deckBrowser()

    def undisplay(self) -> None:
        assert mw is not None
        self.display_quickadd = True
        col = mw.col
        if col is not None:
            refresh_deckBrowser()

    def render(self, args: T, _old: Callable[[T], str]) -> str:
        ret = _old(args)
        if not self.display_quickadd:
            return ret
        ret += """
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>JapaNote: create a note for a Japanese word</legend>
        <input style="height:1.8em" type="text" id="quick-add-pattern" placeholder="あんき">
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
    var quickadd = document.querySelector('#quick-add-button');
    var pattern = document.querySelector('#quick-add-pattern');
    var settings = document.querySelector('#quick-add-settings');
    quickadd.addEventListener('click', function(event) { if (edict.quickAdd(pattern.value)) { pattern.value = ''; } });
    settings.addEventListener('click', function(event) { edict.showSettings() });
    pattern.addEventListener('keypress', function(event) { if (event.keyCode == 13) { edict.quickAdd(pattern.value) } });
    })();
    </script>"""
        return ret
