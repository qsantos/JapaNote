#!/usr/bin/env python3
"""Publish a fake next version of the dictionaries built in DIST_DIR, with the patches to it

The entry of 猫 gets an extra meaning, so that the test can tell that the update was applied. The
manifest of the new version is written as manifest-newer.json, next to the manifest of the build.

Usage:
    make_update.py DIST_DIR BASE_URL
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import build_dictionaries as build

# 猫, in JMdict
CHANGED_ENTRY = 1467640
CHANGED_MEANING = 'updated by make_update.py'


def change(path: str, version: str) -> None:
    db = sqlite3.connect(path)
    db.execute("UPDATE meta SET value = ? WHERE key = 'version'", (version,))
    row = db.execute('SELECT data FROM entry WHERE id = ?', (CHANGED_ENTRY,)).fetchone()
    if row is not None:
        data = json.loads(row[0])
        data['s'][0]['g'].append(CHANGED_MEANING)
        db.execute('UPDATE entry SET data = ? WHERE id = ?', (json.dumps(data, ensure_ascii=False), CHANGED_ENTRY))
    db.commit()
    db.close()


def main() -> None:
    if len(sys.argv) != len(['make_update.py', 'DIST_DIR', 'BASE_URL']):
        sys.exit(__doc__)
    dist_dir, base_url = sys.argv[1], sys.argv[2].rstrip('/')
    package = build.load_module('package')
    with open(os.path.join(dist_dir, f'manifest-v{build.FORMAT}.json')) as f:
        manifest = json.load(f)
    version = str(int(manifest['version']) + 1)
    newer = {**manifest, 'version': version, 'dictionaries': {}}
    with tempfile.TemporaryDirectory() as tmp:
        old_paths = {}
        for name, info in manifest['dictionaries'].items():
            old_paths[name] = os.path.join(tmp, f'{name}-old.sqlite')
            package.read_package(os.path.join(dist_dir, os.path.basename(info['url'])), old_paths[name])
        db = sqlite3.connect(old_paths['jmdict'])
        size = int(dict(db.execute('SELECT key, value FROM analyzer'))['size'])
        db.close()
        encodings = build.encodings(size)
        for name, old_path in old_paths.items():
            new_path = os.path.join(tmp, f'{name}-new.sqlite')
            filename = os.path.basename(manifest['dictionaries'][name]['url'])
            package.read_package(os.path.join(dist_dir, filename), new_path)
            change(new_path, version)
            packaged = f'{name}-v{build.FORMAT}-{version}.xz'
            patched = f'{name}-v{build.FORMAT}-{manifest["version"]}-{version}.xz'
            package.write_package(new_path, os.path.join(dist_dir, packaged), encodings)
            package.write_patch(old_path, new_path, os.path.join(dist_dir, patched), encodings)

            def published(filename: str) -> dict[str, object]:
                path = os.path.join(dist_dir, filename)
                return {
                    'url': f'{base_url}/{filename}', 'size': os.path.getsize(path), 'sha256': build.sha256sum(path),
                }

            patch = {'from': manifest['version'], 'to': version, **published(patched)}
            newer['dictionaries'][name] = {**published(packaged), 'patches': [patch]}
            print(f'{name}: {packaged}, and {patched} ({patch["size"]} bytes)')
    with open(os.path.join(dist_dir, 'manifest-newer.json'), 'w') as f:
        json.dump(newer, f, indent=4)


if __name__ == '__main__':
    main()
