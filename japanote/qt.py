try:
    from PyQt6 import QtCore, QtGui # type: ignore[import-not-found]
except ImportError:
    from PyQt5 import QtCore, QtGui
    from . import searchwindow_qt5 as searchwindow
    from . import settingswindow_qt5 as settingswindow
else:
    from . import searchwindow_qt6 as searchwindow  # type: ignore[no-redef]
    from . import settingswindow_qt6 as settingswindow  # type: ignore[no-redef]
