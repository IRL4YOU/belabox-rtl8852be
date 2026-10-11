#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Erzeugt das Quellarchiv mit gleichbleibenden Metadaten und Prüfsumme."""
import gzip
import hashlib
import io
from pathlib import Path
import re
import subprocess
import sys
import tarfile

BASE = Path(__file__).resolve().parent


def main():
    subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(BASE / 'tests'), '-v'], check=True)
    version = re.search(r"VERSION = '([^']+)'", (BASE / 'rtw89ctl.py').read_text()).group(1)
    files = [f for f in BASE.rglob('*') if f.is_file() and f.name != '.DS_Store' and
             not set(f.relative_to(BASE).parts).intersection({'dist', '__pycache__', '.git'})
             and f.suffix not in ('.o', '.ko', '.pyc')]
    if any(f.is_symlink() for f in files):
        raise RuntimeError('Keine Links im Paket erlaubt')
    destination = BASE / 'dist'
    destination.mkdir(exist_ok=True)
    archive = destination / ('belabox-rtw89-' + version + '.tar.gz')
    with archive.open('wb') as output, gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w', format=tarfile.USTAR_FORMAT) as tf:
            for file in sorted(files):
                data = file.read_bytes()
                info = tarfile.TarInfo('belabox-rtw89/' + file.relative_to(BASE).as_posix())
                info.mode = 0o755 if file.name in ('rtw89ctl.py', 'make_release.py') else 0o644
                info.uid = info.gid = info.mtime = 0
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + '.sha256').write_text(checksum + '  ' + archive.name + '\n')
    print('PAKET:', archive)
    print('SHA256:', checksum)


if __name__ == '__main__':
    main()
