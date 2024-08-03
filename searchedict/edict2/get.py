import gzip
import os
import time
from typing import BinaryIO, Callable, Optional
from urllib.request import urlopen

from .search import default_edict, default_enamdict

# data source
edict_url = 'http://ftp.edrdg.org/pub/Nihongo/edict2.gz'
enamdict_url = 'http://ftp.edrdg.org/pub/Nihongo/enamdict.gz'


def fetch(url: str, out_file: BinaryIO, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> bool:
    # prepare transfer
    request = urlopen(url)
    blocksize = 2**10

    # prepare progress reporting
    if progress_callback is not None:
        size = float(request.headers['Content-Length'])
        progress_callback(0.)
        last = time.time()

    done = 0.
    while True:
        # transfer a block of data
        data = request.read(blocksize)
        if not data:
            break
        out_file.write(data)
        done += len(data)

        # report progress
        if progress_callback is not None:
            now = time.time()
            if now - last >= progress_step:
                progress_callback(done / size)
                last = now

    # clean up
    request.close()

    if done != size:
        return False

    # last report
    if progress_callback is not None:
        progress_callback(1.)

    return True


def extract(in_file: BinaryIO, out_file: BinaryIO, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> None:
    # prepare extraction
    gzip_stream = gzip.GzipFile(mode='rb', fileobj=in_file)

    # prepare progress reporting
    blocksize = 2**10
    if progress_callback is not None:
        # get size of file
        offset = in_file.tell()
        in_file.seek(0, 2)
        size = float(in_file.tell()) - offset
        in_file.seek(offset, 0)

        progress_callback(0.)
        last = time.time()

    while True:
        # extract block
        data = gzip_stream.read(blocksize)
        if not data:
            break
        out_file.write(data)

        # report progress
        if progress_callback is not None:
            now = time.time()
            if now - last >= progress_step:
                progress_callback(in_file.tell() / size)
                last = now

    # last report
    if progress_callback is not None:
        progress_callback(1.)


def atomic_fetch(url: str, filename: str, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> bool:
    # fetch in temporary file
    temp_filename = filename + '.tmp'
    with open(temp_filename, 'wb') as temp_file:
        if not fetch(url, temp_file, progress_callback, progress_step):
            return False
    # atomatically move into destination
    os.rename(temp_filename, filename)
    return True


def atomic_extract(in_filename: str, out_filename: str, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> None:
    # extract into temporary file
    temp_filename = out_filename + '.tmp'
    with open(in_filename, 'rb') as in_file, open(temp_filename, 'wb') as temp_file:
        extract(in_file, temp_file, progress_callback, progress_step)
    # atomatically move into destination
    os.rename(temp_filename, out_filename)


def fetch_and_extract(url: str, filename: str, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> bool:
    # do nothing is file already exists
    if os.path.isfile(filename):
        return True

    # fetch compressed file
    gz_filename = filename + '.gz'
    if not os.path.isfile(gz_filename):
        if not atomic_fetch(url, gz_filename, progress_callback, progress_step):
            return False
    # extract file
    atomic_extract(gz_filename, filename, progress_callback, progress_step)
    # remove intermediate file
    os.remove(gz_filename)
    return True


def fetch_edict(url: str = edict_url, filename: str = default_edict, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> bool:
    return fetch_and_extract(url, filename, progress_callback, progress_step)


def fetch_enamdict(url: str = enamdict_url, filename: str = default_enamdict, progress_callback: Optional[Callable[[float], None]] = None, progress_step: float = 2**-6) -> bool:
    return fetch_and_extract(url, filename, progress_callback, progress_step)
