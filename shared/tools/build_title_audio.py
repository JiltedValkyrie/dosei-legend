#!/usr/bin/env python3
"""Build a live SCSP score from ZeldaRET's fresh US 1.2 extraction.

No fan MIDI or legacy generated tables are inputs. The supported opcode set
covers seq_30 and seq_60; unexpected instructions fail the build.
Expressive effects omitted by this port are recorded in the manifest.
"""
import argparse
import bisect
import hashlib
import json
import math
import re
import struct
import wave
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FPS = 60
VOICES = 24
SAMPLE_BASE = 0x1000
MUSIC_SAMPLE_BUDGET = 159600   # +33% over the 120000-sample music budget
# Opcodes with no counterpart in the SCSP player, recorded per score rather
# than silently dropped. `panweight` blends a note's own pan with its channel's;
# this player takes pan from the channel alone, so the blend has nothing to
# apply. The existing title and forest scores never emit it -- it turned up
# first in the opening cutscene sequences.
OMITTED = {'mutebhv', 'mutescale', 'initchan', 'freechan', 'notepri',
           'reverb', 'vibdepth', 'ldfilter', 'filter', 'freefilter', 'noshort',
           'panweight',
           # All-scenes area themes: SCSP has no comb filter or reverb index;
           # 'env' (channel envelope override) falls back to the instrument's.
           'combfilter', 'reverbidx', 'env',
           # Channel release-rate override: the instrument's own release used.
           'releaserate'}


def pitch(name):
    # z64's A0 is MIDI 21. Work directly in MIDI for WAV unity-note tuning.
    m = re.fullmatch(r'(C|DF|D|EF|E|F|GF|G|AF|A|BF|B)(\d+)', name)
    assert m, name
    return 12 * (int(m[2]) + 1) + ['C','DF','D','EF','E','F','GF','G','AF','A','BF','B'].index(m[1])


def parse(path):
    instructions, labels = [], {}
    for line in path.read_text().splitlines():
        line = line.strip()
        m = re.match(r'\.(sequence|channel|layer)\s+(\w+)', line)
        if m:
            labels[m[2]] = len(instructions)
        elif re.fullmatch(r'\w+:', line):
            labels[line[:-1]] = len(instructions)
        m = re.match(r'/\*.*?\*/\s*(\w+)\s*(.*)', line)
        if not m:
            continue
        args = []
        for a in m[2].split(',') if m[2] else []:
            a = a.strip()
            if a.startswith('PITCH_'):
                args.append(pitch(a[6:]))
            elif re.fullmatch(r'SF\d+_INST_\d+', a):
                args.append(int(a.rsplit('_', 1)[1]))
            elif a.startswith('IO_PORT_'):
                args.append(int(a[8:]))
            else:
                try:
                    args.append(int(a, 0))
                except ValueError:
                    args.append(a)
        instructions.append((m[1], args))
    return instructions, labels


@dataclass
class Script:
    pc: int
    wake: int = 0
    stack: list = field(default_factory=list)
    done: bool = False
    last_delay: int = 0
    transpose: int = 0
    value: int = 0


