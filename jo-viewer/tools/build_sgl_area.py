#!/usr/bin/env python
"""Generate a project-local SGL work area (SGLAREA) with a raised polygon limit.

The stock ../../joengine/Compiler/COMMON/SGL_302j/LIB_ELF/SGLAREA.O caps the
scene at MaxPolygons=1761, so the Kokiri scene's 2060-polygon list is refused
outright by slPutPolygon. This rebuilds the area with a larger limit.

How it works
------------
SGLAREA.O is a pure data object: one SLPROG section, no relocations (verified
with objdump -r). Its first 0x40 bytes are a header of absolute pointers and
sizes, declared in SGL_302j/INC/SL_DEF.H under "System Work Assignments".
The graphics buffers themselves live OUTSIDE the object, in the top of work
RAM, reachable only through those pointers -- which is why nothing but this
header has to change. We copy the SDK object and patch the header in place, so
symbol names and offsets are untouched and the shared SDK is never written to.

Buffer sizing, derived from the stock header and confirmed exactly against the
shipped values (see verify_stock_layout):

    SortList   = 12 * (MaxPolygons + 6)   12-byte SCU DMA indirect entries
    SpriteBuf  = 72 * (MaxPolygons + 5)   72 bytes allocated per polygon
    Pbuffer    = 16 * MaxVertices         point calculate buffer
    Zbuffer    = (128 + 128 + 256) * 4    fixed, per SL_DEF.H
    CLOfstBuf  = 32 * 32 required         stock allocates 3072, we keep that
    CommandBuf   no exported size and no clean per-polygon stride, so it is
                 scaled by the polygon ratio with margin rather than guessed.
                 UNVERIFIED: a static view does not exercise it. Watch for
                 submission failures during camera motion.

These are the ALLOCATION formulas, read off the stock header's own layout.
They say how many bytes each buffer gets per polygon or vertex; they do not
establish how SGL consumes them. Nothing here was traced into LIBSGL.A, so
no claim is made about single- vs multi-buffering.
    TransList, MasterStack  kept at their stock sizes

Buffers are laid out contiguously ending at 0x06100000 (top of work RAM), the
same way the stock area does, so TransList and MasterStack keep their original
addresses and only the growing buffers move down. The resulting base address is
the new ceiling for .bss -- check_boundary() compares it against the linker map.
"""

import argparse
import pathlib
import struct
import sys

# Offsets within the SLPROG section, from SL_DEF.H's declaration order.
FIELDS = {
    'MasterStack':   (0x00, 'I'),
    'SlaveStack':    (0x04, 'I'),
    'MaxVertices':   (0x08, 'H'),
    'MaxPolygons':   (0x0A, 'H'),
    'SortList':      (0x0C, 'I'),
    'SortListSize':  (0x10, 'I'),
    'TransList':     (0x14, 'I'),
    'Zbuffer':       (0x18, 'I'),
    'SpriteBuf':     (0x1C, 'I'),
    'SpriteBufSize': (0x20, 'I'),
    'Pbuffer':       (0x24, 'I'),
    'CommandBuf':    (0x28, 'I'),
    'CLOfstBuf':     (0x2C, 'I'),
    'PCM_Work':      (0x30, 'I'),
    'PCM_WkSize':    (0x34, 'I'),
    'MaxEvents':     (0x38, 'H'),
    'EventSize':     (0x3A, 'H'),
    'MaxWorks':      (0x3C, 'H'),
    'WorkSize':      (0x3E, 'H'),
}

# File offset of the SLPROG section inside SGLAREA.O (objdump -h: File off 0x40).
SLPROG_FILE_OFFSET = 0x40

WORK_RAM_END = 0x06100000       # top of the 1 MB high work RAM
ALIGN = 32                      # every buffer is 32-byte aligned in the stock area

# The stock area, used both as the source object and as a self-check.
STOCK = dict(MaxPolygons=1761, MaxVertices=2500, SortList=0x060C0000,
             SortListSize=21204, CLOfstBuf=0x060C52D4, Zbuffer=0x060C5ED4,
             SpriteBuf=0x060C66D4, SpriteBufSize=127152, Pbuffer=0x060E5784,
             CommandBuf=0x060EF3C4, TransList=0x060FB800,
             MasterStack=0x060FFC00)

