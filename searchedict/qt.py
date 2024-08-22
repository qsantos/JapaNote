try:
    from PyQt6 import QtCore, QtGui # type: ignore[import-not-found]
except ImportError:
    from PyQt5 import QtCore, QtGui
    from . import formbrowser_qt5 as formbrowser
    from . import formsettings_qt5 as formsettings
else:
    from . import formbrowser_qt6 as formbrowser  # type: ignore[no-redef]
    from . import formsettings_qt6 as formsettings  # type: ignore[no-redef]