def interpret(path, loop_label='SEQ_0027', stop_at_loop=False, pitch_automation=False):
    """Play one sequence out and collect its notes.

    Normally playback ends when the sequence reaches its `end` opcode. Some
    sequences never do: the opening's cutscene cues sit in a `jump` back to
    their own loop label and play until the game stops them. For those,
    stop_at_loop takes the SECOND arrival at the loop label as the end, which
    captures exactly one pass -- the whole cue, once.
    """
    code, labels = parse(path)
    seq = Script(labels['SEQ_0000'])
    channels, notes, tempo, volumes = {}, [], [], {}
    ignored = set()
    loop_start = None
    loop_visits = 0
    seq_volume = 127
    finished = False
    io = [-1] * 8  # Fresh playback, not a game-requested section resume.

    def run(script, tick, kind, channel=None, channel_id=None):
        nonlocal finished, loop_start, seq_volume, loop_visits
        if script.done or tick < script.wake:
            return
        for _ in range(10000):
            if kind == 'sequence' and script.pc == labels[loop_label]:
                # First visit is the loop point; a later one is the wrap.
                if loop_start is None or not stop_at_loop:
                    loop_start = tick
                loop_visits += 1
                if stop_at_loop and loop_visits > 1:
                    # Back at the top: one complete pass is captured.
                    finished = True
                    script.done = True
                    return
            op, a = code[script.pc]
            script.pc += 1
            if op in ('delay', 'cdelay', 'ldelay'):
                script.wake = tick + a[0]
                return
            if op == 'delay1':
                script.wake = tick + 1
                return
            if op == 'call':
                script.stack.append(script.pc)
                script.pc = labels[a[0]]
            elif op == 'end':
                if script.stack:
                    script.pc = script.stack.pop()
                else:
                    script.done = True
                    # A sequence that runs off its own end is over. Only a
                    # `jump` back to the loop label used to count as finished,
                    # so a one-shot cue -- the nightmare's fanfare has no loop
                    # at all -- ran until the tick limit and was rejected.
                    if kind == 'sequence':
                        finished = True
                    return
            elif op in ('jump','rjump'):
                if kind == 'sequence' and a[0] == loop_label:
                    finished = True
                    return
                script.pc = labels[a[0]]
            elif op == 'ldi':
                script.value = (a[0] + 128) % 256 - 128
            elif op == 'ldio':
                # Channels have their own soundScriptIO ports (seqplayer.c);
                # nothing writes them from outside here, so unset reads -1.
                ports = io if kind == 'sequence' else channel.setdefault('io', {})
                script.value = ports[a[0]] if kind == 'sequence' else ports.get(a[0], -1)
                if a[0] < 2:
                    ports[a[0]] = -1
            elif op == 'stio':
                (io if kind == 'sequence' else channel.setdefault('io', {}))[a[0]] = script.value
            elif op == 'sub':
                script.value = (script.value - a[0] + 128) % 256 - 128
            elif op in ('beqz', 'rbeqz', 'rbltz'):
                if (script.value < 0 if op == 'rbltz' else script.value == 0):
                    script.pc = labels[a[0]]
            elif op == 'transpose':
                assert kind == 'layer', 'Only layer transpose implemented'
                script.transpose = (a[0] + 128) % 256 - 128
            elif op == 'tempo':
                assert kind == 'sequence'
                tempo.append((tick, a[0]))
            elif op in ('ldchan','rldchan'):
                slot, label = a
                c = channels.setdefault(slot, {'program': None, 'pan': 64, 'vol': 127, 'volexp': 128})
                c.update(script=Script(labels[label], tick), layers={})
                volumes.setdefault(slot, [(0, c['vol'] * c['volexp'] / 128)])
            elif op in ('ldlayer','rldlayer'):
                channel['layers'][a[0]] = Script(labels[a[1]], tick)
            elif op == 'instr':
                assert kind == 'channel'
                channel['program'] = a[0]
            elif op == 'pan':
                channel['pan'] = a[0]
            elif op == 'bend':
                # En_Owl's cue explicitly restores neutral channel pitch.
                # A nonzero bend needs a time-varying pitch lane; never drop it.
                if kind != 'channel' or (a[0] != 0 and not pitch_automation):
                    raise ValueError('Non-neutral channel bend requires pitch automation')
                channel.setdefault('bend_lane',[(0,0)]).append((tick,max(-127,(a[0]+128)%256-128)))
            elif op == 'volexp':
                assert kind == 'channel'
                # seqplayer.c/effects.c: channel volumeScale, before squaring.
                channel['volexp'] = a[0]
                volumes[channel_id].append((tick, channel['vol'] * a[0] / 128))
            elif op == 'vol':
                if kind == 'sequence':
                    seq_volume = a[0]
                else:
                    channel['vol'] = a[0]
                    volumes[channel_id].append((tick, a[0] * channel['volexp'] / 128))
            elif op in ('notedvg', 'notedv', 'notevg'):
                assert kind == 'layer'
                if op == 'notevg':
                    key, velocity, gate = a
                    delay = script.last_delay
                else:
                    key, delay, velocity = a[:3]
                    gate = a[3] if op == 'notedvg' else 0
                    script.last_delay = delay
                if delay <= 0 or channel['program'] is None:
                    # No instrument yet (or zero length): the N64 plays
                    # nothing audible here either. Skip, keep the timing.
                    ignored.add('note_without_instrument')
                    script.wake = tick + max(delay, 1) if delay > 0 else tick
                    if delay > 0:
                        return
                    continue
                notes.append(dict(tick=tick, end_tick=tick + delay - ((delay * gate) >> 8),
                                  program=channel['program'],
                                  key=key + script.transpose, velocity=velocity,
                                  pan=channel['pan'], channel=channel_id,
                                  bend_lane=channel.setdefault('bend_lane',[(0,0)])))
                script.wake = tick + delay
                return
            elif op in OMITTED:
                ignored.add(op)
            else:
                raise ValueError(f'Unsupported {kind} opcode: {op}')
        raise ValueError('Script did not yield')

    for tick in range(100000):
        run(seq, tick, 'sequence')
        if finished:
            assert loop_start is not None
            return notes, tempo, volumes, seq_volume, loop_start, tick, sorted(ignored)
        for channel_id, c in sorted(channels.items()):
            run(c['script'], tick, 'channel', c, channel_id)
            for _, layer in sorted(c['layers'].items()):
                run(layer, tick, 'layer', c, channel_id)
    raise ValueError('No sequence loop found')


