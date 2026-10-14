#!/usr/bin/env python3
"""Fail when a linked placeholder table is not in its key-list order.

The draw shim keys a display list by its slot: (address - table start) / 8
(oot_core_draw.cpp Draw_Key). The mesh baker names meshes by position in
objects/O<id>_ph.txt and keep_ph.txt (build_core_meshes.py). GCC -Os emitted
these one-word variables in reverse source order (BUILD.md 124), so every
object/keep mesh key missed and those actors drew nothing (King Dodongo,
the King Dodongo floor). Placeholder files now build with
-fno-toplevel-reorder; this check keeps that true.

  check_ph_order.py object O019.elf O019_ph.txt     (.ph after the head)
  check_ph_order.py keep oot-core.elf keep_ph.txt   (.keep_ph from its start)
"""
import struct
import sys


def sections_and_symbols(path):
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF' or d[5] != 2:
        raise SystemExit('%s: not a big-endian ELF' % path)
    shoff, = struct.unpack('>I', d[32:36])
    entsize, count, strndx = struct.unpack('>HHH', d[46:52])
    sh = [struct.unpack('>10I', d[shoff + i * entsize:shoff + (i + 1) * entsize]) for i in range(count)]

    def cstr(base, off):
        end = d.index(b'\0', base + off)
        return d[base + off:end].decode()
    names = {cstr(sh[strndx][4], s[0]): (i, s) for i, s in enumerate(sh)}
    _, symtab = names['.symtab']
    strtab = sh[symtab[6]][4]
    symbols = {}
    for i in range(symtab[5] // 16):
        name, value, _, _, _, shndx = struct.unpack('>IIIBBH', d[symtab[4] + i * 16:symtab[4] + i * 16 + 16])
        symbols.setdefault(shndx, {})[cstr(strtab, name).lstrip('_')] = value
    return names, symbols


def check(kind, elf, listing):
    names, symbols = sections_and_symbols(elf)
    words = open(listing).read().split()
    order = words[1:] if kind == 'object' else words
    section = '.ph' if kind == 'object' else '.keep_ph'
    if section not in names:
        raise SystemExit('%s: no %s section' % (elf, section))
    index, header = names[section]
    start = header[3]
    found = symbols.get(index, {})
    bad = []
    for slot, name in enumerate(order):
        addr = found.get(name)
        if addr is None or (addr - start) // 8 != slot:
            bad.append('%s: list %d, linked %s' % (name, slot, 'missing' if addr is None else (addr - start) // 8))
    if bad:
        raise SystemExit('%s: %d of %d placeholders out of order (draw keys would miss):\n  %s'
                         % (elf, len(bad), len(order), '\n  '.join(bad[:8])))


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('object', 'keep'):
        raise SystemExit(__doc__)
    check(*sys.argv[1:])
