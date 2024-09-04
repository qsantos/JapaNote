try:
    from PyQt6 import QtCore, QtGui # type: ignore[import-not-found]
except ImportError:
    from PyQt5 import QtCore, QtGui
    from . import searchwindow_qt5 as searchwindow
    from . import formsettings_qt5 as formsettings
else:
    from . import searchwindow_qt6 as searchwindow  # type: ignore[no-redef]
    from . import formsettings_qt6 as formsettings  # type: ignore[no-redef]
