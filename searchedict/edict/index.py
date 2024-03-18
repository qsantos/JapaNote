#!/usr/bin/env python
import re
import time
from collections import defaultdict

from .search import (
    Word,
    common_marker,
    default_edict,
    default_edict_index,
    default_enamdict,
    default_enamdict_index,
    edict_line_pattern,
)

byte_line_pattern = re.compile(b'(?m)^(.*)$')


def load_edict(filename, progress_callback=None, progress_step=2**-6):
    with open(filename, mode='rb') as f:
        edict_data = f.read()

    # prepare progress report
    if progress_callback is not None:
        size = float(len(edict_data))
        progress_callback(0.)
        last = time.time()

    edict = defaultdict(set)
    for match in byte_line_pattern.finditer(edict_data):
        # get byte offset of line
        offset = match.start()

        # parse line
        line = match.group(0).decode('euc_jp')
        match = edict_line_pattern.match(line)
        if not match:
            continue

        # gather information for new word
        line, writings, readings, glosses = match.groups()
        writings = common_marker.sub('', writings).split(';')
        readings = common_marker.sub('', readings).split(';') if readings else []
        word = Word(writings, readings, glosses, line, offset)

        # map writings and reading to word
        for key in writings + readings:
            edict[key].add(word)

        # report progress
        if progress_callback is not None:
            now = time.time()
            if now - last >= progress_step:
                progress_callback(offset / size / 2.)
                last = now

    # last report
    if progress_callback is not None:
        progress_callback(.5)

    return edict


def edict_to_index(edict, output_filename, progress_callback=None, progress_step=2**-6):
    if progress_callback is not None:
        size = float(len(edict))
        progress_callback(.5)
        last = time.time()

    with open(output_filename, 'wb') as f:
        for i, key in enumerate(sorted(edict)):
            words = edict[key]
            offsets = sorted(word.edict_offset for word in words)
            offsets = u' '.join(str(offset) for offset in offsets)
            line = u'{} {}\n'.format(key, offsets)
            f.write(line.encode('utf-8'))

            # report progress
            if progress_callback is not None:
                now = time.time()
                if now - last >= progress_step:
                    progress_callback(.5 + i / size / 2.)
                    last = now

    # last report
    if progress_callback is not None:
        progress_callback(1.)


def build_index(input_filename, output_filename, progress_callback=None, progress_step=2**-6):
    edict = load_edict(input_filename, progress_callback, progress_step)
    edict_to_index(edict, output_filename, progress_callback, progress_step)


if __name__ == '__main__':
    build_index(default_edict, default_edict_index)
    build_index(default_enamdict, default_enamdict_index)
