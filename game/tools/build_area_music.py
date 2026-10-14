"""Bake each scene's area theme (scene header seqId) into a disc-loaded bank.

Every scene's SCENE_CMD_SOUND_SETTINGS seqId comes from scene_table.json
(build_scene_table.py). A seqId that songs.json already routes keeps its
built-in bank; every other one is baked with the shared music pipeline
(build_cutscene_audio.build_one) into M<seq hex>.PCM / .LVL / .HDR on the
disc. The runtime (src/music_area.c) loads the .HDR tables into the cart
heap and plays them through one shared music_bank_t, so a new theme costs no
work RAM. A sequence the converter cannot bake is reported, never faked.

HDR layout (big-endian): 'MBNK', u32 frames, loop_frame, voices, sample_base,
pcm_bytes, level_bytes, pcm_count, trigger_count; then music_pcm_t[pcm_count]
(u32 offset, u16 loop_start, u16 loop_end) and music_trigger_t[trigger_count]
(u16 frame, u8 slot, u8 sample, u16 pitch, u8 pan, pad).
"""
import argparse
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import build_cutscene_audio as bank

ROOT = Path(__file__).resolve().parents[1]
NO_MUSIC = 0x7F
NATURE_AMBIENCE = 0x01  # NA_BGM_NATURE_AMBIENCE: ambience only, no sequence file
GENERAL_SFX = 0x00      # NA_BGM_GENERAL_SFX: the sound-effect sequence, not music


def without_debug(text):
    """Drop DEBUG_FEATURES=0 branches (not the retail shop's music menu)."""
    output, stack, enabled = [], [], True
    for line in text.splitlines(keepends=True):
        match = re.match(r'\s*#\s*(if|ifdef|ifndef|else|endif)\b(.*)', line)
        if match:
            op, condition = match.groups()
            if op in ('if', 'ifdef', 'ifndef'):
                known = op == 'if' and condition.strip() in ('DEBUG_FEATURES', '!DEBUG_FEATURES')
                active = condition.strip() != 'DEBUG_FEATURES' if known else True
                stack.append((enabled, known, active))
                enabled = enabled and active
            elif op == 'else' and stack:
                parent, known, active = stack[-1]
                enabled = parent and (not active if known else True)
            elif op == 'endif' and stack:
                enabled = stack.pop()[0]
        elif enabled:
            output.append(line)
    return ''.join(output)


def route_sequences(oot):
    """Original actor/scene-script/engine requests, including non-area minigame cues."""
    import scene_pack_actors
    import core_cutscene_sources
    table = (oot / 'include/tables/sequence_table.h').read_text(encoding='utf-8')
    ids = {name: int(number) for number, name in re.findall(
        r'DEFINE_SEQUENCE\s*\(Sequence_(\d+),\s*(NA_BGM_\w+)', table)}
    text = '\n'.join(without_debug((oot / path).read_text(encoding='utf-8')) for path in scene_pack_actors.SOURCES)
    # Engine requests too: z_message plays every ocarina song fanfare
    # (sOcarinaSongFanfares, learn/play), which no actor names.
    text += '\n' + '\n'.join(without_debug(p.read_text(encoding='utf-8')) for p in sorted((oot / 'src/code').glob('*.c')))
    asset_root = oot / 'extracted/ntsc-1.2'
    for path in (asset_root / 'assets/scenes').rglob('*_scene.c'):
        if path.stem.removesuffix('_scene') in core_cutscene_sources.SCENES:
            script, _ = core_cutscene_sources.scene_scripts(path, asset_root)
            text += '\n' + script
    return {ids[name] for name in set(re.findall(r'\bNA_BGM_\w+\b', text)) if name in ids}


def define(text, name):
    return int(re.search(r'#define %s (\d+)' % name, text).group(1))


def array(text, name):
    body = re.search(r'%s\[\] = \{(.*?)\};' % name, text, re.S).group(1)
    return [tuple(int(v) for v in row.split(',')) for row in re.findall(r'\{\s*([-\d,\s]+?)\s*\}', body)]


