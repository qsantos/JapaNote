from aqt import mw
from aqt.qt import QDialog, Qt

from . import formsettings
from .view import set_combobox_from_config, window_to_front


class SearchSettingsWindow(QDialog):
    instance = None

    @classmethod
    def open(cls):
        if cls.instance is None:
            cls.instance = cls()
        else:
            window_to_front(cls.instance)
        return cls.instance

    def closeEvent(self, evt) -> None:
        type(self).instance = None
        self.hide()
        evt.accept()

    def __init__(self) -> None:
        QDialog.__init__(self)
        self.form = formsettings.Ui_searchEdictSettings()
        self.form.setupUi(self)

        mw.col.conf['searchedict_hasopensettings'] = True

        deck_names = sorted(deck.name for deck in mw.col.decks.all_names_and_ids())
        model_names = sorted(model.name for model in mw.col.models.all_names_and_ids())

        self.form.deckBox.addItems(deck_names)
        self.form.modelBox.addItems(model_names)
        self.form.closeButton.clicked.connect(self.close)

        # restore state from configuration
        # deck
        set_combobox_from_config(self.form.deckBox, deck_names, 'searchedict_deck')
        # model
        set_combobox_from_config(self.form.modelBox, model_names, 'searchedict_model')
        self.update_fieldboxes()  # fill combo boxes for selected model
        self.update_warning()
        # field mapping
        model_name = mw.col.conf.setdefault('searchedict_model', model_names[0])
        model = mw.col.models.by_name(model_name)
        if model:
            field_names = [''] + [field['name'] for field in model['flds']]
            set_combobox_from_config(self.form.kanjiBox, field_names, 'searchedict_kanjiField')
            set_combobox_from_config(self.form.kanaBox, field_names, 'searchedict_kanaField')
            set_combobox_from_config(self.form.furiganaBox, field_names, 'searchedict_furiganaField')
            set_combobox_from_config(self.form.definitionBox, field_names, 'searchedict_definitionField')
            set_combobox_from_config(self.form.idBox, field_names, 'searchedict_idField')

        # events
        self.set_onChange_combobox(self.form.deckBox, 'searchedict_deck')
        self.form.modelBox.currentIndexChanged.connect(self.onChangeModel)
        self.set_onChange_combobox(self.form.kanjiBox, 'searchedict_kanjiField')
        self.set_onChange_combobox(self.form.kanaBox, 'searchedict_kanaField')
        self.set_onChange_combobox(self.form.furiganaBox, 'searchedict_furiganaField')
        self.set_onChange_combobox(self.form.definitionBox, 'searchedict_definitionField')
        self.set_onChange_combobox(self.form.idBox, 'searchedict_idField')

        self.show()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()

    def set_onChange_combobox(self, combobox, config_key) -> None:
        def _(combobox):
            def onChange():
                mw.col.conf[config_key] = combobox.currentText()
                self.update_warning()
            return onChange
        combobox.currentIndexChanged.connect(_(combobox))

    def onChangeModel(self) -> None:
        mw.col.conf['searchedict_model'] = self.form.modelBox.currentText()
        self.update_fieldboxes()
        self.update_warning()

    def update_fieldboxes(self) -> None:
        model_name = mw.col.conf['searchedict_model']
        model = mw.col.models.by_name(model_name)
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
        if mw.col.conf.get('searchedict_idField'):
            self.form.noidWarning.hide()
        else:
            self.form.noidWarning.show()
