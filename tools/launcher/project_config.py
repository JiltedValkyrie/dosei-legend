"""Read the same local INI as the Windows launcher; no executable INI content."""
import argparse
import configparser
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def read_paths(root=ROOT):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(root/'config.example.ini', encoding='utf-8-sig')
    old_checkout = root.parent.parent/'game-decomps/n64/oot'
    if old_checkout.is_dir():
        parser['Paths']['oot_decomp'] = str(old_checkout)
    parser.read(root/'config.ini', encoding='utf-8-sig')
    values = dict(parser['Paths'])
    for key, value in values.items():
        if not value:
            continue
        if key == 'python' and not any(c in value for c in '/\\:'):
            values[key] = shutil.which(value) or value
        else:
            path = Path(value)
            values[key] = str(path if path.is_absolute() else (root/path).resolve())
    values['oot_roms'] = values.get('oot_roms') or str(Path(values['oot_decomp'])/'baseroms/ntsc-1.2')
    return values


def dependency_alias(path, kind):
    """Immutable, no-space relative alias for Jo's unquoted legacy make rules.

    Never deletes/repoints anything, never writes into the SDK. Different
    installations get different names. Build output lives under game/build.
    """
    source = Path(path).resolve(strict=True)
    digest = hashlib.sha256(str(source).encode()).hexdigest()[:12]
    target = ROOT/'game/build/dependencies'/f'{kind}-{digest}'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.resolve() != source:
            raise ValueError(f'Dependency alias points elsewhere: {target}')
    elif os.name == 'nt':
        env = dict(os.environ, DOSEI_LINK_PATH=str(target), DOSEI_LINK_TARGET=str(source))
        subprocess.run(['powershell.exe','-NoProfile','-Command',
                        "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path $env:DOSEI_LINK_PATH -Value $env:DOSEI_LINK_TARGET | Out-Null"],
                       env=env, check=True)
    else:
        target.symlink_to(source, target_is_directory=True)
    return target.relative_to(ROOT/'game').as_posix()


def prepare(paths):
    sdk = dependency_alias(paths['jo_engine'], 'sdk')
    msys = dependency_alias(paths['msys2'], 'msys')
    stamp = ROOT/'game/build/generated/toolchain.stamp'
    stamp.parent.mkdir(parents=True, exist_ok=True)
    signature = sdk+'\n'+msys+'\n'+paths['python']+'\n'
    if not stamp.exists() or stamp.read_text() != signature:
        stamp.write_text(signature)
    print(sdk)
    print(msys)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('key', nargs='?')
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    paths = read_paths()
    if args.prepare:
        prepare(paths)
    elif args.key in paths:
        print(paths[args.key])
    else:
        parser.error('provide a [Paths] key or --prepare')
