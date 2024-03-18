import os
import time
import gzip
from urllib.request import urlopen

from .search import default_edict, default_enamdict

# data source
edict_url = 'http://ftp.edrdg.org/pub/Nihongo/edict2.gz'
enamdict_url = 'http://ftp.edrdg.org/pub/Nihongo/enamdict.gz'


def fetch(url, out_file, progress_callback=None, progress_step=2**-6):
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
    progress_callback(1.)

    return True


def extract(in_file, out_file, progress_callback=None, progress_step=2**-6):
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
    progress_callback(1.)


def atomic_fetch(url, filename, progress_callback=None, progress_step=2**-6):
    # fetch in temporary file
    temp_filename = filename + '.tmp'
    with open(temp_filename, 'wb') as temp_file:
        if not fetch(url, temp_file, progress_callback, progress_step):
            return False
    # atomatically move into destination
    os.rename(temp_filename, filename)
    return True


def atomic_extract(in_filename, out_filename, progress_callback=None, progress_step=2**-6):
    # extract into temporary file
    temp_filename = out_filename + '.tmp'
    with open(in_filename, 'rb') as in_file, open(temp_filename, 'wb') as temp_file:
        extract(in_file, temp_file, progress_callback, progress_step)
    # atomatically move into destination
    os.rename(temp_filename, out_filename)


def fetch_and_extract(url, filename, progress_callback=None, progress_step=2**-6):
    # do nothing is file already exists
    if os.path.isfile(filename):
        return

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


def fetch_edict(url=edict_url, filename=default_edict, progress_callback=None, progress_step=2**-6):
    return fetch_and_extract(url, filename, progress_callback, progress_step)


def fetch_enamdict(url=enamdict_url, filename=default_enamdict, progress_callback=None, progress_step=2**-6):
    return fetch_and_extract(url, filename, progress_callback, progress_step)
