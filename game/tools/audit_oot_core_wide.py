#!/usr/bin/env python3
"""Wave 0 SH-2 audit of the oot-core blob (no 64-bit runtime math rule).

Reads `objdump -d` output of build/oot-core/oot-core.elf (or the game ELF)
and reports, per function, uses of the on-chip 64/32 divider registers and
references to libgcc software 64-bit or soft-float helpers: those FAIL.
Native dmuls.l / dmulu.l (hardware product in MACH:MACL) is ALLOWED by the
human (2026-10-06, speed wins) and only counted for information. SH symbol spellings differ (__divdi3 vs ___divdi3):
every 1-to-3-underscore prefix counts. 32-bit helpers (___sdivsi3,
___udivsi3, ___ashiftrt_r4_*, ___lshrsi3, ___clzsi2) are allowed.
Literal-pool and table words that merely decode as mac.l or `sts mach`
(0x000A is the number 10) are ignored: only dmuls/dmulu count.

usage: audit_oot_core_wide.py DISASM.txt   (exit 1 when anything is found)
       audit_oot_core_wide.py --self-test  (positive/negative controls)
"""
import re
import sys
from collections import Counter

FUNC = re.compile(r'^[0-9a-f]+ <([^>]+)>:$')
INSN = re.compile(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} ){2}\s*(\S+)\s*(.*)$')
# 64-bit integer helpers (...di2/di3) and soft-float helpers (sf/df/tf type
# tags, fp-bit internals). Mangled C++ names (_Z...) are never helpers.
WIDE_HELPERS = re.compile(
    r'<(_{1,3}(?![_Z])(?:'
    r'(?:mul|div|udiv|mod|umod|udivmod|ashl|ashr|lshr|neg|cmp|ucmp|ffs|clz|ctz|popcount|parity|bswap)di[23]'
    r'|(?:add|sub|mul|div|neg|eq|ne|lt|le|gt|ge|cmp|unord|fixuns|fix|floatun|float|extend|trunc|powi)'
    r'(?:sf|df|tf|si|di)*?(?:sf|df|tf)(?:si|di|sf|df|tf)?\d?'
    r'|(?:un)?pack_[fd]|make_dp|fpcmp_parts_[fd]|thenan_[sdt]f))>')
# Helper bodies themselves (libgcc / fp-bit): 2-3 leading underscores and not
# a mangled C++ name. Game C functions carry ONE leading underscore (_main).
LIBGCC = re.compile(r'^_{2,3}(?![_Z])')


def audit(lines):
    func = '?'
    found = Counter()
    for line in lines:
        m = FUNC.match(line)
        if m:
            func = m.group(1)
            continue
        m = INSN.match(line)
        if not m:
            continue
        op, args = m.group(2), m.group(3)
        if op in ('dmuls.l', 'dmulu.l'):
            found[(func, op)] += 1
        elif re.search(r'0xffffff(0[04]|1[04])\b', args, re.I):
            found[(func, 'divider register')] += 1
        h = WIDE_HELPERS.search(args)
        if h:
            found[(func, 'calls ' + h.group(1))] += 1
    return found


ALLOWED = ('dmuls.l', 'dmulu.l')


def own(found):
    """Failing findings outside libgcc's own helper bodies (C++ is mangled _Z).
    Hardware multiplies are allowed and never fail."""
    return {k: v for k, v in found.items() if not LIBGCC.match(k[0]) and k[1] not in ALLOWED}


