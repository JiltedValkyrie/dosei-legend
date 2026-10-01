"""Resident opening SFX from OoT's sequence-0 samples, in the action-bank tail.

Bounded PCM8 at 5512.5 Hz (fairy flight 11025 Hz). Fairy sounds retain source
sustain/pitch bends; other effects have reduced envelopes and no reverb.
The opening swaps this bank with ACTIONS.PCM at scene load.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import build_action_audio as audio
import fairy_audio

ROOT = Path(__file__).resolve().parents[1]
# name, source channel, (instrument, note) layers, seconds, looping
SOUNDS = (
    ('cut', 'CHAN_5AB7', ((47, 'DF4'), (74, 'A1')), .9, False),
    ('thunder', 'CHAN_1DEE', ((47, 'DF4'), (70, 'G3')), 1.1, False),
    ('bridge', 'CHAN_198F', ((34, 'C4'), (57, 'EF3')), .45, True),
    ('bridge_stop', 'CHAN_19F7', ((36, 'B2'), (59, 'D1')), .65, False),
    ('hooves', 'CHAN_264B', ((48, 'C4'),), .4, True),
    ('neigh', 'CHAN_1FFD', ((50, 'D4'),), 1.5, False),
    ('dust', 'CHAN_1DBF', ((12, 'C4'),), .33, False),
    ('dash', 'CHAN_1B01', ((69, 'B5'),), .65, False),
    ('rain', 'CHAN_2EB6', (), .6, True),
)


def build(oot, source, output):
    seq = (oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
    font = ET.parse(source / 'soundfonts/Soundfont_0.xml')
    audio.RATE = 5512.5
    bank, records = bytearray(), []
    for name, channel, layers, duration, loop in SOUNDS:
        block = seq.split('.channel ' + channel + '\n', 1)[1].split('.channel', 1)[0]
        rendered, sources = [], []
        if name == 'rain':
            sample = font.find('.//Drum[@Note="B0"]').attrib['Sample']
            selected = [(sample, None)]
        else:
            selected = []
            for instrument, pitch in layers:
                if 'SF0_INST_%d' % instrument not in block or 'PITCH_' + pitch not in block:
                    raise ValueError('Review source SFX channel ' + channel)
                selected.append((font.find('.//Instrument[@ProgramNumber="%d"]' % instrument)
                                 .attrib['Sample'], audio.note(pitch)))
        for sample, key in selected:
            matches = list((source / 'samples/SampleBank_0').glob(
                'Sample%03d*.wav' % int(sample.rsplit('_', 1)[1])))
            if len(matches) != 1:
                raise ValueError('Expected one decoded source sample: ' + sample)
            path = matches[0]
            pcm, rate, unity = audio.decode(path)
            data = audio.render(pcm, rate, unity, unity if key is None else key, duration)
            rendered.append([v if v < 128 else v - 256 for v in data])
            sources.append(dict(sample=sample, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        count = max(map(len, rendered))
        mixed = [max(-127, min(127, round(sum(p[i] if i < len(p) else 0 for p in rendered)
                                            / len(rendered)))) for i in range(count)]
        if name == 'dash':
            mixed = [v if v < 128 else v-256 for v in fairy_audio.dash_sample(source, audio)]
            count = len(mixed)
        if loop and count > 256:
            # Join the finite source window with a short crossfade.
            for i in range(128):
                mixed[count - 128 + i] = round((mixed[count - 128 + i] * (128-i) + mixed[i] * i)/128)
            mixed = mixed[128:]
        records.append(dict(name=name, offset=len(bank), length=len(mixed), loop=loop,
                            channel=channel, layers=layers, samples=sources))
        bank.extend(v & 255 for v in mixed)
        bank.extend(bytes(4 + (-len(bank) % 2)))
    fairy, fairy_loop = fairy_audio.flight_sample(oot, source, audio)
    records.append(dict(name='navi_fly', offset=len(bank), length=len(fairy),
                        loop=True, loop_start=fairy_loop, channel='CHAN_2582', rate=11025))
    bank.extend(fairy)
    bank.extend(bytes(4 + (-len(bank) % 2)))
    # EnDemo / CS_MISC_DEKU_TREE_DEATH: source layered creak, bounded to its
    # 580 sequence ticks. Existing opening indices remain stable.
    mixed=[]
    sources=[]
    for instrument,start,end in ((77,'D3','F3'),(80,'B0','D1')):
        sample=font.find('.//Instrument[@ProgramNumber="%d"]'%instrument).attrib['Sample']
        path=next((source/'samples/SampleBank_0').glob('Sample%03d*.wav'%int(sample.rsplit('_',1)[1])))
        pcm,rate,unity=audio.decode(path)
        data=audio.render_glide(pcm,rate,unity,audio.note(start),audio.note(end),580/96,audio.RATE)
        mixed.append([v if v<128 else v-256 for v in data])
        sources.append(dict(sample=sample,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    data=bytes(max(-127,min(127,sum(x[i] if i<len(x) else 0 for x in mixed)//2))&255 for i in range(max(map(len,mixed))))
    records.append(dict(name='tree_death',offset=len(bank),length=len(data),loop=False,channel='CHAN_2862',samples=sources))
    bank.extend(data);bank.extend(bytes(4+(-len(bank)%2)))
    if audio.BASE + len(bank) > 0x80000:
        raise ValueError('Opening effects exceed reserved sound RAM')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'OPENING.PCM').write_bytes(bank)
    lines = ['/* Generated by build_opening_audio.py. */', '#ifndef OPENING_AUDIO_DATA_H',
             '#define OPENING_AUDIO_DATA_H', '#define OPENING_PCM_BYTES %d' % len(bank),
             '#define OPENING_PCM_COUNT %d' % len(records),
             'static const action_pcm_t opening_pcm[] = {']
    lines += ['    {%d, %d},' % (r['offset'], r['length']) for r in records]
    lines += ['};'] + fairy_audio.tables(fairy_loop) + ['#endif']
    (output / 'opening_audio_data.h').write_text('\n'.join(lines) + '\n')
    (output / 'opening_audio.json').write_text(json.dumps(
        dict(base=audio.BASE, bytes=len(bank), rate=audio.RATE, samples=records,
             limitations=__doc__), indent=2) + '\n')
    print('Opening SFX: %d samples, %d bytes, %d spare' %
          (len(records), len(bank), 0x80000-audio.BASE-len(bank)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT.parent/'shared/build/audio-source/extracted/assets/audio')
    parser.add_argument('--output', type=Path, default=ROOT/'build/generated')
    args = parser.parse_args()
    build(args.oot, args.source, args.output)
