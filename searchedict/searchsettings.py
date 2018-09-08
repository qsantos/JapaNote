# encoding: utf-8
from aqt import mw
from aqt.qt import *

from .view import formsettings, window_to_front, set_combobox_from_config

class SearchSettingsWindow(QDialog):
    instance = None

    @classmethod
    def open(cls):
        if cls.instance is None:
            cls.instance = cls()
        else:
            window_to_front(cls.instance)
        return cls.instance

    def closeEvent(self, evt):
        type(self).instance = None
        self.hide()
        evt.accept()

    def __init__(self):
        QDialog.__init__(self)
        self.form = formsettings.Ui_searchEdictSettings()
        self.form.setupUi(self)

        mw.col.conf['searchedict_hasopensettings'] = True
        mw.col.setMod()

        decks = sorted(mw.col.decks.allNames())
        models = sorted(mw.col.models.allNames())

        self.form.deckBox.addItems(decks)
        self.form.modelBox.addItems(models)
        self.form.closeButton.clicked.connect(self.close)

        # restore state from configuration
        # deck
        set_combobox_from_config(self.form.deckBox, decks, 'searchedict_deck')
        # model
        set_combobox_from_config(self.form.modelBox, models, 'searchedict_model')
        self.update_fieldboxes()  # fill combo boxes for selected model
        self.update_warning()
        # field mapping
        model_name = mw.col.conf.setdefault('searchedict_model', models[0])
        model = mw.col.models.byName(model_name)
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def set_onChange_combobox(self, combobox, config_key):
        def _(combobox):
            def onChange():
                mw.col.conf[config_key] = combobox.currentText() if combobox.currentIndex() != 0 else None
                mw.col.setMod()
                self.update_warning()
            return onChange
        combobox.currentIndexChanged.connect(_(combobox))

    def onChangeModel(self):
        mw.col.conf['searchedict_model'] = self.form.modelBox.currentText()
        mw.col.setMod()
        self.update_fieldboxes()
        self.update_warning()

    def update_fieldboxes(self):
        model_name = mw.col.conf['searchedict_model']
        model = mw.col.models.byName(model_name)
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

    def update_warning(self):
        if mw.col.conf.get('searchedict_idField'):
            self.form.noidWarning.hide()
        else:
            self.form.noidWarning.show()
