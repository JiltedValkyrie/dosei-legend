#!/usr/bin/env python3
"""Relink an existing Windows Kronos Ninja build with its VDP1 cap repaired.

All writes stay in --output. The upstream source, archive and executable stay
unchanged. Kronos 2.7 stops at 2048 drawing commands without setting EDSR.CEF,
deadlocking SGL slSynch. Allow the full 512 KiB / 32-byte command address space.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build, output = args.build.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=str(args.toolchain) + os.pathsep + os.environ['PATH'])
    commands = subprocess.check_output(
        [str(args.toolchain / 'ninja.exe'), '-C', str(build), '-t', 'commands',
         'src/port/qt/kronos.exe'], text=True, env=env).splitlines()
    compile_cmd = next(c for c in commands if re.search(r' -c .*[/\\]vdp1.c$', c))
    source = Path(compile_cmd.split(' -c ', 1)[1].strip('"'))
    text = source.read_text()
    old = '(nbCmdToProcess < CMD_QUEUE_SIZE)'
    if text.count(old) != 1:
        raise SystemExit('Unsupported Kronos source: expected one draw-limit guard')
    patched = output / 'vdp1.c'
    patched.write_text(text.replace(old, '(nbCmdToProcess < (0x80000 / 0x20))'))
    obj = output / 'vdp1.c.obj'
    compile_cmd = re.sub(r' -MD\b', '', compile_cmd)
    compile_cmd = re.sub(r' -M[TF] \S+', '', compile_cmd)
    compile_cmd = re.sub(r' -o \S+', ' -o "' + obj.as_posix() + '"', compile_cmd)
    compile_cmd = compile_cmd.split(' -c ', 1)[0] + ' -c "' + patched.as_posix() + '"'
    subprocess.run(compile_cmd, cwd=build, env=env, check=True)
    archive = output / 'libkronos.a'
    shutil.copy2(build / 'src/libkronos.a', archive)
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
