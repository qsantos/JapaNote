[Anki add-on](https://ankiweb.net/shared/info/171148684) to quickly make notes for Japanese vocabulary.

Type a word (in kanji, kana or romaji, possibly conjugated) in the field below the deck list, and press Enter: JapaNote
creates a note with its kanji, kana, furigana, definition and JMdict ID. When several words match, it lets you pick.
When no word matches, it looks for a proper noun; and for text that is in neither dictionary, such as a sentence, it
guesses the furigana and lets you check them before adding the note. To browse the results without adding anything,
including proper nouns that are also common words, use the Search button.

## Dictionaries

The add-on does not ship any dictionary. On first start, it downloads the main dictionary (about 20 MB); the names
dictionary (about 35 MB) and the sentence analyzer (about 20 MB) are downloaded the first time they are needed. The
dictionaries are then updated in the background, at most once a day. Everything is stored in the add-on's
`user_files` folder.

The dictionaries are built every week by [a workflow](.github/workflows/dictionaries.yml) running
[tools/build_dictionaries.py](tools/build_dictionaries.py), and published as assets of the
[dictionaries release](https://github.com/qsantos/JapaNote/releases/tag/dictionaries). Each one is an SQLite database
that is ready to query, so nothing is parsed when Anki starts.

## Cards in different decks

Each card type of a note type can go to its own deck (e.g. spelling cards in a separate deck): set it in the settings
of JapaNote, or as the Deck Override of the card type in Anki.

## Development

```sh
# build the dictionaries locally (about a minute)
python3 tools/build_dictionaries.py download sources
python3 tools/build_dictionaries.py build sources dist http://127.0.0.1:8000
mkdir db && for name in jmdict names; do gunzip -c dist/$name-*.sqlite.gz > db/$name.sqlite; done

# run the tests
JAPANOTE_DB_DIR=db uv run pytest

# use local dictionaries in Anki
(cd dist && python3 -m http.server 8000) &
JAPANOTE_MANIFEST_URL=http://127.0.0.1:8000/manifest-v1.json anki

# package the add-on
make -C japanote package
```

The add-on must stay compatible with Python 3.9, which Anki 24.06 to 25.02 ship.

## Credits

- [JMdict](https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project),
  [JMnedict](https://www.edrdg.org/enamdict/enamdict_doc.html) and
  [KANJIDIC2](https://www.edrdg.org/wiki/index.php/KANJIDIC_Project) are the property of the
  [Electronic Dictionary Research and Development Group](https://www.edrdg.org/), and are used in conformance with
  the Group's [licence](https://www.edrdg.org/edrdg/licence.html) (CC BY-SA 4.0)
- furigana from [JmdictFurigana](https://github.com/Doublevil/JmdictFurigana) (CC BY-SA 4.0)
- JLPT levels from [Jonathan Waller's lists](http://www.tanos.co.uk/jlpt/) (CC BY), matched to JMdict by
  [yomitan-jlpt-vocab](https://github.com/stephenmk/yomitan-jlpt-vocab) (CC BY-SA 4.0)
- the pitch accent notation was provided by Uros O. through his free database
  [Kanjium](https://github.com/mifunetoshiro/kanjium) (CC BY-SA 4.0)
- sentences are analyzed with [Janome](https://github.com/mocobeta/janome) (Apache 2.0) and the IPA dictionary
- romaji conversion by [python-romkan](https://github.com/soimort/python-romkan), a port of Ruby/Romkan by Satoru
  Takabayashi (Ruby's licence)