def timeline(tempo, end):
    times = [0.0]
    index = 0
    for tick in range(end + 1):
        while index + 1 < len(tempo) and tempo[index + 1][0] <= tick:
            index += 1
        times.append(times[-1] + 60 / (48 * tempo[index][1]))
    return times


def wav_source(path):
    with wave.open(str(path)) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        rate = w.getframerate()
        pcm = struct.unpack('<%dh' % w.getnframes(), w.readframes(w.getnframes()))
    raw = path.read_bytes()
    pos = 12
    while pos + 8 <= len(raw):
        kind, size = struct.unpack_from('<4sI', raw, pos)
        body = pos + 8
        if kind == b'smpl':
            unity = struct.unpack_from('<I', raw, body + 12)[0]
            loops = struct.unpack_from('<I', raw, body + 28)[0]
            if loops == 0:
                # A one-shot: percussion and similar, which the cutscene
                # soundfonts use and the title's did not. The SCSP always
                # loops, so the loop is pinned to the final sample, where the
                # tail has already decayed. Playing it through and repeating
                # one dead sample is the closest this player can get to "stop".
                return pcm, rate, unity, max(0, len(pcm) - 1)
            assert loops == 1, path
            start, end = struct.unpack_from('<II', raw, body + 44)
            assert 0 <= start < end <= len(pcm)
            return pcm[:end], rate, unity, start
        pos = body + size + (size & 1)
    raise ValueError(f'No sample loop: {path}')


def resample(pcm, ratio, loop_start):
    """32-tap windowed-sinc lowpass with periodic extension at the loop end."""
    result = []
    cutoff = min(1.0, ratio) * 0.95
    for i in range(int(len(pcm) * ratio)):
        x = i / ratio
        center = int(x)
        value = weight = 0.0
        for j in range(center - 15, center + 17):
            distance = x - j
            if abs(distance) >= 16:
                continue
            z = math.pi * cutoff * distance
            w = (math.sin(z) / z if z else 1.0) * (0.5 + 0.5 * math.cos(math.pi * distance / 16))
            k = max(0, j)
            if k >= len(pcm):
                k = loop_start + (k - len(pcm)) % (len(pcm) - loop_start)
            value += pcm[k] * w
            weight += w
        result.append(max(-32768, min(32767, round(value / weight))))
    return result


def sample_path(source, name):
    _, bank, sample = name.split('_')
    directory = source / f'samples/SampleBank_{int(bank)}'
    # Extractor pads large banks to three digits, small banks to one. Resolve
    # the original numeric identity rather than assuming bank zero's width.
    matches = [p for p in directory.glob('Sample*.wav')
               if p.stem.removeprefix('Sample').isdigit()
               and int(p.stem.removeprefix('Sample')) == int(sample)]
    if len(matches) != 1:
        raise FileNotFoundError(f'{name}: expected one sample in {directory}, got {len(matches)}')
    return matches[0]


