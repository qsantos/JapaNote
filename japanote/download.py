"""Download and install the resources that are not shipped with the add-on

Everything is stored in user_files, which Anki keeps when updating the add-on. Files are first
downloaded and checked next to their final location, then moved into place in one step, so that an
interrupted download never leaves a broken file behind.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import urllib.request
import zipfile
from collections.abc import Callable
from typing import Any

from .package import apply_patch, read_package

USER_FILES = os.path.join(os.path.dirname(__file__), 'user_files')
USER_AGENT = 'JapaNote (https://github.com/qsantos/JapaNote)'
# called with the number of bytes (or rows) processed so far, and the total
Progress = Callable[[int, int], None]
# called with what is being done ('download', then 'build'), and the fraction of it that is done
StepProgress = Callable[[str, float], None]


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


def install_database(  # noqa: PLR0913
    url: str,
    sha256: str,
    path: str,
    format_: int,
    prepare: Callable[[str, Progress | None], None],
    progress: StepProgress | None = None,
) -> str:
    """Download a package (see package.py), and return the path of the checked database built from it

    prepare is called with the path of the database (e.g. to build indexes), and a progress callback.
    The caller must move the returned file to path, once the previous database is closed.
    """
    compressed = path + '.xz'
    new = path + '.new'

    def step(name: str, start: float, end: float) -> Progress | None:
        """Report the progress of a step, as the part of the progress of name from start to end"""
        if progress is None:
            return None
        return lambda done, total: progress(name, start + (end - start) * (done / total if total else 0))

    try:
        download(url, compressed, sha256, step('download', 0, 1))
        if os.path.exists(new):
            os.remove(new)
        # each half takes about the same time
        read_package(compressed, new, step('build', 0, 0.5))
        check_database(new, format_)
        prepare(new, step('build', 0.5, 1))
    except BaseException:
        if os.path.exists(new):
            os.remove(new)
        raise
    finally:
        if os.path.exists(compressed):
            os.remove(compressed)
    return new


def patch_chain(patches: list[dict[str, Any]], version: str, target: str) -> list[dict[str, Any]] | None:
    """The patches that update a database from version to target, in order, if there are"""
    by_origin = {patch['from']: patch for patch in patches}
    chain = []
    while version != target:
        patch = by_origin.get(version)
        if patch is None:
            return None
        chain.append(patch)
        version = patch['to']
    return chain


def patch_database(
    patches: list[dict[str, Any]],
    path: str,
    format_: int,
    update_indexes: Callable[[str, dict[str, list[tuple[Any, ...]]]], None],
) -> str:
    """Apply patches to a copy of the database at path, and return the path of the copy (see install_database)"""
    new = path + '.new'
    downloaded = path + '.patch'
    try:
        shutil.copyfile(path, new)
        for patch in patches:
            download(patch['url'], downloaded, patch['sha256'])
            update_indexes(new, apply_patch(downloaded, new))
        check_database(new, format_)
    except BaseException:
        if os.path.exists(new):
            os.remove(new)
        raise
    finally:
        if os.path.exists(downloaded):
            os.remove(downloaded)
    return new


def update_database(  # noqa: PLR0913
    info: dict[str, Any],
    path: str,
    version: str,
    target: str,
    format_: int,
    prepare: Callable[[str, Progress | None], None],
    update_indexes: Callable[[str, dict[str, list[tuple[Any, ...]]]], None],
) -> str:
    """Update a database from version to target, with patches when they are smaller than the new package

    Return the path of the new database (see install_database).
    """
    chain = patch_chain(info.get('patches', []), version, target)
    if chain is not None and sum(patch['size'] for patch in chain) < info['size']:
        try:
            return patch_database(chain, path, format_, update_indexes)
        except Exception as e:  # noqa: BLE001
            print(f'JapaNote: could not patch {path}, downloading it again: {e}')
    return install_database(info['url'], info['sha256'], path, format_, prepare)


def install_wheel(url: str, sha256: str, directory: str, progress: Progress | None = None) -> None:
    """Download a pure-Python wheel, and extract it to directory (to be added to sys.path)"""
    wheel = directory + '.whl'
    tmp = directory + '.tmp'
    try:
        download(url, wheel, sha256, progress)
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(wheel) as z:
            z.extractall(tmp)
        shutil.rmtree(directory, ignore_errors=True)
        os.replace(tmp, directory)
    finally:
        if os.path.exists(wheel):
            os.remove(wheel)
        shutil.rmtree(tmp, ignore_errors=True)
