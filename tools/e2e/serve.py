#!/usr/bin/env python3
"""Serve DIST_DIR at about 2 MB/s, so that the progress of the downloads can be seen

Usage:
    serve.py DIST_DIR PORT
"""
from __future__ import annotations

import functools
import http.server
import sys
import time
from typing import IO


class Handler(http.server.SimpleHTTPRequestHandler):
    def copyfile(self, source: IO[bytes], outputfile: IO[bytes]) -> None:  # type: ignore[override]
        while chunk := source.read(1 << 16):
            outputfile.write(chunk)
            time.sleep(0.03)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f'serve.py: {format % args}\n')


def main() -> None:
    if len(sys.argv) != len(['serve.py', 'DIST_DIR', 'PORT']):
        sys.exit(__doc__)
    handler = functools.partial(Handler, directory=sys.argv[1])
    http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[2])), handler).serve_forever()


if __name__ == '__main__':
    main()
