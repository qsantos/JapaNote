"""Download and install the resources that are not shipped with the add-on

Everything is stored in user_files, which Anki keeps when updating the add-on. Files are first
downloaded and checked next to their final location, then moved into place in one step, so that an
interrupted download never leaves a broken file behind.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import urllib.request
from collections.abc import Callable
from typing import Any

USER_FILES = os.path.join(os.path.dirname(__file__), 'user_files')
USER_AGENT = 'JapaNote (https://github.com/qsantos/JapaNote)'
# called with the number of bytes downloaded so far, and the total
Progress = Callable[[int, int], None]


class DownloadError(Exception):
    pass


def user_file(name: str) -> str:
    os.makedirs(USER_FILES, exist_ok=True)
    return os.path.join(USER_FILES, name)


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download(url: str, path: str, sha256: str, progress: Progress | None = None) -> None:
    """Download url to path, and check its SHA-256"""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    digest = hashlib.sha256()
    part = path + '.part'
    try:
        with urllib.request.urlopen(request, timeout=30) as response, open(part, 'wb') as f:
            total = int(response.headers.get('Content-Length') or 0)
            done = 0
            while chunk := response.read(1 << 16):
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
        if digest.hexdigest() != sha256:
            msg = f'corrupted download from {url}'
            raise DownloadError(msg)
        os.replace(part, path)
    finally:
        if os.path.exists(part):
            os.remove(part)


def check_database(path: str, format_: int) -> None:
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        row = db.execute("SELECT value FROM meta WHERE key = 'format'").fetchone()
    finally:
        db.close()
    if row is None or int(row[0]) != format_:
        msg = 'unexpected dictionary format'
        raise DownloadError(msg)


def install_database(url: str, sha256: str, path: str, format_: int, progress: Progress | None = None) -> str:
    """Download a gzipped SQLite database, and return the path of the checked, uncompressed file

    The caller must move the returned file to path, once the previous database is closed.
    """
    compressed = path + '.gz'
    new = path + '.new'
    try:
        download(url, compressed, sha256, progress)
        with gzip.open(compressed, 'rb') as src, open(new, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        check_database(new, format_)
    except BaseException:
        if os.path.exists(new):
            os.remove(new)
        raise
    finally:
        if os.path.exists(compressed):
            os.remove(compressed)
    return new

