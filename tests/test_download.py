from __future__ import annotations

import hashlib
import os
import sqlite3
from typing import TYPE_CHECKING, Any

import pytest

from japanote.download import DownloadError, Progress, install_database, patch_chain, update_database
from japanote.package import write_package, write_patch

if TYPE_CHECKING:
    from pathlib import Path

FORMAT = 1


def make_database(path: Path, version: str, words: dict[int, str]) -> str:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;
        CREATE TABLE word (id INTEGER PRIMARY KEY, text TEXT NOT NULL);
    """)
    db.executemany('INSERT INTO meta VALUES (?, ?)', [('version', version), ('format', str(FORMAT))])
    db.executemany('INSERT INTO word VALUES (?, ?)', words.items())
    db.commit()
    db.close()
    return str(path)


def words(path: str) -> dict[int, str]:
    db = sqlite3.connect(path)
    try:
        return dict(db.execute('SELECT id, text FROM word'))
    finally:
        db.close()


def published(path: Path) -> dict[str, Any]:
    """What the manifest says about a file"""
    data = path.read_bytes()
    return {'url': path.as_uri(), 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


# many words, so that the patches are smaller than the packages
COMMON = {i: f'言葉{i}' for i in range(10, 2000)}
VERSIONS = {
    '1': {**COMMON, 1: '猫', 2: '犬'},
    '2': {**COMMON, 1: '猫', 2: '犬', 3: '鳥'},
    '3': {**COMMON, 1: '猫', 3: '鳥', 4: '魚'},
}


@pytest.fixture
def release(tmp_path: Path) -> dict[str, Any]:
    """The packages of each version, and the patches from each version to the next"""
    sources = tmp_path / 'sources'
    sources.mkdir()
    for version, content in VERSIONS.items():
        make_database(sources / f'{version}.sqlite', version, content)
        write_package(str(sources / f'{version}.sqlite'), str(sources / f'{version}.xz'), {})
    for old, new in [('1', '2'), ('2', '3')]:
        patch = str(sources / f'{old}-{new}.xz')
        write_patch(str(sources / f'{old}.sqlite'), str(sources / f'{new}.sqlite'), patch, {})
    return {
        'packages': {version: published(sources / f'{version}.xz') for version in VERSIONS},
        'patches': [
            {'from': old, 'to': new, **published(sources / f'{old}-{new}.xz')}
            for old, new in [('1', '2'), ('2', '3')]
        ],
    }


def prepared(path: str, progress: Progress | None) -> None:
    """Stands for create_indexes"""
    db = sqlite3.connect(path)
    db.execute("INSERT INTO meta VALUES ('prepared', 'yes')")
    db.commit()
    db.close()
    if progress is not None:
        progress(1, 1)


def updated_indexes(path: str, changes: dict[str, list[tuple[Any, ...]]]) -> None:
    """Stands for update_indexes"""


def install(release: dict[str, Any], tmp_path: Path, version: str) -> str:
    path = str(tmp_path / 'dictionary.sqlite')
    package = release['packages'][version]
    os.replace(install_database(package['url'], package['sha256'], path, FORMAT, prepared), path)
    return path


def leftovers(tmp_path: Path) -> list[str]:
    return sorted(name for name in os.listdir(tmp_path) if name.startswith('dictionary.sqlite.'))


def test_install(release: dict[str, Any], tmp_path: Path) -> None:
    steps: list[tuple[str, float]] = []
    package = release['packages']['1']
    path = str(tmp_path / 'dictionary.sqlite')
    new = install_database(package['url'], package['sha256'], path, FORMAT, prepared, lambda *a: steps.append(a))
    assert new == path + '.new'
    assert words(new) == VERSIONS['1']
    assert list(dict.fromkeys(step for step, _ in steps)) == ['download', 'build']
    assert steps[-1] == ('build', 1)
    assert leftovers(tmp_path) == ['dictionary.sqlite.new']


def test_install_replaces_stale_copy(release: dict[str, Any], tmp_path: Path) -> None:
    # e.g. left by Anki being closed while the previous version was being prepared
    path = str(tmp_path / 'dictionary.sqlite')
    make_database(tmp_path / 'dictionary.sqlite.new', '0', {9: '古'})
    package = release['packages']['1']
    new = install_database(package['url'], package['sha256'], path, FORMAT, prepared)
    assert words(new) == VERSIONS['1']


def test_install_corrupted(release: dict[str, Any], tmp_path: Path) -> None:
    package = release['packages']['1']
    path = str(tmp_path / 'dictionary.sqlite')
    with pytest.raises(DownloadError, match='corrupted'):
        install_database(package['url'], '0' * 64, path, FORMAT, prepared)
    assert leftovers(tmp_path) == []


def test_install_wrong_format(release: dict[str, Any], tmp_path: Path) -> None:
    package = release['packages']['1']
    path = str(tmp_path / 'dictionary.sqlite')
    with pytest.raises(DownloadError, match='format'):
        install_database(package['url'], package['sha256'], path, FORMAT + 1, prepared)
    assert leftovers(tmp_path) == []


def test_patch_chain(release: dict[str, Any]) -> None:
    patches = release['patches']
    assert patch_chain(patches, '1', '3') == patches
    assert patch_chain(patches, '2', '3') == patches[1:]
    assert patch_chain(patches, '3', '3') == []
    # too old: the patches from it are no longer published
    assert patch_chain(patches, '0', '3') is None
    assert patch_chain(patches[1:], '1', '3') is None


def update(release: dict[str, Any], path: str, version: str, patches: list[dict[str, Any]]) -> str:
    info = {**release['packages']['3'], 'patches': patches}
    calls: list[str] = []

    def prepare(path: str, progress: Progress | None) -> None:
        calls.append('prepare')
        prepared(path, progress)

    def update_indexes(_path: str, _changes: dict[str, list[tuple[Any, ...]]]) -> None:
        calls.append('update_indexes')

    new = update_database(info, path, version, '3', FORMAT, prepare, update_indexes)
    assert words(new) == VERSIONS['3']
    # whether the update ended up downloading the full package
    return 'package' if 'prepare' in calls else 'patches'


def test_update_with_patches(release: dict[str, Any], tmp_path: Path) -> None:
    path = install(release, tmp_path, '1')
    make_database(tmp_path / 'dictionary.sqlite.new', '0', {9: '古'})  # stale copy
    assert update(release, path, '1', release['patches']) == 'patches'
    assert words(path) == VERSIONS['1']  # the caller replaces it
    assert leftovers(tmp_path) == ['dictionary.sqlite.new']


def test_update_without_chain(release: dict[str, Any], tmp_path: Path) -> None:
    path = install(release, tmp_path, '1')
    assert update(release, path, '1', release['patches'][1:]) == 'package'


def test_update_patches_larger_than_package(release: dict[str, Any], tmp_path: Path) -> None:
    path = install(release, tmp_path, '1')
    patches = [{**patch, 'size': release['packages']['3']['size']} for patch in release['patches']]
    assert update(release, path, '1', patches) == 'package'


@pytest.mark.parametrize('broken', ['sha256', 'url', 'from'])
def test_update_broken_patch(release: dict[str, Any], tmp_path: Path, broken: str) -> None:
    path = install(release, tmp_path, '1')
    patches = [dict(patch) for patch in release['patches']]
    if broken == 'sha256':
        patches[1]['sha256'] = '0' * 64
    elif broken == 'url':
        patches[1]['url'] = (tmp_path / 'missing.xz').as_uri()
    else:
        # the patch does not apply to the version it claims to (e.g. the database was modified)
        patches[1]['url'], patches[1]['sha256'] = patches[0]['url'], patches[0]['sha256']
    assert update(release, path, '1', patches) == 'package'
    assert words(path) == VERSIONS['1']
    assert leftovers(tmp_path) == ['dictionary.sqlite.new']


def test_update_fails(release: dict[str, Any], tmp_path: Path) -> None:
    # neither the patches nor the package can be downloaded: the database is left as it was
    path = install(release, tmp_path, '1')
    info = {**release['packages']['3'], 'sha256': '0' * 64, 'patches': []}
    with pytest.raises(DownloadError):
        update_database(info, path, '1', '3', FORMAT, prepared, updated_indexes)
    assert words(path) == VERSIONS['1']
    assert leftovers(tmp_path) == []
