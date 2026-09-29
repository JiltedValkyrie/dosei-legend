"""Fail before mastering a disc that exceeds the SDK directory table."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check(root, capacity):
    # ISO '.' and '..' entries also occupy directory records.
    for directory in [root] + [p for p in root.rglob('*') if p.is_dir()]:
        count = len(list(directory.iterdir())) + 2
        if count > capacity:
            raise ValueError('%s: %d directory entries exceed capacity %d' %
                             (directory, count, capacity))


if __name__ == '__main__':
    capacity = int(re.search(r'#define JO_FS_MAX_FILES (\d+)',
                            (ROOT / 'src/fs_capacity.h').read_text())[1])
    check(ROOT / 'build/cd', capacity)
    print('Disc directory fits %d-entry filesystem table' % capacity)
