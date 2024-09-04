from anki.hooks import addHook
from aqt import mw
from aqt.browser import Browser
from aqt.qt import QAction

from .quickadd import QuickAddModule
from .searchwindow import SearchWindow


def add_menu_entries_to_browser(self: Browser) -> None:
    menu = self.form.menuEdit
    menu.addSeparator()

    action = QAction('Browse EDICT...', mw)
    action.triggered.connect(lambda: SearchWindow.open())
    menu.addAction(action)


def main() -> None:
    addHook('browser_menus_did_init', add_menu_entries_to_browser)
    QuickAddModule().display()


main()