def load_font(source, font_id=6):
    font = ET.parse(source / f'soundfonts/Soundfont_{font_id}.xml').getroot()
    envelopes = {e.attrib['Name']: dict(release=int(e.attrib['Release']),
                 points=[(int(p.attrib['Delay']), int(p.attrib['Arg'])) for p in e])
                 for e in font.find('Envelopes')}
    instruments = {int(e.attrib['ProgramNumber']): dict(e.attrib) for e in font.find('Instruments')}
    # FONTANY_INSTR_DRUM: the note picks a drum; each drum plays at a fixed
    # pitch (its BaseNote tuning, native rate when absent). CD fanfares only;
    # no music bank sequence uses drums.
    drums = font.find('Drums')
    if drums is not None:
        instruments['FONTANY_INSTR_DRUM'] = [dict(d.attrib) for d in drums]
    names = sorted({e.attrib['Name'] for e in font.find('Samples')})
    original = []
    hashes = {}
    for name in names:
        p = sample_path(source, name)
        original.append(wav_source(p))
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    # 16-bit samples. Human approved +33% on 2026-09-28: 159600 samples.
    # Music occupies roughly 319 KB; SFX begin at 0x50000.
    ratio = min(1.0, MUSIC_SAMPLE_BUDGET / sum(len(pcm) for pcm, *_ in original))
    samples, blob = [], bytearray()
    for name, (pcm, rate, unity, loop) in zip(names, original):
        # SCSP loop registers address at most 65535 samples per instrument,
        # independently of the whole bank budget (Deku Tree's long drone).
        # Resample that instrument further, preserving pitch via its rate.
        out_rate = max(1, int(rate * min(ratio, 65530 / len(pcm))))
        actual_ratio = out_rate / rate
        data = resample(pcm, actual_ratio, loop)
        start = int(loop * actual_ratio)
        end = len(data)
        # A one-shot's loop point is its last sample, which resampling can push
        # onto the end; keep it inside the data.
        if start >= end:
            start = end - 1
        assert 0 <= start < end < 65535
        # SCSP LEA is a sample index. Guard samples repeat LSA at LEA and
        # beyond, so interpolation cannot read the next instrument's data.
        data.extend(data[start:start + 4])
        samples.append(dict(name=name, offset=len(blob), loop_start=start,
                            loop_end=end, rate=out_rate, source_rate=rate, unity=unity, pcm=data))
        blob.extend(struct.pack('>%dh' % len(data), *data))
    assert SAMPLE_BASE + len(blob) < 0x80000
    return envelopes, instruments, samples, blob, hashes


def scsp_pitch(rate):
    octave = math.floor(math.log2(rate / 44100))
    fns = round((rate / (44100 * 2 ** octave) - 1) * 1024)
    if fns == 1024:
        octave += 1
        fns = 0
    assert -8 <= octave <= 7 and 0 <= fns < 1024, rate
    return ((octave & 15) << 11) | fns


def envelope_level(env, age):
    # NTSC 32 kHz: 3 audio ticks/video frame. effects.c truncates each
    # delay * (3/4) to an integer; targets are squared before interpolation.
    current = 0.0
    for delay, arg in env['points']:
        duration = max(1, int(delay * 0.75)) / 180.0
        target = (arg / 32767) ** 2
        if age < duration:
            return current + (target - current) * max(0, age) / duration
        age -= duration
        current = target
    return current


def release_seconds(index):
    if index >= 251:
        return {255: .25, 254: .33, 253: .5, 252: .66, 251: .75}[index] / 60
    if index >= 128:
        return (251 - index) / 60
    if index >= 16:
        return 4 * (143 - index) / 60
    if index:
        return 60 * (23 - index) / 60
    # Rate zero does not decay. Nonlooping samples still stop at their end;
    # looping samples retain their level until the score/voice allocator ends.
    return math.inf


def volume_at(changes, tick):
    return changes[bisect.bisect_right(changes, (tick, 1000)) - 1][1]


