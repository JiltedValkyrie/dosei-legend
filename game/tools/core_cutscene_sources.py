"""Source cutscene scripts for scene-local Saturn data, without IEEE runtime data.

Names retain stable tagged identities in resident code; the matching scene blob
supplies the complete script. Actors may also use ordinary pack-local scripts.
No missing script is represented by an empty cutscene.
"""
import re
import struct
import zlib
from pathlib import Path

SCENES = {'spot01', 'spot02', 'spot15', 'spot16', 'spot17', 'spot18', 'spot20',
          'spot05', 'ddan', 'ddan_boss', 'nakaniwa', 'hiral_demo',
          'daiyousei_izumi', 'yousei_izumi_yoko'}
SCRIPT = re.compile(r'CutsceneData\s+(\w+)\[\]\s*=\s*\{(.*?)\n\};', re.S)
FLOAT = re.compile(r'CS_FLOAT\(\s*(0[xX][0-9a-fA-F]+)\s*,\s*[^)]+\)')


def script_id(name):
    return 0xF1000000 | (zlib.crc32(name.encode('ascii')) & 0x00FFFFFF)


def fixed_word(match):
    value = struct.unpack('>f', struct.pack('>I', int(match.group(1), 16)))[0]
    if not -32768 <= value < 32768:
        raise ValueError(f'cutscene float outside Q16 range: {value}')
    return str(round(value * 65536))


def scene_scripts(path, asset_root):
    """Full arrays, including every cue, camera, text and branch command."""
    if path.stem.removesuffix('_scene') not in SCENES:
        return '', []
    definitions, rows = [], []
    for match in SCRIPT.finditer(path.read_text(encoding='utf-8')):
        name, body = match.groups()
        # Credits are outside this child-route admission; no fake replacement.
        if 'Credits' in name:
            continue
        body = re.sub(r'#include "([^"]+)"',
                      lambda inc: (asset_root / inc.group(1)).read_text(encoding='utf-8'), body)
        body = FLOAT.sub(fixed_word, body)
        if 'CS_FLOAT(' in body or '#include' in body:
            raise ValueError(f'{name}: unresolved script data')
        definitions.append(f'CutsceneData {name}[] = {{{body}\n}};')
        rows.append((script_id(name), name))
    if len({key for key, _ in rows}) != len(rows):
        raise ValueError(f'{path}: duplicate cutscene id')
    if not definitions:
        return '', []
    # Every former float word is already Q16. No Fx static constructor/data
    # relocation is permitted in a scene blob, whose loader copies bytes only.
    prefix = '#include "cutscene_commands.h"\n#undef CMD_F\n#define CMD_F(a) CMD_W(a)\n'
    return prefix + '\n'.join(definitions) + '\n', rows


def scene_symbols(oot):
    names = set()
    for path in (Path(oot) / 'extracted/ntsc-1.2/assets/scenes').rglob('*_scene.c'):
        names.update(m.group(1) for m in SCRIPT.finditer(path.read_text(encoding='utf-8')))
    if len({script_id(n) for n in names}) != len(names):
        raise ValueError('scene cutscene tag collision')
    return names


def adapt(rel, text, names):
    if not rel.endswith('.c') or rel.startswith('assets/') or rel.startswith('extracted/'):
        return text
    if rel == 'src/code/z_demo.c':
        # N64-only 64DD callback and segmented addresses cannot interpret the
        # cached SH-2 pointers. Resolve a scene tag or retain the pack pointer.
        start = text.index('void Cutscene_SetScript(PlayState* play, void* script) {')
        text = text[:start] + '''void Cutscene_SetScript(PlayState* play, void* script) {
    play->csCtx.script = OotCore_CutsceneResolve(script);
}
'''
        # Only a fully admitted script may consume its source entrance flag.
        text = text.replace('if ((gSaveContext.save.entranceIndex == entranceCutscene->entrance) &&',
                            'if (OotCore_CutsceneAvailable(entranceCutscene->script) &&\n'
                            '            (gSaveContext.save.entranceIndex == entranceCutscene->entrance) &&')
    used = set(re.findall(r'\b\w+\b', text)) & names
    if used:
        for name in sorted(used, key=len, reverse=True):
            # Tables need constant identities; direct actor assignments are
            # resolved centrally before source script processing.
            text = re.sub(r'\b' + re.escape(name) + r'\b',
                          f'((CutsceneData*)0x{script_id(name):08X}u)', text)
    if used or rel == 'src/code/z_demo.c':
        text = '#include "oot_core_cutscene.h"\n' + text
    return text
