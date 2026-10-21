# Testing in a real Anki

`run.sh` starts Anki with a new profile, and the add-on with an extra add-on, `harness.py`, which
uses it as a user would, and checks the results:

- the settings of JapaNote 1 are migrated;
- the dictionary is downloaded at startup, with the progress shown below the input field;
- the deck of each card type can be set in the settings, and the credits window opens;
- words are added, with their tags, pitch accent, example sentence, kanji details and audio
  (downloaded from Lingua Libre), without duplicates, including of the notes added by JapaNote 1;
- a word with several matches opens the search window;
- a proper noun downloads the names dictionary, then is added;
- a sentence, or a word only on Wikipedia, opens the preview;
- typing in the input field of the deck browser adds a word;
- pasting a list of words in it opens the window to add them;
- an update of the dictionaries downloads only the patches;
- the interface never freezes for more than 300 ms.

Anki runs offscreen, with another user name, so that it does not interfere with an Anki already
running. It takes a few minutes, and needs an internet connection, for the audio and Wikipedia.

## Running

1. Build the dictionaries, with the address where `run.sh` serves them as base URL:

   ```sh
   python tools/build_dictionaries.py download sources
   python tools/build_dictionaries.py build sources dist http://127.0.0.1:18765
   ```

   The first time, `run.sh` adds a newer version to `dist` (see `make_update.py`), to test the
   update.

2. Run it with the executable of Anki, e.g. that of the launcher (Anki 25.07 and later):

   ```sh
   tools/e2e/run.sh ~/.local/share/AnkiProgramFiles/.venv/bin/anki dist
   ```

   Or an extracted release from https://github.com/ankitects/anki/releases (e.g. 24.06, the oldest
   version supported), whose bundled Python cannot be used to create the profile; any Python with
   Anki installed can, e.g. that of the launcher:

   ```sh
   ANKI_PYTHON=~/.local/share/AnkiProgramFiles/.venv/bin/python \
       tools/e2e/run.sh anki-24.06.3-linux-qt6/anki dist
   ```

It prints the log of the harness, and fails if a check failed. The Anki base directory is kept
(its path is printed), with the logs of Anki and of the server, and screenshots of the progress
bars, of the window to add several words, and of the preview of a note.

Set `JAPANOTE_E2E_PORT` to use another port than 18765 (and build with the matching base URL).

## Screenshots

`screenshots.py` is another add-on driving JapaNote, which takes the screenshots of its listing on AnkiWeb (the main
screen, the preview, a card, the search, the list of words, the settings, and a sentence with its furigana), in a note type with every field that
JapaNote fills; set `JAPANOTE_SCREENSHOTS_THEME=dark` for the dark theme:

```sh
JAPANOTE_E2E_HARNESS=tools/e2e/screenshots.py tools/e2e/run.sh ~/.local/share/AnkiProgramFiles/.venv/bin/anki dist
```
