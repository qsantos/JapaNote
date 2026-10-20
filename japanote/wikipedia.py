"""Look up terms that are in no dictionary (e.g. technical words) on the Japanese Wikipedia"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .download import USER_AGENT

API = 'https://ja.wikipedia.org/w/api.php'
# text with these is a sentence rather than a term
SENTENCE_PUNCTUATION = re.compile(r'[。、！？!?\s]')
MAX_TERM_LENGTH = 30
# the reading in parentheses after the title at the start of the article,
# e.g. "機械学習（きかいがくしゅう、英: machine learning）とは" or "量子コンピュータ （りょうしコンピュータ、英: …"
READING = re.compile(r'\s*[（(]\s*([ぁ-ゟ゠-ヿ・ 　]+?)\s*[、，,）)]')


@dataclass
class Article:
    title: str
    # None when the article does not give it
    reading: str | None
    # title of the English article, if any
    english: str | None
    # first sentence of the article
    summary: str
    url: str
    # whether text was redirected to an article with another title
    redirected: bool


def looks_like_term(text: str) -> bool:
    return len(text) <= MAX_TERM_LENGTH and not SENTENCE_PUNCTUATION.search(text)


def parse_reading(title: str, extract: str) -> str | None:
    # usually at the start, but not always (e.g. "数学における微分幾何学（びぶんきかがく、…")
    start = extract.find(title)
    if start == -1:
        return None
    match = READING.match(extract, start + len(title))
    if match is None:
        return None
    return re.sub(r'[・ 　]', '', match.group(1))


def lookup(text: str) -> Article | None:
    params = {
        'action': 'query',
        'titles': text,
        'redirects': '1',
        'prop': 'extracts|langlinks|pageprops|info',
        'exintro': '1',
        'explaintext': '1',
        'exsentences': '1',
        'lllang': 'en',
        'inprop': 'url',
        'format': 'json',
        'formatversion': '2',
    }
    request = urllib.request.Request(f'{API}?{urllib.parse.urlencode(params)}', headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)['query']
    page = result['pages'][0]
    if page.get('missing') or page.get('invalid') or 'disambiguation' in page.get('pageprops', {}):
        return None
    extract = page.get('extract', '')
    langlinks = page.get('langlinks', [])
    return Article(
        title=page['title'],
        reading=parse_reading(page['title'], extract),
        # without the precision of the title, e.g. "Morphological analysis (problem-solving)"
        english=re.sub(r' \(.*\)$', '', langlinks[0]['title']) if langlinks else None,
        summary=extract,
        url=page['fullurl'],
        redirected=bool(result.get('redirects') or result.get('normalized')),
    )
