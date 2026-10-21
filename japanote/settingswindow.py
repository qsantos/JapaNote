from __future__ import annotations

import os
from typing import Any

from anki.decks import DeckId
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from . import config, resources
from .collection import get_collection
from .view import window_to_front

CURRENT_DECK = '(current deck)'
NO_OVERRIDE = '(same as above)'
EXAMPLES = {
    'kanji': '暗記',
    'kana': 'あんき',
    'furigana': '暗[あん]記[き]',
    'definition': 'memorization',
    'id': 'EntL1586910',
    'pitch': 'あ‾んき',
    'audio': '[sound:…] (when available)',
}


def credits() -> str:
    versions = []
    for name, dictionary in resources.DICTIONARIES.items():
        if os.path.exists(dictionary.path):
            versions.append(f'{name} {dictionary.version()}')
    installed = f'<p>Installed dictionaries: {", ".join(versions)}</p>' if versions else ''
    return (
        '<p>Uses <a href="https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project">JMdict</a>, '
        '<a href="https://www.edrdg.org/enamdict/enamdict_doc.html">JMnedict</a> and '
        '<a href="https://www.edrdg.org/wiki/index.php/KANJIDIC_Project">KANJIDIC2</a>, '
        'property of the <a href="https://www.edrdg.org/">Electronic Dictionary Research and Development '
        'Group</a>, used in conformance with the Group\'s <a href="https://www.edrdg.org/edrdg/licence.html">'
        'licence</a> (CC BY-SA 4.0); furigana from '
        '<a href="https://github.com/Doublevil/JmdictFurigana">JmdictFurigana</a> (CC BY-SA 4.0); '
        'JLPT levels from <a href="http://www.tanos.co.uk/jlpt/">Jonathan Waller</a> (CC BY), matched by '
        '<a href="https://github.com/stephenmk/yomitan-jlpt-vocab">yomitan-jlpt-vocab</a> (CC BY-SA 4.0); '
        'the pitch accent notation was provided by Uros O. through his free database '
        '<a href="https://github.com/mifunetoshiro/kanjium">Kanjium</a> (CC BY-SA 4.0); '
        'technical words from <a href="https://ja.wikipedia.org/">Wikipedia</a> (CC BY-SA 4.0); '
        'recordings from <a href="https://lingualibre.org/">Lingua Libre</a> (mostly CC BY-SA 4.0); '
        'sentences analyzed with the IPA dictionary (© Nara Institute of Science and Technology), as compiled '
        f'by <a href="https://github.com/mocobeta/janome">Janome</a> (Apache 2.0).</p>{installed}'
    )