def bake(notes, times, changes, seq_volume, envelopes, instruments, samples, end_tick,
         limit_one_shots=False, steal_releasing=False):
    frames = round(times[end_tick] * FPS)
    levels = bytearray([255]) * (frames * VOICES)
    available = [0] * VOICES
    triggers, cooked = [], []
    for n in sorted(notes, key=lambda n: n['tick']):
        instrument = instruments[n['program']]
        if n['program'] == 'FONTANY_INSTR_DRUM':
            drum = next(d for d in instrument
                        if pitch(d['NoteStart']) <= n['key'] <= pitch(d['NoteEnd']))
            instrument = dict(Envelope=drum['Envelope'], Sample=drum['Sample'],
                              BaseNote=drum.get('BaseNote', 'C4'))
            n = dict(n, key=pitch('C4'))
        env = envelopes[instrument['Envelope']]
        variant = ('Lo' if n['key'] < pitch(instrument.get('RangeLo', 'C0')) else
                   'Hi' if n['key'] > pitch(instrument.get('RangeHi', 'B9')) else '')
        sample = next(s for s in samples if s['name'] == instrument['Sample' + variant])
        # Soundfont 15 overrides the high split's base note for program 14.
        unity = pitch(instrument['BaseNote' + variant]) if 'BaseNote' + variant in instrument else sample['unity']
        rate = sample['rate'] * 2 ** ((n['key'] - unity) / 12)
        if 'SampleRate' + variant in instrument:
            rate *= int(instrument['SampleRate' + variant]) / sample['source_rate']
        unbent_rate=rate
        # seqplayer.c: gBendPitchOneOctaveFrequencies[(u8)(bend+128)].
        # Table is 2**(signed/127), clamped at -127 (duplicated first entry).
        bend=next((b for t,b in reversed(n.get('bend_lane',())) if t<=n['tick']),0)
        rate *= 2**(bend/127)
        start = times[n['tick']]
        gate = times[min(n['end_tick'], end_tick)]
        gate_level = envelope_level(env, gate - start)
        release = release_seconds(env['release'])
        stop = times[end_tick] if math.isinf(release) else min(times[end_tick], gate + gate_level * release)
        if limit_one_shots and sample["loop_end"] - sample["loop_start"] <= 1:
            stop = min(stop, start + sample["loop_end"] / rate)
        first, last = round(start * FPS), min(frames, math.ceil(stop * FPS))
        if n['velocity'] == 0 or first >= frames:
            continue
        gains = []
        for f in range(first, last):
            t = max(start, f / FPS)
            amp = (envelope_level(env, t - start) if t < gate else
                   max(0.0, gate_level - (t - gate) / release))
            tick = bisect.bisect_right(times, min(t, gate - 1e-8)) - 1
            channel = volume_at(changes[n['channel']], tick)
            # effects.c: squared note velocity * squared channel/sequence gain.
            gain = amp * (n['velocity'] / 127) ** 2 * (channel / 127 * seq_volume / 127) ** 2
            # Fade the last 4 frames at the wrap to avoid a discontinuity.
            gain *= min(1.0, (frames - 1 - f) / 4)
            gains.append(gain)
        if not any(g > 1e-5 for g in gains):
            continue
        slot = next((i for i, end in enumerate(available) if end <= first), None)
        if slot is None and steal_releasing:
            # Reclaim a releasing voice before dropping a new attack. Select
            # the quietest tail at this frame; existing scores opt out.
            releasing = [n for n in cooked
                         if times[min(n['end_tick'], end_tick)] <= start
                         and n['end_frame'] > first]
            if releasing:
                victim = max(releasing, key=lambda n: levels[first * VOICES + n['slot']])
                slot = victim['slot']
                for frame in range(first, available[slot]):
                    if frame < frames: levels[frame * VOICES + slot] = 255
                victim['end_frame'] = first
        assert slot is not None, 'Polyphony exceeds SCSP voice budget'
        available[slot] = last + 1  # one fully silent frame before reuse
        for i, gain in enumerate(gains):
            # One TL unit is 1/16 of an amplitude halving (SEGA SCSP manual).
            levels[(first + i) * VOICES + slot] = (255 if gain <= 1e-5 else
                min(254, max(0, round(-16 * math.log2(gain)))))
        # DIPAN attenuation: approximate equal-power stereo using the 3 dB steps.
        angle = n['pan'] / 127 * math.pi / 2
        left, right = math.cos(angle), math.sin(angle)
        small, large = min(left, right), max(left, right)
        amount = 15 if small < 1e-6 else min(15, round(-20 * math.log10(small / large) / 3))
        pan = amount | (0x10 if left > right else 0)
        triggers.append((first, slot, samples.index(sample), scsp_pitch(rate), pan))
        cooked.append(dict(n, frame=first, end_frame=last, slot=slot, rate=rate,
                           sample=samples.index(sample), gains=gains,unbent_rate=unbent_rate))
    # Pitch-only commands never key-on a voice. Add after voice stealing so an
    # old note cannot bend its replacement; attacks at the same frame win.
    pitch_events={}
    for n in cooked:
        for tick,bend in n.get('bend_lane',()):
            f=round(times[min(tick,end_tick)]*FPS)
            if n['frame']<f<n['end_frame']:
                pitch_events[(f,n['slot'])]=(f,n['slot'],255,scsp_pitch(n['unbent_rate']*2**(bend/127)),0)
    triggers.extend(pitch_events.values())
    triggers.sort(key=lambda t:(t[0],0 if t[2]==255 else 1,t[1]))
    return frames, levels, triggers, cooked