SELF_TEST = [
    # (name, disassembly, expected own findings)
    ('target 3-underscore 64-bit divide', '''
02770000 <__Z3fooii>:
 2770000:	d0 02       	mov.l	277000c <__Z3fooii+0xc>,r0	! 27c8000 <___divdi3>
 2770002:	40 0b       	jsr	@r0
''', 1),
    ('2-underscore 64-bit multiply', '''
02770000 <__Z3barv>:
 2770000:	d0 02       	mov.l	277000c <__Z3barv+0xc>,r0	! 27c8000 <__muldi3>
''', 1),
    ('soft-float calls', '''
02770000 <__ZN2FxC1Ef>:
 2770000:	d0 16       	mov.l	2770314 <__ZN2FxC1Ef+0x60>,r0	! 27c8128 <___extendsfdf2>
 2770002:	d0 17       	mov.l	2770318 <__ZN2FxC1Ef+0x64>,r0	! 27c8164 <___fixdfsi>
''', 2),
    ('allowed: native dmuls.l / dmulu.l', '''
02770000 <__Z3bazl>:
 2770000:	30 2d       	dmuls.l	r2,r0
 2770002:	30 25       	dmulu.l	r2,r0
''', 0),
    ('divider register', '''
02770000 <__Z3quxv>:
 2770000:	d1 02       	mov.l	277000c <__Z3quxv+0xc>,r1	! 0xffffff00
''', 1),
    ('negative: data words, 32-bit helpers, mangled sf names', '''
02770000 <__Z3okv>:
 2770000:	07 ff       	mac.l	@r15+,@r7+
 2770002:	00 0a       	sts	mach,r0
 2770004:	d0 02       	mov.l	277000c <__Z3okv+0xc>,r0	! 27c0a9c <___udivsi3>
 2770006:	d0 03       	mov.l	2770010 <__Z3okv+0x10>,r0	! 27c0a9c <___ashiftrt_r4_8>
 2770008:	d0 04       	mov.l	2770014 <__Z3okv+0x14>,r0	! 27c0d94 <___clzsi2>
 277000a:	d0 05       	mov.l	2770018 <__Z3okv+0x18>,r0	! 27c0d94 <__Z8sfx_playv>
 277000c:	d0 06       	mov.l	277001c <__Z3okv+0x1c>,r0	! 27c0d94 <___sdivsi3>
''', 0),
    ('C function (one underscore) calling 64-bit divide and float', '''
02770000 <_game_step>:
 2770000:	d0 02       	mov.l	277000c <_game_step+0xc>,r0	! 27c8000 <___divdi3>
 2770002:	d0 03       	mov.l	2770010 <_game_step+0x10>,r0	! 27c8000 <___floatunsisf>
''', 2),
    ('negative: printf/transform names are not soft-float', '''
02770000 <_hud>:
 2770000:	d0 02       	mov.l	277000c <_hud+0xc>,r0	! 27c8000 <_siprintf>
 2770002:	d0 03       	mov.l	2770010 <_hud+0x10>,r0	! 27c8000 <___jo_sprintf_buf>
 2770004:	d0 04       	mov.l	2770014 <_hud+0x14>,r0	! 27c8000 <_transform>
''', 0),
    ('negative: helper bodies themselves', '''
027c8000 <___divdi3>:
 27c8000:	33 95       	dmulu.l	r9,r3
''', 0),
]


def self_test():
    ok = True
    for name, text, expected in SELF_TEST:
        got = sum(own(audit(text.strip('\n').splitlines())).values())
        ok &= got == expected
        print(f'{"ok" if got == expected else "FAIL"}: {name}: {got} finding(s), expected {expected}')
    return 0 if ok else 1


def main(path):
    found = audit(open(path, encoding='utf-8', errors='replace'))
    mine = own(found)
    for (f, what), n in sorted(found.items()):
        print(f'{n:5d}  {what:28s} {f}')
    allowed = sum(v for k, v in found.items() if k[1] in ALLOWED)
    print(f'total: {sum(found.values())} sites in {len({f for f, _ in found})} functions; '
          f'{allowed} allowed hardware multiplies; {sum(mine.values())} FAILING outside libgcc')
    return 1 if mine else 0


if __name__ == '__main__':
    sys.exit(self_test() if sys.argv[1:] == ['--self-test'] else main(sys.argv[1]))
