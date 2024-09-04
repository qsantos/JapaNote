from typing import Callable

from aqt import mw
from aqt.qt import QComboBox, QDialog, Qt

from .collection import get_collection
from .qt import QtGui, settingswindow
from .view import set_combobox_from_config, window_to_front


class SettingsWindow(QDialog):
    instance = None

    @classmethod
    def open(cls) -> None:
        if cls.instance is None:
            cls.instance = cls()
        else:
            window_to_front(cls.instance)

    def closeEvent(self, evt: QtGui.QCloseEvent) -> None:
        type(self).instance = None
        self.hide()
        evt.accept()

    def __init__(self) -> None:
        QDialog.__init__(self)
        self.form = settingswindow.Ui_japaNoteSettings()
        self.form.setupUi(self)  # type: ignore[no-untyped-call]

        col = get_collection()

        col.conf['japanote_hasopensettings'] = True

        deck_names = sorted(deck.name for deck in col.decks.all_names_and_ids())
        model_names = sorted(model.name for model in col.models.all_names_and_ids())

        self.form.deckBox.addItems(deck_names)
        self.form.modelBox.addItems(model_names)
        self.form.closeButton.clicked.connect(self.close)

        # restore state from configuration
        # deck
        set_combobox_from_config(self.form.deckBox, deck_names, 'japanote_deck')
        # model
        set_combobox_from_config(self.form.modelBox, model_names, 'japanote_model')
        self.update_fieldboxes()  # fill combo boxes for selected model
        self.update_warning()
        # field mapping
        model_name = col.conf.setdefault('japanote_model', model_names[0])
        model = col.models.by_name(model_name)
        if model:
            field_names = [''] + [field['name'] for field in model['flds']]
            set_combobox_from_config(self.form.kanjiBox, field_names, 'japanote_kanjiField')
            set_combobox_from_config(self.form.kanaBox, field_names, 'japanote_kanaField')
            set_combobox_from_config(self.form.furiganaBox, field_names, 'japanote_furiganaField')
            set_combobox_from_config(self.form.definitionBox, field_names, 'japanote_definitionField')
            set_combobox_from_config(self.form.idBox, field_names, 'japanote_idField')

        # events
        self.set_onChange_combobox(self.form.deckBox, 'japanote_deck')
        self.form.modelBox.currentIndexChanged.connect(self.onChangeModel)
        self.set_onChange_combobox(self.form.kanjiBox, 'japanote_kanjiField')
        self.set_onChange_combobox(self.form.kanaBox, 'japanote_kanaField')
        self.set_onChange_combobox(self.form.furiganaBox, 'japanote_furiganaField')
        self.set_onChange_combobox(self.form.definitionBox, 'japanote_definitionField')
        self.set_onChange_combobox(self.form.idBox, 'japanote_idField')

        self.show()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def set_onChange_combobox(self, combobox: QComboBox, config_key: str) -> None:
        def _(combobox: QComboBox) -> Callable[[], None]:
            def onChange() -> None:
                col = get_collection()
                col.conf[config_key] = combobox.currentText()
                self.update_warning()
            return onChange
        combobox.currentIndexChanged.connect(_(combobox))

    def onChangeModel(self) -> None:
        col = get_collection()
        col.conf['japanote_model'] = self.form.modelBox.currentText()
        self.update_fieldboxes()
        self.update_warning()

    def update_fieldboxes(self) -> None:
        col = get_collection()
        model_name = col.conf['japanote_model']
        model = col.models.by_name(model_name)
        if not model:
            return
        field_names = [''] + [field['name'] for field in model['flds']]

        self.form.kanjiBox.clear()
        self.form.kanaBox.clear()
        self.form.furiganaBox.clear()
        self.form.definitionBox.clear()
        self.form.idBox.clear()

        self.form.kanjiBox.addItems(field_names)
        self.form.kanaBox.addItems(field_names)
        self.form.furiganaBox.addItems(field_names)
        self.form.definitionBox.addItems(field_names)
        self.form.idBox.addItems(field_names)

    def update_warning(self) -> None:
        col = get_collection()
        if col.conf.get('japanote_idField'):
            self.form.noidWarning.hide()
        else:
            self.form.noidWarning.show()
