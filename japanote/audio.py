"""Recordings of words by native speakers, from Lingua Libre (https://lingualibre.org/)

The recordings are hosted on Wikimedia Commons, with names like "LL-Q5287 (jpn)-Speaker-食べる.wav",
under free licenses (mostly CC BY-SA 4.0). Not every word has been recorded.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .download import USER_AGENT

COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
# Q5287 is the Wikidata item of the Japanese language
PREFIX = 'LL-Q5287 (jpn)-'


def commons_query(**params: str) -> Any:
    url = f'{COMMONS_API}?{urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})}'
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def find_recording(word: str) -> str | None:
    """Return the name of a file on Commons, with a recording of exactly this word"""
    result = commons_query(
        action='query',
        list='search',
        srnamespace='6',
        srlimit='50',
        srsearch=f'intitle:"{PREFIX.strip("-")}" intitle:"{word}"',
    )
    for page in result['query']['search']:
        name = page['title'].removeprefix('File:')
        # e.g. "LL-Q5287 (jpn)-Fukujinzuke-食べる.wav", but not "LL-Q5287 (jpn)-CKali-雄猫.wav" for 猫
        if name.startswith(PREFIX) and re.fullmatch(rf'[^-]+-{re.escape(word)}\.\w+', name[len(PREFIX):]):
            return str(name)
    return None


def download_recording(name: str) -> bytes:
    result = commons_query(action='query', titles=f'File:{name}', prop='imageinfo', iiprop='url')
    url = result['query']['pages'][0]['imageinfo'][0]['url']
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return bytes(response.read())


def fetch(words: list[str]) -> tuple[str, bytes] | None:
    """Find and download a recording of the first of words that has one, as (filename, data)"""
    for word in dict.fromkeys(words):
        name = find_recording(word)
        if name is not None:
            # keep the name of the speaker, for attribution, but avoid spaces and parentheses
            filename = 'japanote-' + re.sub(r'[^\w.-]+', '_', name)
            return filename, download_recording(name)
    return None