def preview(path, seconds, frames, levels, cooked, samples):
    """Host reference of the generated PCM/pitch/volume data; not emulator capture."""
    hz = 22050
    count = min(round(seconds * hz), round(frames / FPS * hz))
    left, right = [0.0] * count, [0.0] * count
    for n in cooked:
        sample = samples[n['sample']]
        pcm = sample['pcm']
        begin = round(n['frame'] / FPS * hz)
        end = min(count, round(n['end_frame'] / FPS * hz))
        angle = n['pan'] / 127 * math.pi / 2
        l, r = math.cos(angle), math.sin(angle)
        for i in range(begin, end):
            pos = (i - begin) * n['rate'] / hz
            if pos >= sample['loop_end']:
                pos = sample['loop_start'] + (pos - sample['loop_end']) % (sample['loop_end'] - sample['loop_start'])
            k = int(pos)
            value = pcm[k] + (pcm[k + 1] - pcm[k]) * (pos - k)
            frame = min(frames - 1, i * FPS // hz)
            tl = levels[frame * VOICES + n['slot']]
            gain = 0 if tl == 255 else 2 ** (-tl / 16)
            left[i] += value * gain * l
            right[i] += value * gain * r
    peak = max(max(map(abs, left)), max(map(abs, right)))
    assert peak <= 32767, f'Preview clipping: {peak}'
    output = bytearray()
    for l, r in zip(left, right):
        output.extend(struct.pack('<hh', round(l), round(r)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setparams((2, 2, hz, 0, 'NONE', 'not compressed'))
        w.writeframes(output)
    return peak / 32768


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=ROOT / 'build/audio-source/extracted/assets/audio')
    p.add_argument('--preview', type=Path)
    p.add_argument('--preview-seconds', type=float, default=80)
    args = p.parse_args()
    envelopes, instruments, samples, pcm, hashes = load_font(args.source)
    seq = args.source / 'sequences/seq_30.seq'
    notes, tempo, volumes, seqvol, loop_start, end, omitted = interpret(seq)
    times = timeline(tempo, end)
    frames, levels, triggers, cooked = bake(notes, times, volumes, seqvol,
                                           envelopes, instruments, samples, end)
    (ROOT / 'assets/audio/title/TITLE_PCM.RAW').write_bytes(pcm)
    (ROOT / 'assets/audio/title/TITLE_LEVELS.RAW').write_bytes(levels)
    loop_frame = round(times[loop_start] * FPS)
    header = ['/* Generated from US 1.2 by tools/build_title_audio.py. */',
              '#ifndef TITLE_SCORE_H', '#define TITLE_SCORE_H', '#include <stdint.h>',
              f'#define TITLE_VOICES {VOICES}', f'#define TITLE_FRAMES {frames}',
              f'#define TITLE_LOOP_FRAME {loop_frame}', f'#define TITLE_SAMPLE_BASE {SAMPLE_BASE}',
              f'#define TITLE_PCM_BYTES {len(pcm)}',
              f'#define TITLE_TRIGGER_COUNT {len(triggers)}',
              'typedef struct { uint32_t offset; uint16_t loop_start, loop_end; } title_pcm_t;',
              'typedef struct { uint16_t frame; uint8_t slot, sample; uint16_t pitch; uint8_t pan; } title_trigger_t;',
              'static const title_pcm_t title_pcm[] = {']
    header += [f'    {{ {s["offset"]}, {s["loop_start"]}, {s["loop_end"]} }},' for s in samples]
    header += ['};', 'static const title_trigger_t title_triggers[] = {']
    header += ['    { %d, %d, %d, %d, %d },' % t for t in triggers]
    header += ['};', '#endif', '']
    (ROOT / 'assets/audio/title').mkdir(parents=True, exist_ok=True)
    (ROOT / 'assets/audio/title/title_score.h').write_text('\n'.join(header))
    manifest = dict(version='ntsc-1.2 US', rom_md5='57a9719ad547c516342e1a15d5c28c3d',
                    sequence_sha256=hashlib.sha256(seq.read_bytes()).hexdigest(),
                    sample_sha256=hashes, notes=len(notes), triggers=len(triggers), tempo_changes=tempo,
                    intro_seconds=times[loop_start], total_seconds=times[end], pcm_bytes=len(pcm),
                    levels_bytes=len(levels), omitted_opcodes=omitted,
                    samples=[{k:v for k,v in s.items() if k!='pcm'} for s in samples])
    if args.preview:
        manifest['preview_peak'] = preview(args.preview, args.preview_seconds, frames, levels, cooked, samples)
    (ROOT / 'assets/audio/title/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('sample_sha256','samples','tempo_changes')}, indent=2))


if __name__ == '__main__':
    main()
