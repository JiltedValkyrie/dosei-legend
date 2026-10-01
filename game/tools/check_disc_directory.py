"""Guard Saturn GFS directory capacity and ISO 8.3 filenames before mastering."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check(root, capacity):
    # ISO '.' and '..' entries also occupy directory records.
    for directory in [root] + [p for p in root.rglob('*') if p.is_dir()]:
        entries=list(directory.iterdir())
        count = len(entries) + 2
        if count > capacity:
            raise ValueError('%s: %d directory entries exceed capacity %d' %
                             (directory, count, capacity))

        for entry in entries:
            # SEGA_GFS.H: GFS_FNAME_LEN=12. Use portable ISO 8.3 names;
            # mkisofs -full-iso9660-filenames does not expand Saturn GFS.
            pattern=r'[A-Za-z0-9_]{1,8}' if entry.is_dir() else r'[A-Za-z0-9_]{1,8}(?:\.[A-Za-z0-9_]{1,3})?'
            if not re.fullmatch(pattern,entry.name):
                raise ValueError('%s: filename exceeds Saturn GFS 8.3 contract' % entry)


if __name__ == '__main__':
    capacity = int(re.search(r'#define JO_FS_MAX_FILES (\d+)',
                            (ROOT / 'src/fs_capacity.h').read_text())[1])
    check(ROOT / 'build/cd', capacity)
    print('Disc directory fits %d-entry filesystem table' % capacity)
