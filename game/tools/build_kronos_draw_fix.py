#!/usr/bin/env python3
"""Relink an existing Windows Kronos Ninja build with emulator bugs repaired.

All writes stay in --output. The upstream source, archive and executable stay
unchanged. Each patch recompiles one local copy of a Kronos source file:

* vdp1.c: Kronos 2.7 stops at 2048 drawing commands without setting EDSR.CEF,
  deadlocking SGL slSynch. Allow the full 512 KiB / 32-byte command space.
* sh2int.c: instruction fetch from the A-bus CS0 cart area is only mapped for
  0x02000000-0x020FFFFF; anything higher fetches 0xFFFF and the CPU hangs.
  Real hardware runs code anywhere in CS0. The game's oot-core blob runs from
  the 4 MB RAM cart at 0x027C0000. Map 0x020-0x03F to the CS0 code cache,
  which is already sized for 4 MB (cacheMask 0x1FFFFF words).
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

CS0_OLD = """          case 0x020: // CS0
            krfetchlist[i] = SH2MappedMemoryReadWord;
            cacheId[i] = 2;
            break;"""
CS0_NEW = """          case 0x020: case 0x021: case 0x022: case 0x023: // CS0: whole 4 MB cart
          case 0x024: case 0x025: case 0x026: case 0x027:
            krfetchlist[i] = SH2MappedMemoryReadWord;
            cacheId[i] = 2;
            break;"""

# (source file name, old text, new text). Each old text must occur once.
PATCHES = [
    ('vdp1.c', '(nbCmdToProcess < CMD_QUEUE_SIZE)', '(nbCmdToProcess < (0x80000 / 0x20))'),
    ('sh2int.c', CS0_OLD, CS0_NEW),
]


def compile_patched(build, output, env, commands, name, old, new):
    compile_cmd = next(c for c in commands if re.search(r' -c .*[/\\]' + re.escape(name) + '$', c))
    source = Path(compile_cmd.split(' -c ', 1)[1].strip('"'))
    if not source.is_absolute():
        source = build / source
    text = source.read_text(encoding='utf-8', errors='surrogateescape')
    if text.count(old) != 1:
        raise SystemExit(f'Unsupported Kronos source: expected one patch site in {name}')
    patched = output / name
    patched.write_text(text.replace(old, new), encoding='utf-8', errors='surrogateescape')
    obj = output / (name + '.obj')
    compile_cmd = re.sub(r' -MD\b', '', compile_cmd)
    compile_cmd = re.sub(r' -M[TF] \S+', '', compile_cmd)
    compile_cmd = re.sub(r' -o \S+', ' -o "' + obj.as_posix() + '"', compile_cmd)
    # The local copy lives in --output: keep the original directory on the
    # include path for its relative "#include" lines.
    compile_cmd = (compile_cmd.split(' -c ', 1)[0] + ' -I"' + source.parent.as_posix() + '"'
                   + ' -c "' + patched.as_posix() + '"')
    subprocess.run(compile_cmd, cwd=build, env=env, check=True)
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path,
                        help='base libkronos.a (default: the build\'s own)')
    args = parser.parse_args()
    build, output = args.build.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=str(args.toolchain) + os.pathsep + os.environ['PATH'])
    commands = subprocess.check_output(
        [str(args.toolchain / 'ninja.exe'), '-C', str(build), '-t', 'commands',
         'src/port/qt/kronos.exe'], text=True, env=env).splitlines()
    objs = [compile_patched(build, output, env, commands, *p) for p in PATCHES]
    archive = output / 'libkronos.a'
    base = (args.archive or build / 'src/libkronos.a').resolve()
    if base != archive:
        shutil.copy2(base, archive)
    for obj in objs:
        # Archive members are named by basename: replace the original object.
        subprocess.run([str(args.toolchain / 'ar.exe'), 'r', str(archive), str(obj)],
                       cwd=build, env=env, check=True)
    ninja = (build / 'build.ninja').read_text()
    block = ninja.split('build src/port/qt/kronos.exe:', 1)[1].split('\n\n', 1)[0]
    objects = block.splitlines()[0].split(' | ', 1)[0].split()[1:]
    libraries = re.search(r'  LINK_LIBRARIES = (.+)', block).group(1).split()
    libraries = [archive.as_posix() if p == 'src/libkronos.a' else p for p in libraries]
    rsp = output / 'link.rsp'
    rsp.write_text('\n'.join('"' + p + '"' for p in objects + libraries))
    subprocess.run([str(args.toolchain / 'c++.exe'), '-mwindows', '-fno-PIE',
                    '-no-pie', '@' + str(rsp), '-o', str(output / 'kronos.exe')],
                   cwd=build, env=env, check=True)
    settings = build / 'src/port/qt/kronos.ini'
    if settings.exists() and not (output / 'kronos.ini').exists():
        shutil.copy2(settings, output / 'kronos.ini')
    print('Built', output / 'kronos.exe')


if __name__ == '__main__':
    main()
