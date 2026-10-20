"""Settings, stored in the collection so that they follow it across devices"""
from __future__ import annotations

from typing import Any

from .collection import get_collection

KEY = 'japanote'
# field role → label in the settings
FIELDS = {
    'kanji': 'Put kanji in',
    'kana': 'Put kana in',
    'furigana': 'Put furigana in',
    'definition': 'Put definition in',
    'id': 'Put JMdict ID in',
}
# settings of JapaNote 1 (stored in col.conf); they are copied, but kept for older versions
OLD_KEYS = {
    'japanote_kanjiField': 'kanji',
    'japanote_kanaField': 'kana',
    'japanote_furiganaField': 'furigana',
    'japanote_definitionField': 'definition',
    'japanote_idField': 'id',
}


def default() -> dict[str, Any]:
    return {
        # whether the user has looked at the settings
        'configured': False,
        # name of the deck, or '' for the current deck
        'deck': '',
        # name of the note type
        'model': '',
        # field role (see FIELDS) → name of the field, or '' to leave it out
        'fields': dict.fromkeys(FIELDS, ''),
    }


def get() -> dict[str, Any]:
    config = default()
    config.update(get_collection().get_config(KEY, {}))
    config['fields'] = {**default()['fields'], **config['fields']}
    return config


def save(config: dict[str, Any]) -> None:
    get_collection().set_config(KEY, config)


def migrate() -> None:
    """Import the settings of JapaNote 1, once"""
    col = get_collection()
    if col.get_config(KEY, None) is not None:
        return
    if not col.get_config('japanote_hasopensettings', False):
        return
    config = default()
    config['configured'] = True
    config['deck'] = col.get_config('japanote_deck', '') or ''
    config['model'] = col.get_config('japanote_model', '') or ''
    for old_key, role in OLD_KEYS.items():
        config['fields'][role] = col.get_config(old_key, '') or ''
    save(config)
