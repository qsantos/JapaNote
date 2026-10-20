from __future__ import annotations

from typing import Any

from aqt.qt import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import config
from .collection import get_collection
from .view import window_to_front

CURRENT_DECK = '(current deck)'
EXAMPLES = {
    'kanji': '暗記',
    'kana': 'あんき',
    'furigana': '暗[あん]記[き]',
    'definition': 'memorization',
    'id': 'EntL1586910',
}


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
        layout.addWidget(QLabel('How new notes should be created:'))
        form = QFormLayout()
        layout.addLayout(form)

        self.deck_box = self.combobox([CURRENT_DECK, *self.deck_names], self.config['deck'] or CURRENT_DECK)
        self.deck_box.currentTextChanged.connect(self.on_change_deck)
        form.addRow('Deck', self.deck_box)

        self.model_box = self.combobox(model_names, self.config['model'])
        self.model_box.currentTextChanged.connect(self.on_change_model)
        form.addRow('Note type', self.model_box)

        self.field_boxes: dict[str, QComboBox] = {}
        for role, label in config.FIELDS.items():
            box = QComboBox()
            box.currentTextChanged.connect(lambda text, role=role: self.on_change_field(role, text))
            self.field_boxes[role] = box
            form.addRow(label, self.with_example(box, EXAMPLES[role]))

        self.no_id_warning = QLabel(
            'We advise you to save the JMdict ID in a field, so that duplicates are detected, '
            'and notes can be updated later.',
        )
        self.no_id_warning.setWordWrap(True)
        self.no_id_warning.setStyleSheet('color: #c00')
        layout.addWidget(self.no_id_warning)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        # select a note type when there is none yet
        self.on_change_model(self.model_box.currentText())

    def combobox(self, items: list[str], current: str) -> QComboBox:
        box = QComboBox()
        box.addItems(items)
        if current in items:
            box.setCurrentIndex(items.index(current))
        return box

    def with_example(self, widget: QWidget, example: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(f'e.g. {example}')
        label.setStyleSheet('color: gray')
        layout.addWidget(widget, 1)
        layout.addWidget(label)
        return container

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

    def on_change_field(self, role: str, text: str) -> None:
        self.config['fields'][role] = text
        config.save(self.config)
        self.update_warning()

    def update_warning(self) -> None:
        self.no_id_warning.setVisible(not self.config['fields']['id'])

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: Any) -> None:
        type(self).instance = None
        event.accept()
