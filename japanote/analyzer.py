"""Split sentences into words, with their readings

This is the algorithm of Janome (https://github.com/mocobeta/janome), with its tie-breaking rules, so
that the results are exactly the same, but without what is not needed for readings: the data of the
IPA dictionary is stored in the main dictionary (see tools/build_dictionaries.py), instead of
being a separate 20 MB download.

The text is split into the sequence of words with the lowest cost, where each word has a cost (how
unlikely it is), and so has each pair of consecutive words (how unlikely they are to follow each
other, given their right and left context ids). Characters that are not in the dictionary form
unknown words, grouped by category (e.g. katakana).
"""
from __future__ import annotations

import json
import sys
from array import array
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from .kana import hiragana_to_katakana

if TYPE_CHECKING:
    import sqlite3

# longest dictionary word that is looked up
MAX_WORD_LENGTH = 50
# longest unknown word, for categories that group characters
MAX_UNKNOWN_LENGTH = 1024
INFINITY = 2**31 - 1


@dataclass
class Node:
    surface: str
    left_id: int
    right_id: int
    cost: int
    # number of the entry in the dictionary, None for unknown words
    num: int | None = None
    reading: str | None = None
    min_cost: int = INFINITY
    back: Node | None = None


class Analyzer:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        data = dict(db.execute('SELECT key, value FROM analyzer'))
        self.size = int(data['size'])
        self.connections = array('h')
        self.connections.frombytes(data['connections'])
        if sys.byteorder == 'big':
            self.connections.byteswap()
        # category → {'INVOKE': bool, 'GROUP': bool, 'LENGTH': int}
        self.categories: dict[str, dict[str, Any]] = json.loads(data['categories'])
        # [{'from': str, 'to': str, 'cate': str, 'compat_cates': [str]}]
        self.char_ranges: list[dict[str, Any]] = json.loads(data['char_ranges'])
        # category → [[left_id, right_id, cost]]
        self.unknowns: dict[str, list[list[int]]] = json.loads(data['unknowns'])
        self.char_categories = lru_cache(maxsize=1024)(self._char_categories)

    def _char_categories(self, c: str) -> dict[str, list[str]]:
        """The categories of c, with their compatible categories"""
        categories = {
            char_range['cate']: char_range.get('compat_cates', [])
            for char_range in self.char_ranges
            if char_range['from'] <= c <= char_range['to']
        }
        return categories or {'DEFAULT': []}

    def lookup(self, text: str) -> list[Node]:
        """The dictionary words that text starts with"""
        prefixes = [text[:i] for i in range(1, min(len(text), MAX_WORD_LENGTH) + 1)]
        query = f"""
            SELECT num, surface, left_id, right_id, cost, reading FROM token
            WHERE surface IN ({', '.join('?' * len(prefixes))}) ORDER BY num
        """
        return [
            # the reading is NULL when it is the surface in katakana
            Node(surface, left_id, right_id, cost, num, hiragana_to_katakana(surface) if reading is None else reading)
            for num, surface, left_id, right_id, cost, reading in self.db.execute(query, prefixes)
        ]

    def unknown_words(self, text: str, pos: int, matched: bool) -> list[Node]:
        nodes = []
        for category in self.char_categories(text[pos]):
            definition = self.categories.get(category, {})
            if matched and not definition.get('INVOKE', False):
                continue
            length = MAX_UNKNOWN_LENGTH if definition.get('GROUP', False) else definition.get('LENGTH', -1)
            end = pos + 1
            # NOTE: like Janome, this allows length + 1 characters
            while end < min(len(text), pos + length + 1):
                categories = self.char_categories(text[end])
                if category not in categories and not any(category in compat for compat in categories.values()):
                    break
                end += 1
            nodes.extend(
                Node(text[pos:end], left_id, right_id, cost)
                for left_id, right_id, cost in self.unknowns[category]
            )
        return nodes

    def connect(self, node: Node, previous: list[Node]) -> None:
        """Find the best previous node for node"""
        min_cost, best = node.min_cost - node.cost, None
        for candidate in previous:
            cost = candidate.min_cost + self.connections[candidate.right_id * self.size + node.left_id]
            if cost < min_cost or (
                # on a tie, prefer the first dictionary entry
                cost == min_cost and best is not None and best.num is not None
                and candidate.num is not None and candidate.num < best.num
            ):
                min_cost, best = cost, candidate
        node.min_cost = min_cost + node.cost
        node.back = best

    def tokenize(self, text: str) -> list[tuple[str, str | None]]:
        """Split text into (surface, reading) pairs; the reading is None when unknown"""
        text = text.strip()
        bos = Node('', 0, 0, 0, min_cost=0)
        # the nodes ending at each position
        ends: list[list[Node]] = [[] for _ in range(len(text) + 1)]
        ends[0].append(bos)
        pos = 0
        while pos < len(text):
            known = self.lookup(text[pos:])
            for node in known + self.unknown_words(text, pos, bool(known)):
                self.connect(node, ends[pos])
                ends[pos + len(node.surface)].append(node)
            # skip the positions where no word ends
            pos += 1
            while pos < len(text) and not ends[pos]:
                pos += 1
        eos = Node('', 0, 0, 0)
        self.connect(eos, ends[len(text)])

        tokens = []
        back = eos.back
        while back is not None and back is not bos:
            reading = None if back.reading == '*' else back.reading
            tokens.append((back.surface, reading))
            back = back.back
        tokens.reverse()
        return tokens
