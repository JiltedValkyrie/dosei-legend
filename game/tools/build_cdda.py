"""Red Book audio tracks rendered offline from the ROM's sequences.

Track 02: NA_BGM_OPEN_TRE_BOX (Sequence_43, Soundfont 3), the treasure-chest
fanfare, played by the minimap cheat. Rendered with the shared sequence
interpreter (shared/tools/build_title_audio.py) at 44.1 kHz stereo 16-bit.
Host render of the baked notes: no N64 reverb/vibrato, same limits as the
title/forest previews. Output: build/TRACK02.BIN (raw little-endian CD-DA,
padded to 2352-byte sectors), listed by write_cue.py as TRACK 02 AUDIO.
"""
import argparse
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'shared/tools'))
import build_title_audio as audio

TRACKS = (
    # file, sequence, soundfont
    ('TRACK02.BIN', 43, 3),
)
HZ = 44100
# Offline render: no SCSP voice budget; the CD track is plain PCM.
audio.VOICES = 64
SECTOR = 2352


def render(seconds, frames, levels, cooked, samples):
    count = min(round(seconds * HZ), round(frames / audio.FPS * HZ))
    left, right = [0.0] * count, [0.0] * count
    for n in cooked:
        sample = samples[n['sample']]
        pcm = sample['pcm']
        begin = round(n['frame'] / audio.FPS * HZ)
        end = min(count, round(n['end_frame'] / audio.FPS * HZ))
        angle = n['pan'] / 127 * math.pi / 2
        l, r = math.cos(angle), math.sin(angle)
        for i in range(begin, end):
            pos = (i - begin) * n['rate'] / HZ
            if pos >= sample['loop_end']:
                span = sample['loop_end'] - sample['loop_start']
                if span <= 0:
                    break
                pos = sample['loop_start'] + (pos - sample['loop_end']) % span
            k = int(pos)
            if k + 1 >= len(pcm):
                break
            value = pcm[k] + (pcm[k + 1] - pcm[k]) * (pos - k)
            frame = min(frames - 1, i * audio.FPS // HZ)
            tl = levels[frame * audio.VOICES + n['slot']]
            gain = 0 if tl == 255 else 2 ** (-tl / 16)
            left[i] += value * gain * l
            right[i] += value * gain * r
    peak = max(1.0, max(map(abs, left)), max(map(abs, right)))
    scale = min(1.0, 32000 / peak)
    out = bytearray()
    for a, b in zip(left, right):
        out += struct.pack('<hh', round(a * scale), round(b * scale))
    out += bytes(-len(out) % SECTOR)
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=audio.ROOT / 'build/audio-source/extracted/assets/audio')
    parser.add_argument('--out', type=Path, default=ROOT / 'build')
    args = parser.parse_args()
    for name, seq_id, font in TRACKS:
        target = args.out / name
        seq = args.source / ('sequences/seq_%d.seq' % seq_id)
        if target.is_file() and target.stat().st_mtime > seq.stat().st_mtime and \
                target.stat().st_mtime > Path(__file__).stat().st_mtime:
            print('CD-DA %s: cached' % name)
            continue
        notes, tempo, volumes, gain, _, end, _ = audio.interpret(seq, 'SEQ_0000')
        times = audio.timeline(tempo, end)
        envelopes, instruments, samples, _, _ = audio.load_font(args.source, font)
        frames, levels, _, cooked = audio.bake(notes, times, volumes, gain, envelopes,
                                               instruments, samples, end)
        pcm = render(times[end] + 1.0, frames + audio.FPS, levels + bytearray([255]) *
                     (audio.FPS * audio.VOICES), cooked, samples)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pcm)
        print('CD-DA %s: seq %d, %.2f s, %d sectors' % (name, seq_id, times[end],
                                                      len(pcm) // SECTOR))


if __name__ == '__main__':
    main()