class CreditsWindow(QDialog):
    instance: CreditsWindow | None = None

    @classmethod
    def open(cls) -> None:
        if cls.instance is None:
            cls.instance = cls()
            cls.instance.show()
        else:
            window_to_front(cls.instance)

    def __init__(self) -> None:
        QDialog.__init__(self)
        self.setWindowTitle('JapaNote credits')
        layout = QVBoxLayout(self)
        label = QLabel(credits())
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        # NOTE: a word-wrapped label needs a width, or Qt makes it narrow and very tall
        label.setMinimumWidth(500)
        layout.addWidget(label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()


class SettingsWindow(QDialog):
    instance: SettingsWindow | None = None

    @classmethod
    def open(cls) -> None:
        if cls.instance is None:
            cls.instance = cls()
            cls.instance.show()
        else:
            window_to_front(cls.instance)

    def __init__(self) -> None:
        QDialog.__init__(self)
        self.setWindowTitle('JapaNote settings')
        col = get_collection()
        self.config = config.get()
        self.config['configured'] = True
        config.save(self.config)

        self.deck_names = sorted(deck.name for deck in col.decks.all_names_and_ids())
        model_names = sorted(model.name for model in col.models.all_names_and_ids())

        layout = QVBoxLayout(self)
        # grow the window when rows appear (e.g. the warning, or more card types)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.addWidget(QLabel('How new notes should be created:'))
        # labels, then inputs, all of the same width, then examples
        self.grid = QGridLayout()
        self.grid.setColumnStretch(1, 1)
        layout.addLayout(self.grid)

        self.deck_box = self.combobox([CURRENT_DECK, *self.deck_names], self.config['deck'] or CURRENT_DECK)
        self.deck_box.currentTextChanged.connect(self.on_change_deck)
        self.add_row('Deck', self.deck_box)

        self.model_box = self.combobox(model_names, self.config['model'])
        self.model_box.currentTextChanged.connect(self.on_change_model)
        self.add_row('Note type', self.model_box)

        self.field_boxes: dict[str, QComboBox] = {}
        for role, label in config.FIELDS.items():
            box = QComboBox()
            box.currentTextChanged.connect(lambda text, role=role: self.on_change_field(role, text))
            self.field_boxes[role] = box
            self.add_row(label, box, f'e.g. {EXAMPLES[role]}')

        self.tags = QLineEdit(self.config['tags'])
        self.tags.textChanged.connect(self.on_change_tags)
        self.add_row('Tags', self.tags)
        self.tag_jlpt = self.checkbox('Tag the JLPT level (e.g. JLPT::N3)', 'tag_jlpt')
        self.add_row('', self.tag_jlpt, columns=2)
        self.tag_common = self.checkbox('Tag common words (common)', 'tag_common')
        self.add_row('', self.tag_common, columns=2)

        # NOTE: not word-wrapped, since Qt then underestimates the height of the window, and squishes it
        self.no_id_warning = QLabel(
            'We advise you to save the JMdict ID in a field, so that duplicates\n'
            'are detected, and notes can be updated later.',
        )
        self.no_id_warning.setStyleSheet('color: #c00')
        self.grid.addWidget(self.no_id_warning, self.grid.rowCount(), 0, 1, 3)

        # deck overrides are stored in the card templates, so they also apply to Anki's Add window
        heading = QLabel('Decks of the cards (deck override of each card type):')
        heading.setContentsMargins(0, 10, 0, 0)
        self.grid.addWidget(heading, self.grid.rowCount(), 0, 1, 3)
        # the rows of the card types, replaced when the note type changes
        self.template_widgets: list[QWidget] = []

        layout.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        credits_button = buttons.addButton('Credits…', QDialogButtonBox.ButtonRole.HelpRole)
        assert credits_button is not None
        credits_button.clicked.connect(CreditsWindow.open)
        layout.addWidget(buttons)

        # select a note type when there is none yet
        self.on_change_model(self.model_box.currentText())

    def combobox(self, items: list[str], current: str) -> QComboBox:
        box = QComboBox()
        box.addItems(items)
        if current in items:
            box.setCurrentIndex(items.index(current))
        return box

    def checkbox(self, text: str, option: str) -> QCheckBox:
        box = QCheckBox(text)
        box.setChecked(self.config[option])
        box.toggled.connect(lambda checked: self.on_change_option(option, checked))
        return box

    def add_row(self, label: str, widget: QWidget, example: str = '', columns: int = 1) -> list[QWidget]:
        """Add a row to the grid, and return its widgets"""
        row = self.grid.rowCount()
        widgets = [QLabel(label), widget]
        self.grid.addWidget(widgets[0], row, 0)
        self.grid.addWidget(widget, row, 1, 1, columns)
        if example:
            example_label = QLabel(example)
            example_label.setStyleSheet('color: gray')
            self.grid.addWidget(example_label, row, 2)
            widgets.append(example_label)
        return widgets

    def on_change_deck(self, text: str) -> None:
        self.config['deck'] = '' if text == CURRENT_DECK else text
        config.save(self.config)

    def on_change_model(self, model_name: str) -> None:
        col = get_collection()
        self.config['model'] = model_name
        model = col.models.by_name(model_name)
        field_names = [''] + ([field['name'] for field in model['flds']] if model else [])
        for role, box in self.field_boxes.items():
            current = self.config['fields'][role]
            box.blockSignals(True)
            box.clear()
            box.addItems(field_names)
            box.setCurrentIndex(field_names.index(current) if current in field_names else 0)
            box.blockSignals(False)
            self.config['fields'][role] = box.currentText()
        config.save(self.config)
        self.update_warning()
        self.update_templates(model)

    def on_change_field(self, role: str, text: str) -> None:
        self.config['fields'][role] = text
        config.save(self.config)
        self.update_warning()

    def on_change_tags(self, text: str) -> None:
        self.config['tags'] = text
        config.save(self.config)

    def on_change_option(self, key: str, value: bool) -> None:
        self.config[key] = value
        config.save(self.config)

    def update_warning(self) -> None:
        self.no_id_warning.setVisible(not self.config['fields']['id'])

    def update_templates(self, model: dict[str, Any] | None) -> None:
        for widget in self.template_widgets:
            self.grid.removeWidget(widget)
            widget.deleteLater()
        self.template_widgets = []
        if model is None:
            return
        col = get_collection()
        for template in model['tmpls']:
            deck = col.decks.get(DeckId(template.get('did') or 0), default=False)
            current = deck['name'] if deck else NO_OVERRIDE
            box = self.combobox([NO_OVERRIDE, *self.deck_names], current)
            box.currentTextChanged.connect(
                lambda text, name=template['name']: self.on_change_template_deck(name, text),
            )
            self.template_widgets.extend(self.add_row(template['name'], box))

    def on_change_template_deck(self, template_name: str, deck_name: str) -> None:
        col = get_collection()
        model = col.models.by_name(self.config['model'])
        if model is None:
            return
        for template in model['tmpls']:
            if template['name'] == template_name:
                template['did'] = None if deck_name == NO_OVERRIDE else col.decks.id_for_name(deck_name)
        col.models.update_dict(model)

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