def header_blob(score, name):
    text = score.read_text()
    lower = name.lower()
    pcm = array(text, lower + '_pcm')
    triggers = array(text, lower + '_triggers')
    out = bytearray(b'MBNK')
    out += struct.pack('>8I', define(text, name + '_FRAMES'), define(text, name + '_LOOP_FRAME'),
                       define(text, name + '_VOICES'), define(text, name + '_SAMPLE_BASE'),
                       define(text, name + '_PCM_BYTES'), define(text, name + '_LEVEL_BYTES'),
                       len(pcm), len(triggers))
    for p in pcm:
        out += struct.pack('>I2H', *p)
    for t in triggers:
        out += struct.pack('>H2BH2B', *(t if len(t) == 6 else (*t, 0)))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, required=True)
    ap.add_argument('--generated', type=Path, default=ROOT / 'build/generated')
    ap.add_argument('--cd', type=Path, default=ROOT / 'build/cd')
    args = ap.parse_args()
    source = args.oot / 'extracted/ntsc-1.2/assets/audio'
    routed = {s['id'] for s in json.loads((ROOT / 'assets/audio/songs.json').read_text())['songs']}
    scenes = json.loads((args.generated / 'scene_table.json').read_text())['scenes']
    required = route_sequences(args.oot) - routed - {NO_MUSIC, NATURE_AMBIENCE, GENERAL_SFX}
    wanted = sorted(({s['seq'] for s in scenes} | required) - routed - {NO_MUSIC, NATURE_AMBIENCE, GENERAL_SFX})
    out = args.generated / 'area_music'
    report = []
    for seq in wanted:
        name = 'A%02X' % seq
        seq_path = source / ('sequences/seq_%d.seq' % seq)
        try:
            font = source / ('soundfonts/Soundfont_%d.xml' % bank.soundfont_of(seq_path))
            inputs = [Path(__file__), Path(bank.__file__), Path(bank.audio.__file__), seq_path, font]
            inputs += [bank.audio.sample_path(source, s.attrib['Name'])
                       for s in ET.parse(font).getroot().find('Samples')]
            digest = hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
            stamp = out / (name + '.stamp')
            files = [out / (name + '_PCM.RAW'), out / (name + '_LEVELS.RAW'), out / (name.lower() + '_score.h')]
            if not (stamp.exists() and stamp.read_text() == digest and all(f.exists() for f in files)):
                try:
                    bank.build_one(source, out, name, seq, name, preserve_intro=True)
                except ValueError as error:
                    if 'pitch automation' not in str(error):
                        raise
                    bank.build_one(source, out, name, seq, name, preserve_intro=True,
                                   pitch_automation=True)
                stamp.write_text(digest)
            disc = 'M%02X' % seq
            (args.cd / (disc + '.PCM')).write_bytes(files[0].read_bytes())
            (args.cd / (disc + '.LVL')).write_bytes(files[1].read_bytes())
            (args.cd / (disc + '.HDR')).write_bytes(header_blob(files[2], name))
            report.append(dict(seq=seq, status='baked', file=disc))
        except (Exception, SystemExit) as error:  # noqa: BLE001 - report every failure
            report.append(dict(seq=seq, status='blocked', error='%s: %s' % (type(error).__name__, error)))
        print('area music seq 0x%02X: %s' % (seq, report[-1].get('error', 'baked')), flush=True)
    (args.generated / 'area_music.json').write_text(json.dumps(report, indent=1) + '\n')
    bits = bytearray(16)
    for r in report:
        if r['status'] == 'baked':
            bits[r['seq'] >> 3] |= 1 << (r['seq'] & 7)
    (args.generated / 'area_music_list.h').write_text(
        '/* Generated by tools/build_area_music.py: seqIds with an M<seq>.HDR bank. */\n'
        'static const unsigned char area_music_baked[16] = { %s };\n' % ', '.join(str(b) for b in bits))
    print('area music: %d baked, %d blocked' % (sum(r['status'] == 'baked' for r in report),
                                                 sum(r['status'] != 'baked' for r in report)))
    blocked = [r for r in report if r['seq'] in required and r['status'] != 'baked']
    if blocked:
        raise SystemExit('Required route music failed: ' + ', '.join(hex(r['seq']) for r in blocked))


if __name__ == '__main__':
    main()
