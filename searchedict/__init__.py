from anki.hooks import addHook
from aqt import mw
from aqt.browser import Browser
from aqt.qt import QAction

from .guessedict import GuessEDICTWindow
from .quickadd import QuickAddModule
from .searchedict import SearchEDICTWindow


def add_menu_entries_to_browser(self: Browser) -> None:
    menu = self.form.menuEdit
    menu.addSeparator()

    action = QAction('Browse EDICT...', mw)
    action.triggered.connect(lambda: SearchEDICTWindow.open())
    menu.addAction(action)

    action = QAction('Guess JMdict IDs of selected cards...', mw)
    action.triggered.connect(lambda _, parent=self: GuessEDICTWindow.open(parent))
    menu.addAction(action)


def main() -> None:
    addHook('browser_menus_did_init', add_menu_entries_to_browser)
    QuickAddModule().display()


main()
