from anki.hooks import wrap
from aqt import mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import *
from aqt.utils import askUser, showInfo

from .edict.get import fetch_edict, fetch_enamdict
from .edict.index import build_index
from .edict.search import default_edict, default_edict_index, default_enamdict, default_enamdict_index
from .view import refresh_deckBrowser


class GetEDICTThread(QThread):
    progress = pyqtSignal(float, float)
    failed = pyqtSignal()
    completed = pyqtSignal()

    def run(self):
        if not fetch_edict(progress_callback=lambda x: self.progress.emit(x, 0.)):
            self.failed.emit()
            return
        build_index(default_edict, default_edict_index, lambda x:self.progress.emit(1., x))
        self.completed.emit()


class GetENAMDICTThread(QThread):
    progress = pyqtSignal(float, float)
    failed = pyqtSignal()
    completed = pyqtSignal()

    def run(self):
        if not fetch_enamdict(progress_callback=lambda x: self.progress.emit(x, 0.)):
            self.failed.emit()
            return
        build_index(default_enamdict, default_enamdict_index, lambda x:self.progress.emit(1., x))
        self.completed.emit()


class GetEDICTModule:
    def __init__(self):
        self.display_getedict = False
        self.hooked_getedict = False
        self.edict_done = False
        self.enamdict_done = False
        self.callback = None

    def display(self):
        self.display_getedict = True
        if not self.hooked_getedict:
            DeckBrowser._renderStats = wrap(DeckBrowser._renderStats, self.render, 'around')
            self.hooked_getedict = True
        if mw.col is not None:
            refresh_deckBrowser()

    def undisplay(self):
        self.display_getedict = False
        if mw.col is not None:
            refresh_deckBrowser()

    def render(self, args, _old):
        ret = _old(args)
        if not self.display_getedict:
            return ret
        ret += """
    <fieldset id="getedict" style="width:500px; margin:30px 0 30px 0">
        <legend>Get EDICT files</legend>
        <div>
            <progress max="100" id="download-edict"></progress>
            <label for="download-edict">Download EDICT</label>
        </div>
        <div>
            <progress max="100" id="download-enamdict"></progress>
            <label for="download-enamdict">Download ENAMDICT</label>
        </div>
        <div>
            <progress max="100" id="index-edict"></progress>
            <label for="index-edict">Index EDICT</label>
        </div>
        <div>
            <progress max="100" id="index-enamdict"></progress>
            <label for="index-enamdict">Index ENAMDICT</label>
        </div>
    </fieldset>
    <style>
    #getedict>div { text-align:left; margin:5px; }
    #getedict label { width:300px; }
    #getedict progress { width:300px; height:20px; }
    </style>
    """
        return ret

    def progress_edict(self, download, index):
        page = mw.web.page()
        if hasattr(page, 'runJavaScript'):  # Qt 5
            page.runJavaScript(f'document.querySelectorAll("#download-edict").forEach(function(e) {{ e.value = "{download * 100:.0f}"; }});')
            page.runJavaScript(f'document.querySelectorAll("#index-edict").forEach(function(e) {{ e.value = "{index * 100:.0f}"; }});')
        else:  # Qt 4
            document = page.currentFrame().documentElement()
            document.findFirst('#download-edict').setAttribute('value', f'{download * 100:.0f}')
            document.findFirst('#index-edict').setAttribute('value', f'{index * 100:.0f}')
        mw.web.update()


    def progress_enamdict(self, download, index):
        page = mw.web.page()
        if hasattr(page, 'runJavaScript'):  # Qt 5
            page.runJavaScript(f'document.querySelectorAll("#download-enamdict").forEach(function(e) {{ e.value = "{download * 100:.0f}"; }});')
            page.runJavaScript(f'document.querySelectorAll("#index-enamdict").forEach(function(e) {{ e.value = "{index * 100:.0f}"; }});')
        else:  # Qt 4
            document = page.currentFrame().documentElement()
            document.findFirst('#download-enamdict').setAttribute('value', f'{download * 100:.0f}')
            document.findFirst('#index-enamdict').setAttribute('value', f'{index * 100:.0f}')
        mw.web.update()

    def failed(self):
        self.undisplay()
        showInfo('Failed to download EDICT files.')

    def complete_edict(self):
        self.edict_done = True
        if self.enamdict_done:
            self.complete()

    def complete_enamdict(self):
        self.enamdict_done = True
        if self.edict_done:
            self.complete()

    def complete(self):
        self.undisplay()
        self.callback()

    def auto(self, callback=None):
        # check whether all necessary files already exists
        if all(os.path.isfile(filename) for filename in [default_edict, default_enamdict, default_edict_index, default_enamdict_index]):
            callback()
            return

        msg = 'Search EDICT needs do download dictionaries and build indexes. Up to 13 MiB of data may be downloaded. Proceed?'
        if not askUser(msg):
            return

        # callback will be called once both EDICT and ENAMDICT are ready
        self.callback = callback
        self.display()

        self.get_edict_thread = GetEDICTThread()
        self.get_edict_thread.progress.connect(self.progress_edict)
        self.get_edict_thread.failed.connect(self.failed)
        self.get_edict_thread.completed.connect(self.complete_edict)
        self.get_edict_thread.start()

        self.get_enamdict_thread = GetENAMDICTThread()
        self.get_enamdict_thread.progress.connect(self.progress_enamdict)
        self.get_enamdict_thread.failed.connect(self.failed)
        self.get_enamdict_thread.completed.connect(self.complete_enamdict)
        self.get_enamdict_thread.start()
