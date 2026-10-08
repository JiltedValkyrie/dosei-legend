#!/usr/bin/env python3
"""Build fixed-address OAP1 packs against the exact linked resident core.

No actor imports happen here. --objects is a trusted pack-only actor/effect TU
list, never a path for engine helper copies. Supply already-compiled objects or use
--test-pack for the infrastructure fixture. Engine-object weakening is forbidden.
Helper copies require an explicit symbol allowlist and relocation audit.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
MAGIC, VERSION, HEADER_BYTES = 0x4F415031, 1, 80
FIELDS = ('magic version header_bytes core_crc link_base file_bytes memory_bytes '
          'bss_offset bss_bytes ctors_offset ctor_count actors_offset actor_count '
          'effects_offset effect_count crc text_offset text_bytes scene flags').split()


class Elf32:
    """Small ELF reader; preserves raw ABI names, including SH leading _."""
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:6] != b'\x7fELF\x01\x02':
            raise ValueError(f'{path}: expected big-endian ELF32')
        self.header = struct.unpack_from('>16sHHIIIIIHHHHHH', self.data)
        if self.header[2] != 42:
            raise ValueError(f'{path}: expected SH ELF')
        off, size, count, names = self.header[6], self.header[11], self.header[12], self.header[13]
        self.sections = [struct.unpack_from('>10I', self.data, off + i * size) for i in range(count)]
        self.names = self.section_data(names)
        self.symbols = []
        self.symbol_tables = {}
        for index, section in enumerate(self.sections):
            if section[1] != 2:
                continue
            strings = self.section_data(section[6])
            table = []
            for pos in range(section[4], section[4] + section[5], section[9]):
                name, value, nbytes, info, other, shndx = struct.unpack_from('>IIIBBH', self.data, pos)
                row = dict(name=self.cstr(strings, name), value=value, size=nbytes,
                           binding=info >> 4, kind=info & 15, section=shndx)
                table.append(row)
            self.symbol_tables[index] = table
            self.symbols.extend(table)

    @staticmethod
    def cstr(data, offset):
        return data[offset:data.index(0, offset)].decode()

    def section_data(self, index):
        row = self.sections[index]
        return self.data[row[4]:row[4] + row[5]]

    def name(self, index):
        return self.cstr(self.names, self.sections[index][0])

    def value(self, name):
        return next(row['value'] for row in self.symbols if row['name'] == name and row['section'])


def audit_helper(path, allowed, core=None):
    """Reject any helper's relocation to mutable storage or hidden engine code.

    Audit the complete TU conservatively before gc; even unused state is denied.
    Use a dedicated stateless helper TU rather than weakening an engine object.
    """
    elf = Elf32(path)
    resident = {row['name']: row for row in core.symbols if row['section']} if core else {}
    for row in elf.symbols:
        if row['kind'] == 2 and row['section'] and row['name'] not in allowed:
            raise ValueError(f'{path}: helper function not allowed: {row["name"]}')
    for section in elf.sections:
        if section[1] not in (4, 9):
            continue
        table = elf.symbol_tables[section[6]]
        for pos in range(section[4], section[4] + section[5], section[9]):
            _, info = struct.unpack_from('>II', elf.data, pos)
            target = table[info >> 8]
            ix = target['section']
            if 0 < ix < len(elf.sections) and elf.sections[ix][2] & 1:
                raise ValueError(f'{path}: helper touches mutable {target["name"] or elf.name(ix)}')
            if ix == 0 and target['name']:
                resolved = resident.get(target['name'])
                if not resolved or not 0 < resolved['section'] < len(core.sections):
                    raise ValueError(f'{path}: helper external not resolved: {target["name"]}')
                flags = core.sections[resolved['section']][2]
                if flags & 1 or not (resolved['kind'] == 2 and flags & 4 or flags & 2 and not flags & 4):
                    raise ValueError(f'{path}: helper touches resident state: {target["name"]}')


def validate(data, core_crc, carve_base=0x02730000, carve_bytes=0x40000, used=0):
    if len(data) < HEADER_BYTES:
        raise ValueError('short actor pack')
    h = dict(zip(FIELDS, struct.unpack_from('>20I', data)))
    def need(condition, message):
        if not condition:
            raise ValueError(message)
    def extent(offset, count, stride):
        need(HEADER_BYTES <= offset <= len(data) and count <= (len(data) - offset) // stride,
             'actor pack table extent')
    need((h['magic'], h['version'], h['header_bytes']) == (MAGIC, VERSION, HEADER_BYTES), 'actor pack ABI')
    need(h['core_crc'] == core_crc, 'actor pack belongs to another core')
    need(h['file_bytes'] == len(data), 'actor pack file size')
    need(len(data) <= h['memory_bytes'] <= carve_bytes and not h['memory_bytes'] % 16,
         'actor pack memory size')
    need(used <= carve_bytes - h['memory_bytes'], 'OOC + OOB + OAP exceeds scene carve')
    need(h['link_base'] == carve_base + carve_bytes - h['memory_bytes'], 'actor pack link base')
    need(h['bss_offset'] == len(data) and h['bss_bytes'] <= h['memory_bytes'] - len(data), 'actor pack BSS')
    need(h['flags'] & ~1 == 0, 'actor pack flags')
    extent(h['text_offset'], h['text_bytes'], 1)
    need(h['text_bytes'] > 0 and not h['text_offset'] % 4, 'actor pack text')
    for key, stride in (('ctors', 4), ('actors', 8), ('effects', 8)):
        count_key = {'ctors': 'ctor_count', 'actors': 'actor_count', 'effects': 'effect_count'}[key]
        extent(h[key + '_offset'], h[count_key], stride)
        need(not h[key + '_offset'] % 4, 'unaligned actor pack table')
    need(h['ctors_offset'] >= h['text_offset'] + h['text_bytes'] and
         h['actors_offset'] >= h['ctors_offset'] + 4 * h['ctor_count'] and
         h['effects_offset'] >= h['actors_offset'] + 8 * h['actor_count'],
         'overlapping actor pack tables/text')
    copy = bytearray(data)
    copy[60:64] = b'\0' * 4
    need(zlib.crc32(copy) == h['crc'], 'actor pack checksum')
    text_start = h['link_base'] + h['text_offset']
    for i in range(h['ctor_count']):
        ptr, = struct.unpack_from('>I', data, h['ctors_offset'] + 4 * i)
        need(text_start <= ptr < text_start + h['text_bytes'] and not ptr % 2, 'actor pack ctor pointer')
    for key in ('actors', 'effects'):
        ids = set()
        count = h['actor_count' if key == 'actors' else 'effect_count']
        for i in range(count):
            ident, ptr = struct.unpack_from('>II', data, h[key + '_offset'] + i * 8)
            need(ident not in ids, 'duplicate actor pack profile')
            ids.add(ident)
            need(h['link_base'] + h['text_offset'] + h['text_bytes'] <= ptr <
                 h['link_base'] + h['ctors_offset'] and not ptr % 4,
                 'actor pack profile pointer')
    return h


def build(args):
    core = Path(args.core)
    core_bin = Path(args.core_bin)
    core_crc = zlib.crc32(core_bin.read_bytes())
    core_elf = Elf32(core)
    objects = [Path(p) for p in args.objects]
    for path in args.helper_object:
        audit_helper(path, set(args.allow_helper_symbol), core_elf)
        objects.append(Path(path))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cxx = args.cxx
    objcopy = str(Path(cxx).with_name(Path(cxx).name.replace('g++', 'objcopy').replace('gcc', 'objcopy')))
    objdump = str(Path(cxx).with_name(Path(cxx).name.replace('g++', 'objdump').replace('gcc', 'objdump')))
    used = args.used_bytes
    named = {'OOC/OOB': used}
    for raw in args.payload:
        name, path = raw.split('=', 1)
        size = (Path(path).stat().st_size + 15) & ~15
        named[name] = size
        used += size
    with tempfile.TemporaryDirectory(dir=out.parent, prefix='pack-link-') as tmp:
        tmp = Path(tmp)
        converted_core = tmp / 'core.bin'
        subprocess.run([objcopy, '-O', 'binary', str(core), str(converted_core)], check=True)
        if converted_core.read_bytes() != core_bin.read_bytes():
            raise ValueError('core ELF/BIN mismatch: rebuild OOTCORE.BIN before packs')
        if args.test_pack:
            fixture = tmp / 'fixture.o'
            subprocess.run([cxx, '-m2', '-Os', '-std=gnu++17', '-fno-exceptions', '-fno-rtti',
                            '-fno-threadsafe-statics', '-fno-use-cxa-atexit', '-ffunction-sections',
                            '-fdata-sections', '-c', str(ROOT / 'oot-core/tests/actor_pack_fixture.cpp'),
                            '-o', str(fixture)], check=True)
            objects.append(fixture)
        if not objects:
            raise ValueError('no pack objects')
        # Duplicate global engine definitions are never weakened into the pack.
        definitions = {s['name'] for s in core_elf.symbols if s['binding'] == 1 and s['section']}
        for path in objects:
            elf = Elf32(path)
            duplicates = sorted(s['name'] for s in elf.symbols
                                if s['binding'] == 1 and s['section'] and s['name'] in definitions)
            if duplicates:
                raise ValueError(f'{path}: resident engine definitions copied: {duplicates}')
        end = args.carve_base + args.carve_bytes
        elf_path, raw_path = tmp / 'pack.elf', tmp / 'pack.bin'
        base = args.carve_base
        for pass_index in range(2):
            command = [cxx, '-m2', '-nostdlib', '-nostartfiles', '-T', str(ROOT / 'oot-core/pack.ld'),
                       '-Wl,--gc-sections', f'-Wl,--just-symbols={core}',
                       f'-Wl,-Map,{out.with_suffix(".map")}',
                       f'-Wl,--defsym,OOT_PACK_BASE={base}', f'-Wl,--defsym,OOT_PACK_END={end}',
                       f'-Wl,--defsym,OOT_PACK_CORE_CRC={core_crc}',
                       f'-Wl,--defsym,OOT_PACK_SCENE={args.scene}',
                       f'-Wl,--defsym,OOT_PACK_FLAGS={int(args.test_pack)}']
            if args.test_pack:
                command.append('-Wl,-u,_oot_pack_probe')
            command += [str(p) for p in objects]
            if args.obj_syms:
                command.append(args.obj_syms)
            command += ['-lgcc', '-o', str(elf_path)]
            subprocess.run(command, check=True)
            elf = Elf32(elf_path)
            memory = (elf.value('_pack_memory_end') - base + 15) & ~15
            if pass_index == 0:
                base = end - memory
            elif base != end - memory:
                raise ValueError('pack size changed between fixed-address links')
        subprocess.run([objcopy, '-O', 'binary', str(elf_path), str(raw_path)], check=True)
        data = bytearray(raw_path.read_bytes())
        struct.pack_into('>I', data, 60, zlib.crc32(data))
        header = validate(data, core_crc, args.carve_base, args.carve_bytes, used)
        # Existing wide audit covers every pack's actual linked instructions.
        disasm = subprocess.check_output([objdump, '-d', str(elf_path)], text=True)
        # Audit CLI is authoritative, including future rule changes.
        disasm_path = tmp / 'pack.dis'
        disasm_path.write_text(disasm)
        import sys
        subprocess.run([sys.executable, str(ROOT / 'tools/audit_oot_core_wide.py'), str(disasm_path)], check=True)
        out.write_bytes(data)
        out.with_suffix('.elf').write_bytes(elf_path.read_bytes())
        named['OAP file'] = len(data)
        named['OAP BSS/alignment'] = memory - len(data)
        report = {'header': header, 'costs': named, 'total': used + memory,
                  'free': args.carve_bytes - used - memory, 'fixture_only': bool(args.test_pack)}
        out.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, sort_keys=True))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True)
    parser.add_argument('--core-bin', required=True)
    parser.add_argument('--obj-syms')
    parser.add_argument('--output', required=True)
    parser.add_argument('--cxx', default='sh-elf-g++')
    parser.add_argument('--objects', nargs='*', default=[])
    parser.add_argument('--helper-object', action='append', default=[])
    parser.add_argument('--allow-helper-symbol', action='append', default=[])
    parser.add_argument('--test-pack', action='store_true')
    parser.add_argument('--scene', type=lambda x: int(x, 0), default=0xffffffff)
    parser.add_argument('--carve-base', type=lambda x: int(x, 0), default=0x02730000)
    parser.add_argument('--carve-bytes', type=lambda x: int(x, 0), default=0x40000)
    parser.add_argument('--used-bytes', type=lambda x: int(x, 0), default=0)
    parser.add_argument('--payload', action='append', default=[], help='named OOC/OOB cost NAME=FILE')
    args = parser.parse_args()
    try:
        build(args)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'actor pack: {error}\n')


if __name__ == '__main__':
    main()
