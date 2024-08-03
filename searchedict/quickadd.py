from anki.hooks import wrap
from aqt import mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import *
from aqt.utils import showInfo

from .model import add_notes, word_search
from .searchedict import SearchEDICTWindow
from .searchsettings import SearchSettingsWindow
from .view import refresh_deckBrowser


class JavaScriptBridge(QObject):
    @pyqtSlot(str)
    def quickAdd(self, pattern):
        pattern = pattern.strip()
        if not pattern:
            return None
        word_search.search(pattern, enable_edict=True, enable_deinflect=True, enable_enamdict=False)
        if not word_search.words:
            showInfo('No word found')
            return 0
        elif len(word_search.words) > 1:
            SearchEDICTWindow.open(pattern)
            return 1
        else:
            add_notes(word_search.words)
            return 1

    @pyqtSlot()
    def showSettings(self):
        SearchSettingsWindow.open()


class QuickAddModule:
    def __init__(self):
        self.display_quickadd = False
        self.hooked_quickadd = False
        self.bridge = JavaScriptBridge()

    def display(self):
        self.display_quickadd = True
        if not self.hooked_quickadd:
            # display quick add form
            DeckBrowser._renderStats = wrap(DeckBrowser._renderStats, self.render, 'around')
            self.hooked_quickadd = True

            # add bridge to JavaScript's namespace
            web_page = mw.deckBrowser.web.page()
            if hasattr(web_page, 'setWebChannel'):  # Qt5
                channel = web_page.webChannel()
                channel.registerObject('edict', self.bridge)
            else:  # Qt4
                def register_bridge():
                    web_page = mw.deckBrowser.web.page()
                    web_frame = web_page.mainFrame()
                    web_frame.addToJavaScriptWindowObject('edict', self.bridge)
                web_frame = web_page.mainFrame()
                web_frame.javaScriptWindowObjectCleared.connect(register_bridge)

        if mw.col is not None:
            refresh_deckBrowser()

    def undisplay(self):
        self.display_quickadd = True
        if mw.col is not None:
            refresh_deckBrowser()

    def render(self, args, _old):
        ret = _old(args)
        if not self.display_quickadd:
            return ret
        ret += """
    <fieldset style="width:500px; margin:30px 0 30px 0">
        <legend>Quick EDICT add</legend>
        <input style="height:1.8em" type="text" id="quick-add-pattern" placeholder="あんき">
        <input style="width:120px;" type="button" id="quick-add-button" value="Add EDICT note">
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
