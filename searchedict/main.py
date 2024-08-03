from anki.hooks import addHook
from aqt import mw
from aqt.qt import *

from .getedict import GetEDICTModule
from .guessedict import GuessEDICTWindow
from .quickadd import QuickAddModule
from .searchedict import SearchEDICTWindow


def add_menu_entries_to_browser(self):
    menu = self.form.menuEdit
    menu.addSeparator()

    action = QAction('Browse EDICT...', mw)
    action.triggered.connect(lambda: SearchEDICTWindow.open())
    menu.addAction(action)

    action = QAction('Guess JMdict IDs of selected cards...', mw)
    action.triggered.connect(lambda _, parent=self: GuessEDICTWindow.open(parent))
    menu.addAction(action)


def enable_edict():
    addHook('browser.setupMenus', add_menu_entries_to_browser)
    QuickAddModule().display()


def main():
    GetEDICTModule().auto(enable_edict)


main()
