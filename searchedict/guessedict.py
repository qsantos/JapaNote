from gettext import ngettext

from aqt import mw
from aqt.qt import QDialog, Qt
from aqt.utils import showInfo, tooltip
from PyQt5 import QtGui

from . import formguessids, furigana
from .edict2.search import edict
from .model import get_collection
from .view import immediate_redraw, set_combobox_from_config, window_to_front


class GuessEDICTWindow(QDialog):
    instance = None

    @classmethod
    def open(cls, parent):
        if cls.instance is None:
            cls.instance = cls(parent)
        else:
            window_to_front(cls.instance)
        return cls.instance

    def closeEvent(self, evt: QtGui.QCloseEvent) -> None:
        type(self).instance = None
        self.hide()
        evt.accept()

    def __init__(self, parent) -> None:
        QDialog.__init__(self)
        self.form = formguessids.Ui_Dialog()
        self.form.setupUi(self)

        self.form.guessButton.clicked.connect(self.on_click_guess_button)

        self.note_ids = parent.selected_notes()
        if not self.note_ids:
            showInfo('Please select cards first')
            self.close()
            return
        note_id = self.note_ids[0]
        col = get_collection()
        note = col.getNote(note_id)
        self.model = note.model()

        # restore state from configuration
        # model
        self.form.modelValue.setText(self.model['name'])
        self.update_fieldboxes()  # fill combo boxes for selected model
        self.update_enabled()
        # field mapping
        field_names = [''] + [field['name'] for field in self.model['flds']]
        set_combobox_from_config(self.form.kanjiBox, field_names, 'guessedict_kanjiField')
        set_combobox_from_config(self.form.kanaBox, field_names, 'guessedict_kanaField')
        set_combobox_from_config(self.form.furiganaBox, field_names, 'guessedict_furiganaField')
        set_combobox_from_config(self.form.definitionBox, field_names, 'guessedict_definitionField')
        set_combobox_from_config(self.form.idBox, field_names, 'guessedict_idField')

        # events
        self.set_onChange_combobox(self.form.kanjiBox, 'guessedict_kanjiField')
        self.set_onChange_combobox(self.form.kanaBox, 'guessedict_kanaField')
        self.set_onChange_combobox(self.form.furiganaBox, 'guessedict_furiganaField')
        self.set_onChange_combobox(self.form.definitionBox, 'guessedict_definitionField')
        self.set_onChange_combobox(self.form.idBox, 'guessedict_idField')

        self.show()

    def set_onChange_combobox(self, combobox, config_key) -> None:
        def _(combobox):
            def onChange():
                col = get_collection()
                col.conf[config_key] = combobox.currentText() if combobox.currentIndex() != 0 else None
                col.setMod()
                self.update_enabled()
            return onChange
        combobox.currentIndexChanged.connect(_(combobox))

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()

    def onChangeModel(self) -> None:
        col = get_collection()
        col.conf['guessedict_model'] = self.form.modelBox.currentText()
        col.setMod()
        self.update_fieldboxes()
        self.update_enabled()

    def update_fieldboxes(self) -> None:
        field_names = [''] + [field['name'] for field in self.model['flds']]

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

    def enough_fields_given(self) -> bool:
        col = get_collection()
        ok = False
        if col.conf.get('guessedict_kanjiField'):
            ok = True
        if col.conf.get('guessedict_kanField'):
            ok = True
        if col.conf.get('guessedict_furiganaField'):
            ok = True
        if not col.conf.get('guessedict_idField'):
            ok = False
        return ok

    def update_enabled(self) -> None:
        self.form.guessButton.setEnabled(self.enough_fields_given())

    def on_click_guess_button(self) -> None:
        self.form.guessButton.setText('Guessing...')
        immediate_redraw(self)
        self.guess()
        self.close()

    def guess(self) -> None:
        col = get_collection()

        # get field names
        kanji_field = col.conf.get('guessedict_kanjiField')
        kana_field = col.conf.get('guessedict_kanaField')
        furigana_field = col.conf.get('guessedict_furiganaField')
        definition_field = col.conf.get('guessedict_definitionField')
        id_field = col.conf.get('guessedict_idField')

        n_ignored = 0
        n_guessed = 0
        n_ambiguous = 0
        for note_id in self.note_ids:
            note = col.get_note(note_id)

            # gather information about kanji and kana
            kanji = None
            kana = None
            if furigana_field:
                kanji = furigana.kanji(note[furigana_field])
                kana = furigana.kana(note[furigana_field])
            elif kanji_field:
                kanji = note[kanji_field]
            elif kana_field:
                kana = note[furigana_field]

            # gather information about definition
            definition = None
            if definition_field:
                definition = note[definition_field]

            # search
            if kanji is not None:
                words = list(edict.search(kanji))
            elif kana is not None:
                words = list(edict.search(kana))
            else:
                raise NotImplementedError

            # filter words
            if kanji is not None:
                # or kanji == word.kanji ?
                words = [word for word in words if kanji in word.writings + word.readings]
            if kana is not None:
                # or kana == word.kana ?
                words = [word for word in words if kana in word.writings + word.readings]
            if definition is not None:
                words = [word for word in words if definition == word.get_meanings_html()]

            # updatenote
            if len(words) == 0:  # not in EDICT
                # can be found by filtering over id field
                n_ignored += 1
            elif len(words) == 1:
                word, = words
                note[id_field] = word.get_sequence_number()
                n_guessed += 1
            else:  # several matches
                note.addTag('ambiguous')
                n_ambiguous += 1
            note.flush()
        mw.reset()

        ignored = ngettext('{} card ignored.', '{} cards ignored.', n_ignored).format(n_ignored)
        guessed = ngettext('{} card ID guessed.', '{} card IDs guessed.', n_guessed).format(n_guessed)
        ambiguous = ngettext('{} card marked ambiguous.', '{} cards marked ambiguous.', n_ambiguous).format(n_ambiguous)
        tooltip('<br>'.join([ignored, guessed, ambiguous]))
