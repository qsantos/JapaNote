"""Pitch accent, shown as a line over the high morae, which drops after the accented one

For instance, はし is read with a high は then a low し when it means "chopsticks" (箸, accent 1), with
a low は then a high し that drops after the word when it means "bridge" (橋, accent 2), and with a
low は then a high し that stays high when it means "edge" (端, accent 0).
"""
from __future__ import annotations

from html import escape

# kana that do not form a mora by themselves, but with the previous one
SMALL_KANA = set('ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ')

HIGH_STYLE = 'border-top:1px solid'
DROP_STYLE = 'border-right:1px solid'


def split_morae(kana: str) -> list[str]:
    morae: list[str] = []
    for c in kana:
        if c in SMALL_KANA and morae:
            morae[-1] += c
        else:
            morae.append(c)
    return morae


def is_high(mora: int, accent: int) -> bool:
    """Whether the mora at this index is high, for a word with this accent"""
    if accent == 1:
        return mora == 0
    # heiban (0) and nakadaka/odaka: low first mora, then high until the accented mora
    return mora > 0 and (accent == 0 or mora < accent)


def pitch_html(kana: str, accent: int) -> str:
    morae = split_morae(kana)
    parts = []
    # group the morae into runs of the same pitch
    start = 0
    for end in range(1, len(morae) + 1):
        if end < len(morae) and is_high(end, accent) == is_high(start, accent):
            continue
        text = escape(''.join(morae[start:end]))
        if is_high(start, accent):
            # the pitch drops after the accented mora, even at the end of the word
            style = f'{HIGH_STYLE};{DROP_STYLE}' if accent and end == accent else HIGH_STYLE
            parts.append(f'<span style="{style}">{text}</span>')
        else:
            parts.append(text)
        start = end
    return ''.join(parts)


def pitches_html(kana: str, accents: list[int]) -> str:
    """All the possible pitch accents of a word"""
    return '・'.join(pitch_html(kana, accent) for accent in accents)
