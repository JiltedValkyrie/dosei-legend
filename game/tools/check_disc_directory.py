"""Guard Saturn GFS directory capacity, ISO 8.3 names and fs_low.c's keys.

fs_low.c keeps an ID-only GFS table and resolves names by exact packed keys
(two u32: six base-38 symbols, then five more plus a dot flag). File ids are
ISO directory positions, so the keys must be unique and strictly increasing
in mastered order. Run on the staging directory before mastering and with
--iso on the image afterwards.
"""
from pathlib import Path
import argparse
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
SECTOR = 2048


def symbol(c):
    if '0' <= c <= '9':
        return ord(c) - 48 + 1
    if 'A' <= c <= 'Z':
        return ord(c) - 65 + 11
    return 37 if c == '_' else None


def key(name):
    """Mirror of fs_key(); None when GFS lookups could never match."""
    base, dot, ext = name.partition('.')
    if not 1 <= len(base) <= 8 or len(ext) > 3:
        return None
    syms = [symbol(c) for c in base] + [0] * (8 - len(base))
    syms += [symbol(c) for c in ext] + [0] * (3 - len(ext))
    if None in syms:
        return None
    a = b = 0
    for v in syms[:6]:
        a = a * 38 + v
    for v in syms[6:]:
        b = b * 38 + v
    return a, b * 2 + (1 if dot else 0)


def capacity():
    text = (ROOT / 'src/fs_capacity.h').read_text()
    return int(re.search(r'#define DOSEI_FS_MAX_FILES (\d+)', text)[1])


def check(root, limit):
    # ISO '.' and '..' entries also occupy directory records.
    root_count = len(list(root.iterdir())) + 2
    for directory in [root] + [p for p in root.rglob('*') if p.is_dir()]:
        entries = list(directory.iterdir())
        count = len(entries) + 2
        if count > limit:
            raise ValueError('%s: %d directory entries exceed capacity %d' %
                             (directory, count, limit))
        keys = {}
        for entry in entries:
            # SEGA_GFS.H: GFS_FNAME_LEN=12. Use portable ISO 8.3 names;
            # mkisofs -full-iso9660-filenames does not expand Saturn GFS.
            pattern = r'[A-Za-z0-9_]{1,8}' if entry.is_dir() else r'[A-Za-z0-9_]{1,8}(?:\.[A-Za-z0-9_]{1,3})?'
            if not re.fullmatch(pattern, entry.name):
                raise ValueError('%s: filename exceeds Saturn GFS 8.3 contract' % entry)
            # The disc stores upper case; two staged names must not collide.
            disc = entry.name.upper() + ('' if entry.is_dir() or '.' in entry.name else '.')
            k = key(disc)
            if k is None:
                raise ValueError('%s: no exact directory key' % entry)
            if k in keys:
                raise ValueError('%s: directory key collides with %s' % (entry, keys[k]))
            keys[k] = entry.name
    return root_count


def iso_root_names(path):
    data = Path(path).read_bytes()
    pvd = data[16 * SECTOR:17 * SECTOR]
    if pvd[1:6] != b'CD001':
        raise ValueError('%s: no ISO primary volume descriptor' % path)
    root = pvd[156:190]
    extent, size = struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0]
    names, offset, end = [], extent * SECTOR, extent * SECTOR + size
    while offset < end:
        length = data[offset]
        if length == 0:  # records never cross a sector boundary
            offset = (offset // SECTOR + 1) * SECTOR
            continue
        ident = data[offset + 33:offset + 33 + data[offset + 32]]
        names.append(ident.decode('ascii').split(';')[0] if ident not in (b'\0', b'\1') else None)
        offset += length
    return names


def check_iso(path, limit):
    names = iso_root_names(path)
    if len(names) > limit:
        raise ValueError('%s: %d root entries exceed capacity %d' % (path, len(names), limit))
    if names[:2] != [None, None]:
        raise ValueError('%s: root does not start with . and ..' % path)
    previous = (0, 1)
    for name in names[2:]:
        k = key(name)
        if k is None or not previous < k:
            raise ValueError('%s: %r breaks exact directory key order' % (path, name))
        previous = k
    return len(names)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, help='verify a mastered image instead of staging')
    args = parser.parse_args()
    limit = capacity()
    if args.iso:
        print('ISO root: %d of %d entries, keys exact and ordered' % (check_iso(args.iso, limit), limit))
    else:
        print('Disc directory: %d of %d entries' % (check(ROOT / 'build/cd', limit), limit))
