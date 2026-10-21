[Anki add-on](https://ankiweb.net/shared/info/171148684) to quickly make notes for Japanese vocabulary.

Type a word (in kanji, kana or romaji, possibly conjugated) in the field below the deck list, and press Enter: JapaNote
creates a note with its kanji, kana, furigana, definition and JMdict ID, and tells which word it added (e.g. 食べる,
from 食べました, polite past). When several words match, it lets you pick.
When no word matches, it looks for a proper noun, then for an article of the Japanese Wikipedia (for technical words,
taking the reading from the article, and the definition from the title of the English article); for text that is in
none of those, such as a sentence, it guesses the furigana. Either way, it lets you check the note before adding it. To browse the results without adding anything,
including proper nouns that are also common words, use the Search button.

To add a list of words (e.g. the vocabulary of a lesson), paste it in the field, or use the Add several button, which
can also open a text or CSV file (taking its first column): each line is looked up, and you can check the matches, pick
another one when there are several, and skip the words that already have a note, before adding them all at once.

Optionally, notes can also get the pitch accent of the word, an example sentence with its translation (for about
29,000 words, from Tatoeba, with the word in bold), the meanings and readings of its kanji, and a recording by a
native speaker from [Lingua Libre](https://lingualibre.org/) when there is one (it is fetched in the background, and
added to the note a few seconds later). New notes are tagged `japanote` by default, as well as with their JLPT level (e.g. `JLPT::N3`)
and `common` for common words.

## Dictionaries

The add-on does not ship any dictionary. On first start, it downloads the main dictionary (about 10 MB, including the
data of the sentence analyzer); the names dictionary (about 5 MB) is downloaded the first time it is needed. The
dictionaries are then updated in the background, at most once a day. Everything is stored in the add-on's
`user_files` folder.

The dictionaries are built every week by [a workflow](.github/workflows/dictionaries.yml) running
[tools/build_dictionaries.py](tools/build_dictionaries.py), and published as assets of the
[dictionaries release](https://github.com/qsantos/JapaNote/releases/tag/dictionaries), in a format that compresses well
(see [japanote/package.py](japanote/package.py)). Once downloaded, each one is turned into an SQLite database, so
nothing is parsed when Anki starts.

To update the dictionaries, the add-on downloads patches, which only list the entries that changed since the version
that is installed, as long as they are smaller than the new version (e.g. about 50 KB for a thousand changed entries).

## Cards in different decks

Each card type of a note type can go to its own deck (e.g. spelling cards in a separate deck): set it in the settings
of JapaNote, or as the Deck Override of the card type in Anki.

## Development

```sh
# build the dictionaries locally (about a minute)
python3 tools/build_dictionaries.py download sources
python3 tools/build_dictionaries.py build sources dist http://127.0.0.1:8000
python3 tools/build_dictionaries.py install dist db

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
- example sentences from [Tatoeba](https://tatoeba.org/) (CC BY 2.0 FR), chosen with the index of the words they
  contain (originally from the Tanaka Corpus)
- readings and translations of technical words from [Wikipedia](https://ja.wikipedia.org/) (CC BY-SA 4.0)
- recordings from [Lingua Libre](https://lingualibre.org/), hosted on Wikimedia Commons (mostly CC BY-SA 4.0; the
  name of the speaker is kept in the name of the file)
- sentences are analyzed with the IPA dictionary (© Nara Institute of Science and Technology), as compiled by
  [Janome](https://github.com/mocobeta/janome) (Apache 2.0), whose algorithm is reproduced in `japanote/analyzer.py`
  (see [NOTICE-IPADIC.txt](NOTICE-IPADIC.txt))
- romaji conversion by [python-romkan](https://github.com/soimort/python-romkan), a port of Ruby/Romkan by Satoru
  Takabayashi (Ruby's licence)
