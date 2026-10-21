# mypy: disable-error-code="union-attr, arg-type"
"""Create an Anki base directory with a profile 'test', set up for the add-on

Run with the Python of the Anki under test.

Usage:
    python make_profile.py BASE_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path

from anki.collection import Collection
from anki.notes import Note
from aqt.profiles import ProfileManager


def main() -> None:
    if len(sys.argv) != len(['make_profile.py', 'BASE_DIR']):
        sys.exit(__doc__)
    base = sys.argv[1]
    profiles = ProfileManager(Path(base))
    profiles.setupMeta()
    profiles.setLang('en_US')
    profiles.create('test')
    # no dialog about new versions of Anki, which would block the test
    profiles.set_update_check(False)
    profiles.db.execute('UPDATE profiles SET data = ? WHERE name = ?', profiles._pickle(profiles.meta), '_global')
    profiles.db.commit()

    (Path(base) / 'test').mkdir()
    col = Collection(f'{base}/test/collection.anki2')
    models = col.models
    model = models.new('Japanese')
    for field in ['Expression', 'Reading', 'Furigana', 'Meaning', 'ID']:
        models.add_field(model, models.new_field(field))
    for name, question in [('Recognition', '{{Expression}}'), ('Spelling', '{{Reading}}')]:
        template = models.new_template(name)
        template['qfmt'] = question
        template['afmt'] = '{{Furigana}}<br>{{Meaning}}'
        models.add_template(model, template)
    models.add(model)
    col.decks.id('Vocab')
    col.decks.id('Spelling')
    # the settings of JapaNote 1, which the add-on migrates
    settings = {
        'japanote_hasopensettings': True,
        'japanote_deck': 'Vocab',
        'japanote_model': 'Japanese',
        'japanote_kanjiField': 'Expression',
        'japanote_kanaField': 'Reading',
        'japanote_furiganaField': 'Furigana',
        'japanote_definitionField': 'Meaning',
        'japanote_idField': 'ID',
    }
    for key, value in settings.items():
        col.set_config(key, value)
    # a note added by JapaNote 1, with its IDs (with an X suffix)
    note = Note(col, models.by_name('Japanese'))
    note['Expression'] = '暗記'
    note['ID'] = 'EntL1586910X'
    col.add_note(note, col.decks.id('Vocab'))
    col.close()


if __name__ == '__main__':
    main()
