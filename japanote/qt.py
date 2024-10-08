try:
    from PyQt5 import QtCore, QtGui
except ImportError:
    from PyQt6 import QtCore, QtGui  # type: ignore[import-not-found, no-redef]
    from . import searchwindow_qt6 as searchwindow
    from . import settingswindow_qt6 as settingswindow
else:
    from . import searchwindow_qt5 as searchwindow  # type: ignore[no-redef]
    from . import settingswindow_qt5 as settingswindow  # type: ignore[no-redef]