# Buffers in address order, with how each is sized.
CLOFST_BYTES = 3072             # 32*32 required; stock over-allocates, keep it
ZBUFFER_BYTES = (128 + 128 + 256) * 4
TRANSLIST_BYTES = 0x060FFC00 - 0x060FB800
MASTERSTACK_BYTES = WORK_RAM_END - 0x060FFC00
STOCK_COMMANDBUF_BYTES = 0x060FB800 - 0x060EF3C4


def read_header(blob):
    out = {}
    for name, (off, fmt) in FIELDS.items():
        out[name] = struct.unpack_from('>' + fmt, blob, SLPROG_FILE_OFFSET + off)[0]
    return out


def verify_stock_layout(head):
    """Refuse to run if the SDK object is not the area these formulas describe."""
    mp, mv = head['MaxPolygons'], head['MaxVertices']
    problems = []
    if (mp, mv) != (STOCK['MaxPolygons'], STOCK['MaxVertices']):
        problems.append('limits are %d/%d, expected %d/%d'
                        % (mp, mv, STOCK['MaxPolygons'], STOCK['MaxVertices']))
    if head['SortListSize'] != 12 * (mp + 6):
        problems.append('SortListSize %d != 12*(MaxPolygons+6)' % head['SortListSize'])
    if head['SpriteBufSize'] != 72 * (mp + 5):
        problems.append('SpriteBufSize %d != 72*(MaxPolygons+5)' % head['SpriteBufSize'])
    if head['CommandBuf'] - head['Pbuffer'] != 16 * mv:
        problems.append('Pbuffer span != 16*MaxVertices')
    if head['SpriteBuf'] - head['Zbuffer'] != ZBUFFER_BYTES:
        problems.append('Zbuffer span != (128+128+256)*4')
    for name, addr in (('SortList', STOCK['SortList']),
                       ('MasterStack', STOCK['MasterStack'])):
        if head[name] != addr:
            problems.append('%s is %#x, expected %#x' % (name, head[name], addr))
    if problems:
        sys.exit('SGLAREA.O is not the expected SGL 3.02j area:\n  '
                 + '\n  '.join(problems))


