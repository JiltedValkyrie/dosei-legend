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
        out += struct.pack('>H2BHBx', *t)
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
    wanted = sorted({s['seq'] for s in scenes if s['seq'] not in (NO_MUSIC, NATURE_AMBIENCE) and s['seq'] not in routed})
    out = args.generated / 'area_music'
    report = []
    for seq in wanted:
        name = 'A%02X' % seq
        seq_path = source / ('sequences/seq_%d.seq' % seq)
        try:
            font = source / ('soundfonts/Soundfont_%d.xml' % bank.soundfont_of(seq_path))
            inputs = [Path(__file__), Path(bank.__file__), Path(bank.audio.__file__), seq_path, font]
            inputs += [source / ('samples/SampleBank_0/Sample%03d.wav' % int(s.attrib['Name'].split('_')[-1]))
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
    print('area music: %d baked, %d blocked' % (sum(r['status'] == 'baked' for r in report),
                                                 sum(r['status'] != 'baked' for r in report)))


if __name__ == '__main__':
    main()