def plan(max_polygons, max_vertices, commandbuf_margin):
    """Lay buffers out contiguously, ending at the top of work RAM."""
    commandbuf = int(STOCK_COMMANDBUF_BYTES * commandbuf_margin
                     * max_polygons / STOCK['MaxPolygons'])
    commandbuf = (commandbuf + ALIGN - 1) // ALIGN * ALIGN
    sizes = [
        ('SortList',    12 * (max_polygons + 6)),
        ('CLOfstBuf',   CLOFST_BYTES),
        ('Zbuffer',     ZBUFFER_BYTES),
        ('SpriteBuf',   72 * (max_polygons + 5)),
        ('Pbuffer',     16 * max_vertices),
        ('CommandBuf',  commandbuf),
        ('TransList',   TRANSLIST_BYTES),
        ('MasterStack', MASTERSTACK_BYTES),
    ]
    sizes = [(n, (s + ALIGN - 1) // ALIGN * ALIGN) for n, s in sizes]
    total = sum(s for _, s in sizes)
    base = WORK_RAM_END - total
    if base % ALIGN:
        sys.exit('layout base %#x is not %d-byte aligned' % (base, ALIGN))

    layout, addr = [], base
    for name, size in sizes:
        layout.append((name, addr, size))
        addr += size
    if addr != WORK_RAM_END:
        sys.exit('layout ends at %#x, expected %#x' % (addr, WORK_RAM_END))
    return base, total, layout


def check_layout(layout, base):
    """Alignment, ordering and overlap over the whole reserved region."""
    previous_end = base
    for name, addr, size in layout:
        if addr % ALIGN:
            sys.exit('%s at %#x is not %d-byte aligned' % (name, addr, ALIGN))
        if addr != previous_end:
            sys.exit('%s at %#x leaves a gap/overlap after %#x'
                     % (name, addr, previous_end))
        if size <= 0:
            sys.exit('%s has non-positive size %d' % (name, size))
        previous_end = addr + size
    if previous_end != WORK_RAM_END:
        sys.exit('region ends at %#x, expected %#x' % (previous_end, WORK_RAM_END))


def patch(blob, layout, max_polygons, max_vertices):
    out = bytearray(blob)
    addrs = {name: addr for name, addr, _ in layout}

    def put(name, value):
        off, fmt = FIELDS[name]
        struct.pack_into('>' + fmt, out, SLPROG_FILE_OFFSET + off, value)

    put('MaxPolygons', max_polygons)
    put('MaxVertices', max_vertices)
    for name in ('SortList', 'CLOfstBuf', 'Zbuffer', 'SpriteBuf', 'Pbuffer',
                 'CommandBuf', 'TransList', 'MasterStack'):
        put(name, addrs[name])
    put('SortListSize', 12 * (max_polygons + 6))
    put('SpriteBufSize', 72 * (max_polygons + 5))
    return bytes(out)


def check_boundary(map_path, base, fatal):
    """The whole point of the reserved boundary: .bss must end below it.

    During generation the linker map is from the *previous* build, so a
    collision there is only advisory. Re-run with --verify after linking to
    turn it into a hard failure against the map that was just produced.
    """
    if not map_path.is_file():
        return None
    end = None
    for line in map_path.read_text(errors='ignore').splitlines():
        if '_end' in line.split() or line.strip().startswith('0x') and ' _end' in line:
            for token in line.split():
                if token.startswith('0x'):
                    end = int(token, 16)
            if end:
                break
    if end is None:
        return None
    if end > base:
        message = ('.bss ends at %#x, above the SGL work area base %#x -- free '
                   'static RAM (e.g. lower JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC) by '
                   'at least %d bytes' % (end, base, end - base))
        if fatal:
            sys.exit('boundary: ' + message)
        print('boundary: WARNING (stale map, recheck after linking) ' + message)
        return end
    return end


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=pathlib.Path,
                    default=root.parent.parent / 'joengine' / 'Compiler' / 'COMMON'
                    / 'SGL_302j' / 'LIB_ELF' / 'SGLAREA.O')
    ap.add_argument('--out', type=pathlib.Path,
                    default=root / 'generated' / 'sglarea.o')
    ap.add_argument('--max-polygons', type=int, default=2100)
    ap.add_argument('--max-vertices', type=int, default=2500)
    ap.add_argument('--commandbuf-margin', type=float, default=1.10)
    ap.add_argument('--map', type=pathlib.Path, default=root / 'game.map')
    ap.add_argument('--verify', action='store_true',
                    help='fail if the linker map collides with the work area; '
                         'run this after linking')
    args = ap.parse_args()

    blob = args.source.read_bytes()
    stock = read_header(blob)
    verify_stock_layout(stock)

    base, total, layout = plan(args.max_polygons, args.max_vertices,
                               args.commandbuf_margin)
    check_layout(layout, base)

    if not args.verify:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(patch(blob, layout, args.max_polygons,
                                   args.max_vertices))

    print('source  : %s (untouched)' % args.source)
    print('limits  : MaxPolygons %d -> %d, MaxVertices %d -> %d'
          % (stock['MaxPolygons'], args.max_polygons,
             stock['MaxVertices'], args.max_vertices))
    print('layout  : %#010x .. %#010x  (%d bytes, %+d vs stock)'
          % (base, WORK_RAM_END, total, total - (WORK_RAM_END - STOCK['SortList'])))
    for name, addr, size in layout:
        print('    %-12s %#010x  %7d' % (name, addr, size))
    bss_end = check_boundary(args.map, base, args.verify)
    if bss_end is None:
        print('boundary: no linker map yet; rerun with --verify after a build')
    elif bss_end <= base:
        print('boundary: .bss ends %#010x, %d bytes below the work area'
              % (bss_end, base - bss_end))
    if not args.verify:
        print('out     : %s' % args.out)


if __name__ == '__main__':
    main()
