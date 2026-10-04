"""Small resident OoT action bank: real samples, reduced single-layer SFX.

Rupee pickup includes its source three-note synthetic layer plus sample bed.
Other effects use one layer; full N64 sequencing/reverb remain absent. Child attack voice rotates through the four source EFFECT entries.
Offline resampling only; signed PCM8 at 11025 Hz, voices/fairy at 5512.5 Hz.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import wave
import xml.etree.ElementTree as ET
import fairy_audio
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x50000  # above music banks at 0x1000 with 159600-sample budget
RATE = 11025
# seq_0.prg.seq layer, instrument, note, bounded one-shot seconds.
EFFECTS = (
    ('seed_fire', 'CHAN_1208', 30, 'A0', .19),
    ('seed_impact', 'LAYER_128E', 26, 'A2', .25),
    ('nut_flash', 'LAYER_1344', 41, 'DF3', .12),
    ('swing', 'LAYER_0F91', 27, 'D2', .45),
    ('shield', 'LAYER_11EF', 28, 'F3', .45),
    ('cut', 'LAYER_222C', 47, 'G3', .30),
    ('equip', 'CHAN_0FA5', 29, 'A3', .40),
    ('message', 'LAYER_5A68', 84, 'G4', .18),
    ('footstep', 'LAYER_0333', 5, 'A3', .10),
    ('roll', 'CHAN_0731', 27, 'D2', .18),
    ('rupee', 'LAYER_587A', 91, 'C5', .30),  # NA_SE_SY_GET_RUPY sample layer
    ('navi_dash', 'CHAN_1B01', 69, 'B5', .65),  # NA_SE_EV_FAIRY_DASH
    # M2c combat (forest area bank). NA_SE_IT_WALL_HIT_HARD (SOFT reuses it
    # at its own pitch in action_audio.c), NA_SE_IT_SHIELD_REFLECT_SW first
    # layer, NA_SE_EN_OCTAROCK_ROCK (Soundfont 1 INST_40, sample bank 0).
    ('wall_hit', 'CHAN_1187', 26, 'E2', .25),
    ('reflect', 'CHAN_0FE9', 32, 'C4', .25),
    ('nut_break', 'CHAN_43F8', 40, 'A2', .25, 1),
)
# Stored at half rate to leave sound RAM for the combat bank (BUG-036).
# Superseded 2026-09-27 by the bible's SFX rule: every effect is stored at
# half rate (below); this list only records the historical set.
HALF_RATE = ('voice', 'climb', 'navi_dash', 'shield', 'equip',
             'wall_hit', 'reflect', 'nut_break')

# Per-area SFX banks (demo plan M0). Core = ACTIONS.PCM, resident in every
# gameplay scene (Link, UI, Navi, rupee). Area sounds live in one swappable
# bank loaded right after the core on scene load; bank 0 is "no area sounds".
# A sound may appear in several banks. Scenes pick a bank by `sfx` in
# build_scene_table.SCENES. OPENING.PCM still replaces the whole region.
# Source channels; reduced sample renderer omits vibrato/legato/glide and the
# shared FONTANY_INSTR_SFX layer, as with the resident combat effects.
DUNGEON_CHANNELS = (
    ('owl_flap','CHAN_4F7F'),
    ('scrub_up', 'CHAN_3ECF'),
    ('scrub_down', 'CHAN_3EE2'),
    ('scrub_throw', 'CHAN_3EF5'),
    ('scrub_walk', 'CHAN_3F05'),
    ('scrub_hit', 'CHAN_3F12'),
    ('scrub_faint', 'CHAN_4966'),
    ('foot_switch', 'CHAN_1A8F'),
    ('deku_hit', 'CHAN_3B76'),
    ('deku_dead', 'CHAN_3B8E'),
    ('skull_hit', 'CHAN_3FD0'),
    ('skull_dead', 'CHAN_4001'),
    ('larva_hit', 'CHAN_36B3'),
    ('larva_dead', 'CHAN_36F9'),
    ('gohma_hit', 'CHAN_381C'),
    ('gohma_dead', 'CHAN_3E7F'),
    ('correct', 'CHAN_5833'),
    ('appear', 'CHAN_589F'),
    ('door_open', 'CHAN_1A7E'),
    ('door_close', 'CHAN_1B14'),
    ('freeze', 'CHAN_4C1B'),
    ('box_item', 'CHAN_5CB9'),

)
AREA_SOUNDS = ('cut', 'wall_hit', 'reflect', 'nut_break',
               'baba_mouth', 'baba_dead', 'baba_awaken', 'baba_ground', 'tree_open') + tuple(n for n, _ in DUNGEON_CHANNELS)
AREA_BANKS = (
    (None, ()),                     # 0: interiors, nothing area-specific
    # 1: outdoor forest: grass cutting and the M2c combat sounds.
    ('SFXFRST.PCM', ('cut', 'wall_hit', 'reflect', 'nut_break',
                     'baba_mouth', 'baba_dead', 'baba_awaken', 'baba_ground', 'tree_open','box_item','owl_flap')),
    ('SFXTREE.PCM', tuple(n for n in AREA_SOUNDS if n not in ('tree_open','gohma_hit','gohma_dead','owl_flap'))),
    ('SFXBOSS.PCM', ('wall_hit','reflect','nut_break','larva_hit','larva_dead','gohma_hit','gohma_dead','door_open','door_close','freeze','correct')),
)


def note(name):
    match = re.fullmatch(r'(C|DF|D|EF|E|F|GF|G|AF|A|BF|B)(\d)', name)
    return 12 * (int(match[2]) + 1) + ['C','DF','D','EF','E','F','GF','G','AF','A','BF','B'].index(match[1])


def decode(path):
    with wave.open(str(path)) as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError('Expected mono PCM16: ' + str(path))
        rate = wav.getframerate()
        pcm = struct.unpack('<%dh' % wav.getnframes(), wav.readframes(wav.getnframes()))
    raw = path.read_bytes()
    pos, unity = 12, None
    while pos + 8 <= len(raw):
        size = struct.unpack_from('<I', raw, pos + 4)[0]
        if raw[pos:pos+4] == b'smpl':
            unity = struct.unpack_from('<I', raw, pos + 20)[0]
        pos += 8 + size + (size & 1)
    if unity is None:
        raise ValueError('Missing sample tuning: ' + str(path))
    return pcm, rate, unity


def render(pcm, rate, unity, key, duration, output_rate=None):
    output_rate = RATE if output_rate is None else output_rate
    playback = rate * 2 ** ((key - unity) / 12)
    count = min(round(duration * output_rate), int(len(pcm) * output_rate / playback))
    output = bytearray()
    # Low-pass windowed sinc; zero extension, never loop into another sound.
    cutoff = min(1., output_rate / playback) * .95
    for i in range(count):
        x = i * playback / output_rate
        value = weight = 0.
        for j in range(int(x)-15, int(x)+17):
            d = x-j
            if abs(d) >= 16: continue
            z = math.pi * cutoff * d
            w = (math.sin(z)/z if z else 1.) * (.5 + .5*math.cos(math.pi*d/16))
            value += (pcm[j] if 0 <= j < len(pcm) else 0) * w
            weight += w
        fade = min(1., i/32, (count-1-i)/110)
        output.append(max(-127, min(127, round(value/weight * fade * .8 / 256))) & 255)
    return bytes(output)


def render_path(pcm, rate, unity, segments, output_rate):
    """Legato/portamento: (key0, key1, seconds, gain) segments played on one
    running sample position, pitch moving linearly in semitones."""
    out, x = bytearray(), 0.
    for key0, key1, seconds, gain in segments:
        count = round(seconds * output_rate)
        for i in range(count):
            key = key0 + (key1 - key0) * i / max(1, count - 1)
            j = int(x)
            if j + 1 >= len(pcm):
                return bytes(out)
            v = (pcm[j] + (pcm[j + 1] - pcm[j]) * (x - j)) * gain
            out.append(max(-128, min(127, round(v / 256))) & 255)
            x += rate * 2 ** ((key - unity) / 12) / output_rate
    return bytes(out)


def render_wave(notes, output_rate, shape):
    """Synthetic FONTANY waves; a None key is a rest."""
    out, phase = bytearray(), 0.
    for key, seconds, gain in notes:
        count = round(seconds * output_rate)
        if key is None:
            out += bytes(count)
            continue
        freq = 440 * 2 ** ((key - 69) / 12)
        for i in range(count):
            t = phase % 1.
            v = ((4 * t - 1) if t < .5 else (3 - 4 * t)) if shape == 'triangle' else \
                (2 * t - 1) if shape == 'sawtooth' else (1 if t < .5 else -1)
            out.append(max(-128, min(127, round(v * 100 * gain))) & 255)
            phase += freq / output_rate
    return bytes(out)


def render_recovery(seq, output_rate):
    """NA_SE_SY_HP_RECOVER: source sine layer, three rising octave glides.

    Envelope 6720 attacks for 12 audio ticks and falls toward 5000 for 40;
    retain the existing offline SFX renderer's linear portamento convention.
    """
    block = seq.split('.layer LAYER_5971\n', 1)[1].split('.channel', 1)[0]
    glides = re.findall(r'portamento\s+0x81, PITCH_(\w+), 127.*?notedv\s+PITCH_(\w+), (\d+), (\d+)', block, re.S)
    if 'FONTANY_INSTR_SINE' not in block or len(glides) != 3:
        raise ValueError('Health recovery channel changed')
    out = bytearray()
    for start, end, ticks, velocity in glides:
        count = round(int(ticks) / 96 * output_rate)
        phase = 0.
        for i in range(count):
            t = i / output_rate
            envelope = min(1., t * 180 / 12)
            if t * 180 > 12:
                envelope = max(5000 / 32700, 1 - (t * 180 - 12) / 40 * (1 - 5000 / 32700))
            key = note(start) + (note(end) - note(start)) * i / max(1, count - 1)
            gain = (int(velocity) / 127) ** 2 * envelope * min(1., (count - i) / 16)
            out.append(round(math.sin(phase * 2 * math.pi) * 100 * gain) & 255)
            phase += 440 * 2 ** ((key - 69) / 12) / output_rate
    return bytes(out)


def render_triangle(notes, output_rate):
    """FONTANY_INSTR_TRIANGLE notes (key, seconds, gain), phase continuous."""
    out, phase = bytearray(), 0.
    for key, seconds, gain in notes:
        freq = 440 * 2 ** ((key - 69) / 12)
        for i in range(round(seconds * output_rate)):
            t = phase % 1.
            v = (4 * t - 1) if t < .5 else (3 - 4 * t)
            out.append(max(-128, min(127, round(v * 100 * gain))) & 255)
            phase += freq / output_rate
    return bytes(out)


class Unsupported(Exception):
    pass


def layer_body(seq, label, visited=()):
    """Follow bounded source layer calls, fallthrough and unconditional tail jumps."""
    if label in visited: raise Unsupported('layer cycle: '+label)
    match=re.search(r'(?m)^(?:\.layer\s+'+label+r'\b[^\n]*|'+label+r':)\n',seq)
    if not match: raise Unsupported('missing layer: '+label)
    body=[]
    for line in seq[match.end():].splitlines():
        jump=re.search(r'\*/\s*(?:rjump|jump)\s+(LAYER_\w+)',line)
        if jump:
            return '\n'.join(body)+'\n'+layer_body(seq,jump[1],visited+(label,))
        call=re.search(r'\*/\s*call\s+(LAYER_\w+)',line)
        if call:
            nested=layer_body(seq,call[1],visited+(label,))
            body.append(re.sub(r'(?m)^.*\*/\s*end\b.*$', '', nested))
            continue
        body.append(line)
        if re.search(r'\*/\s*end\b',line): return '\n'.join(body)
    raise Unsupported('unterminated layer: '+label)


def channel_layers(seq, chan):
    """A simple SFX channel: channel instr/transpose + its ldlayer blocks.
    Each layer -> (instr, transpose, [(key, ticks, velocity)]). Any opcode
    this cannot follow (calls, self-modifying stseq, jumps) raises."""
    body = seq.split('.channel %s\n' % chan, 1)[1].split('\n.', 1)[0]
    chan_instr = re.search(r'\binstr\s+(\w+)', body)
    layers = re.findall(r'ldlayer\s+\d+,\s*(LAYER_\w+)', body)
    if not layers or re.search(r'\b(stseq|ldptr|jump|rjump|call|dyncall)\b', body):
        raise Unsupported(chan)
    out = []
    for label in layers:
        # The shared FONTANY_INSTR_SFX layer is a reduced-bank omission,
        # matching the existing withered-Baba exporter (no runtime N64 synth).
        if label == 'LAYER_4829': continue
        block=layer_body(seq,label)
        if re.search(r'\b(call|jump|rjump|stseq)\b', block):
            raise Unsupported(label)
        instr = re.search(r'\binstr\s+(\w+)', block)
        instr = instr.group(1) if instr else (chan_instr.group(1) if chan_instr else None)
        t = re.search(r'transpose\s+(-?\d+)', block)
        block=re.sub(r'FRAMERATE_CONST\(\s*([^,()]+),\s*[^()]+\)',lambda m:m[1],block)
        # Notes and rests in order: a rest is (None, ticks, 0).
        notes = []
        for m in re.finditer(r'notedvg?\s+PITCH_(\w+),\s*(\d+),\s*(\d+)|\bldelay\s+(\d+)', block):
            if m.group(4):
                notes.append((None, int(m.group(4)), 0))
            else:
                notes.append((m.group(1), int(m.group(2)), int(m.group(3))))
        if not instr or not any(p for p, _, _ in notes):
            raise Unsupported(label)
        out.append((instr, int(t.group(1)) if t else 0, notes))
    return out


def render_channel(seq, chan, fonts, source, output_rate):
    """Mix a simple channel's layers; notes restart the sample (no legato)."""
    mix = []
    for instr, transpose, notes in channel_layers(seq, chan):
        run = bytearray()
        if instr in ('FONTANY_INSTR_TRIANGLE', 'FONTANY_INSTR_SAWTOOTH', 'FONTANY_INSTR_SQUARE'):
            shape = instr.rsplit('_', 1)[1].lower()
            run = bytearray(render_wave([(note(p) + transpose if p else None, tk / 96,
                                          (v / 127) ** 2) for p, tk, v in notes],
                                        output_rate, shape))
        else:
            m = re.fullmatch(r'SF(\d)_INST_(\d+)', instr)
            if not m:
                raise Unsupported(instr)
            attrib = fonts[int(m.group(1))].find('.//Instrument[@ProgramNumber="%s"]' % m.group(2)).attrib
            for p, tk, v in notes:
                if p is None:
                    run += bytes(round(tk / 96 * output_rate))
                    continue
                key = note(p) + transpose
                sample = attrib['SampleHi'] if 'RangeHi' in attrib and key > note(attrib['RangeHi']) else attrib['Sample']
                path = source / ('samples/SampleBank_0/Sample%03d.wav' % int(sample.rsplit('_', 1)[1]))
                if not path.is_file():
                    path = path.with_suffix('.half.wav')
                pcm, rate, unity = decode(path)
                # A zero-duration note followed by END leaves its one-shot
                # sample playing; use the full source sample at authored pitch.
                seconds=tk/96 if tk else len(pcm)/rate/2**((key-unity)/12)
                part = render_path(pcm, rate, unity, [(key, key, seconds, (v / 127) ** 2)], output_rate)
                run += part + bytes(max(0, round(seconds * output_rate) - len(part)))
        mix.append(run)
    length = max(len(r) for r in mix)
    out = bytearray()
    for i in range(length):
        total = sum((r[i] - 256 if r[i] > 127 else r[i]) for r in mix if i < len(r))
        out.append(max(-128, min(127, total)) & 255)
    return bytes(out)


def render_glide(pcm, rate, unity, key0, key1, duration, output_rate):
    """Portamento: pitch moves from key0 to key1 linearly in semitones."""
    count = round(duration * output_rate)
    out, x = bytearray(), 0.
    for i in range(count):
        key = key0 + (key1 - key0) * i / max(1, count - 1)
        step = rate * 2 ** ((key - unity) / 12) / output_rate
        j = int(x)
        if j + 1 >= len(pcm):
            break
        v = pcm[j] + (pcm[j + 1] - pcm[j]) * (x - j)
        out.append(max(-128, min(127, round(v / 256))) & 255)
        x += step
    return bytes(out)


def rupee_melody(oot):
    """The missing tonal layer of NA_SE_SY_GET_RUPY, not its noise/sample bed.

    Keep source oscillator in SCSP RAM and sequence three pitches at vblank.
    No long second PCM recording: 64 bytes holds all eight sawtooth periods.
    """
    seq = (oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
    block = seq.split('.layer LAYER_5868\n',1)[1].split('.layer',1)[0]
    notes = [(p,int(t),int(v)) for p,t,v in re.findall(
        r'notedv\s+PITCH_(\w+),\s*(\d+),\s*(\d+)',block)]
    if notes != [('BF4',6,80),('F4',6,80),('BF4',24,80)] or not all(
        item in block for item in ('FONTANY_INSTR_SAWTOOTH','transpose   24','ENVELOPE_6660')):
        raise ValueError('Rupee melody changed; review source sequence')
    if not re.search(r'tempo\s+120\b',seq) or '#define SEQTICKS_PER_BEAT 48' not in (oot/'include/audio.h').read_text():
        raise ValueError('Review sequence clock')
    bed = seq.split('.layer LAYER_587A\n',1)[1].split('.channel',1)[0]
    if not re.search(r'notedv\s+PITCH_C5,\s*36,\s*72',bed):
        raise ValueError('Rupee backing layer changed')
    bed_level = 12 + round(-20*math.log10((72/127)**2)/.375)
    data = (oot / 'src/audio/internal/data.c').read_text()
    wave_block = data.split('s16 gSawtoothWaveSample[] = {',1)[1].split('};',1)[0]
    wave_block = re.sub(r'//[^\n]*','',wave_block)
    wave = [int(n) for n in re.findall(r'-?\d+',wave_block)][192:256]
    if len(wave) != 64 or wave[:8]*8 != wave:
        raise ValueError('Unexpected source harmonic-8 waveform')
    pcm = bytes(max(-128,min(127,v//256)) & 255 for v in wave)
    freq_block = data.split('gPitchFrequencies[] = {',1)[1].split('};',1)[0]
    freq_block = re.sub(r'/\*.*?\*/|//[^\n]*','',freq_block,flags=re.S)
    frequencies = [float(n) for n in re.findall(r'([0-9.]+)f',freq_block)]
    # Audio_BuildSyntheticWave: harmonic 8 uses 1.0465/8 - 2.5e-6.
    pitches=[]
    for pitch,ticks,velocity in notes:
        scale = frequencies[note(pitch)+24-21]
        if scale < 4: raise ValueError('Expected harmonic-8 source note')
        rate = 32000 * scale * (1.0465/8 - 2.5e-6)
        octave = math.floor(math.log2(rate/44100))
        fine = round((rate/(44100*2**octave)-1)*1024)
        pitches.append(((octave & 15)<<11) | fine)
    env_block = seq.split('.envelope ENVELOPE_6660\n',1)[1].split('.envelope',1)[0]
    points = [(int(t),int(v)) for t,v in re.findall(r'point\s+(\d+),\s*(\d+)',env_block)]
    if points != [(1,32700),(8,32700),(8,22000),(100,15000)]:
        raise ValueError('Review rupee envelope')
    # effects.c squares targets and scales delays to 1/240 second; quantized
    # here to sequence ticks, then vblank. N64 sub-frame interpolation differs.
    levels=[]
    for tick in range(24):
        t=(tick+.5)/96; elapsed=0.; previous=0.
        for duration,target in points:
            end=elapsed+duration/240
            amplitude=(target/32767)**2
            if t <= end:
                amplitude=previous+(amplitude-previous)*(t-elapsed)/(end-elapsed)
                break
            elapsed=end; previous=amplitude
        amplitude *= (80/127)**2
        levels.append(min(255,max(0,12+round(-20*math.log10(max(amplitude,1e-9))/.375))))
    return pcm, dict(source='LAYER_5868', wave='gSawtoothWaveSample[192:256]',
                     notes=notes, transpose=24, ticks_per_second=96,
                     pitches=pitches, levels=levels, bed_level=bed_level,
                     sha256=hashlib.sha256(pcm).hexdigest())


def build(oot, source, out):
    seq = (oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
    font = ET.parse(source / 'soundfonts/Soundfont_0.xml')
    fonts = {0: font, 1: ET.parse(source / 'soundfonts/Soundfont_1.xml')}
    entries = []
    # seq_0 ARRAY_5F30's default ocarina is Soundfont 0, instrument 52.
    # Resident half-rate, bounded one-shots: no CD reads while entering notes.
    # Original D4/F4/A4/B4/D5 pitches; note lengths/vibrato remain approximate.
    ocarina = font.find('.//Instrument[@ProgramNumber="52"]').attrib['Sample']
    for i, pitch in enumerate(('D4', 'F4', 'A4', 'B4', 'D5')):
        entries.append(('ocarina%d' % i, ocarina, note(pitch), .28, 'ARRAY_5F30 / SF0_INST_52'))
    for name, layer, inst, pitch, duration, *which in EFFECTS:
        which = which[0] if which else 0
        prefix = '.channel ' if layer.startswith('CHAN_') else '.layer '
        block = seq.split(prefix+layer+'\n', 1)[1].split('\n.channel', 1)[0]
        if prefix == '.layer ': block = block.split('\n.layer', 1)[0]
        if 'SF%d_INST_%d' % (which, inst) not in block or 'PITCH_'+pitch not in block:
            raise ValueError('OoT SFX layer changed: '+layer)
        sample = fonts[which].find('.//Instrument[@ProgramNumber="%d"]' % inst).attrib['Sample']
        entries.append((name, sample, note(pitch), duration, layer))
    array = seq.split('.array ARRAY_6347', 1)[1].split('.array', 1)[0]
    for i in range(4):
        effect = 28+i
        if 'SF0_EFFECT_%d' % effect not in array:
            raise ValueError('Child sword voice array changed')
        sample = font.find('.//Effect[@Name="EFFECT_%d"]' % effect).attrib['Sample']
        entries.append(('voice%d' % i, sample, 60, .6, 'ARRAY_6347'))
    jump_array = seq.split('.array ARRAY_64C5', 1)[1].split('.array', 1)[0]
    if 'SF0_EFFECT_53' not in jump_array:
        raise ValueError('Child jump voice array changed')
    sample = font.find('.//Effect[@Name="EFFECT_53"]').attrib['Sample']
    entries.append(('jump', sample, 60, .30, 'ARRAY_64C5'))
    # NA_SE_VO_LI_CLIMB_END_KID (CHAN_639A) picks rand 2 over this array.
    # Both takes (BUG-007's second take fits since the music half-rate change).
    climb_array = seq.split('.array ARRAY_63AB', 1)[1].split('.array', 1)[0]
    for i, effect in enumerate((35, 36)):
        if 'SF0_EFFECT_%d' % effect not in climb_array:
            raise ValueError('Child climb-end voice array changed')
        sample = font.find('.//Effect[@Name="EFFECT_%d"]' % effect).attrib['Sample']
        entries.append(('climb%d' % i, sample, 60, .6, 'ARRAY_63AB'))
    # Navi (M2d): NA_SE_VO_NA_HELLO_2 (CHAN_6520: effect = PITCH_BF2 25 +
    # (0x5F - NA_SE_VO_TA_SLEEP 0x50) + (layer transpose 1 << 6) = EFFECT_104), the
    # unlocked "Hey!"; NA_SE_VO_NAVY_CALL (CHAN_6581 -> ARRAY_65A7, one of
    # EFFECT_57/58/59 at random, velocity 100/95/105) plus layer 1, INST_69
    # portamento C5 -> F5 over 48 ticks at velocity 65 (rendered as a glide). NA_SE_VO_NAVY_HELLO/ENEMY/HEAR
    # dispatch to CHAN_612C, a bare `end`: silent in the source.
    hello = seq.split('.channel CHAN_6520\n', 1)[1].split('\n.channel', 1)[0]
    if ('PITCH_BF2' not in hello or 'NA_SE_VO_TA_SLEEP' not in hello or
            'transpose   1' not in hello):
        raise ValueError('Navi hello channel changed')
    sample = font.find('.//Effect[@Name="EFFECT_104"]').attrib['Sample']
    entries.append(('navi_hello', sample, 60, .6, 'CHAN_6520'))
    # NA_SE_VO_SK_LAUGH (0x6873, same channel): 25 + 0x23 + 64 = EFFECT_124,
    # which En_Elf plays when a C-Up talk is accepted.
    sample = font.find('.//Effect[@Name="EFFECT_124"]').attrib['Sample']
    entries.append(('navi_talk', sample, 60, .8, 'CHAN_6520'))
    call = seq.split('.array ARRAY_65A7', 1)[1].split('.array', 1)[0]
    for i, effect in enumerate((57, 58, 59)):
        if 'SF0_EFFECT_%d' % effect not in call:
            raise ValueError('Navi call array changed')
        sample = font.find('.//Effect[@Name="EFFECT_%d"]' % effect).attrib['Sample']
        entries.append(('navi_call%d' % i, sample, 60, .7, 'ARRAY_65A7'))
    chime = seq.split('.layer LAYER_6598\n', 1)[1].split('\n.array', 1)[0]
    if not all(t in chime for t in ('SF0_INST_69', 'portamento  0x81, PITCH_C5', 'PITCH_F5, 48, 65')):
        raise ValueError('Navi call chime layer changed')
    sample = font.find('.//Instrument[@ProgramNumber="69"]').attrib['Sample']
    entries.append(('navi_chime', sample, (note('C5'), note('F5')), 48 / 96, 'LAYER_6598'))
    # NA_SE_SY_LOCK_ON (LAYER_5CB1): INST_90, C4 + transpose 48 = C8, above
    # RangeHi B5, so the high sample. 97 ticks at 96 a second.
    lock = seq.split('.layer LAYER_5CB1\n', 1)[1].split('\n.channel', 1)[0]
    if 'SF0_INST_90' not in lock or 'transpose   48' not in lock or 'PITCH_C4, 97' not in lock:
        raise ValueError('Lock-on layer changed')
    inst = font.find('.//Instrument[@ProgramNumber="90"]').attrib
    entries.append(('lock_on', inst['SampleHi'], note('C4') + 48, 97 / 96, 'LAYER_5CB1'))
    # NA_SE_SY_LOCK_ON_HUMAN (LAYER_59E9): INST_84 notes, each restarted,
    # level = (velocity / 127)^2 as the N64 mixes it.
    human = seq.split('.layer LAYER_59E9' + chr(10), 1)[1].split(chr(10) + '.channel', 1)[0]
    notes = [(note(p), int(t) / 96, (int(v) / 127) ** 2) for p, t, v in
             re.findall(r'notedv\s+PITCH_(\w+),\s*(\d+),\s*(\d+)', human)]
    if 'SF0_INST_84' not in human or len(notes) != 6:
        raise ValueError('Human lock-on layer changed')
    sample = font.find('.//Instrument[@ProgramNumber="84"]').attrib['Sample']
    entries.append(('lock_on_human', sample, tuple(notes), 0, 'LAYER_59E9'))
    # M2d.2 En_Karebaba (Soundfont 1, forest area bank) and the pickup.
    # ('path', segments): portamento/legato rendered on one sample run;
    # vibrato and DEKU_JR_DEAD's second layer (LAYER_4829) are not (logged).
    tick = 1 / 96
    font1 = fonts[1]

    def inst1(program):
        return font1.find('.//Instrument[@ProgramNumber="%d"]' % program).attrib['Sample']

    def check(label, *needles):
        block = seq.split(label + '\n', 1)[1].split('\n.channel', 1)[0]
        if not all(n in block for n in needles):
            raise ValueError('Deku Baba SFX changed: ' + label)
    check('.channel CHAN_3BBD', 'SF1_INST_21', 'PITCH_F4, 15, 100')
    entries.append(('baba_mouth', inst1(21), ('path', [(note('F4'), note('F4'), 15 * tick, 1.)]), 0, 'CHAN_3BBD'))
    check('.channel CHAN_3BD7', 'SF1_INST_3', 'portamento  0x85, PITCH_BF4', 'PITCH_GF5, 30', 'PITCH_GF4, 50')
    entries.append(('baba_dead', inst1(3), ('path', [(note('BF4'), note('GF5'), 30 * tick, 1.),
                                                    (note('GF5'), note('GF4'), 50 * tick, 1.)]), 0, 'CHAN_3BD7'))
    check('.channel CHAN_4CA7', 'SF1_INST_40', 'portamento  0x85, PITCH_E1', 'PITCH_DF1, 10', 'PITCH_DF2, 22')
    entries.append(('baba_awaken', inst1(40), ('path', [(note('E1'), note('DF1'), 10 * tick, 1.),
                                                       (note('DF1'), note('DF2'), 22 * tick, 1.)]), 0, 'CHAN_4CA7'))
    check('.channel CHAN_3648', 'SF1_INST_6', 'portamento  0x81, PITCH_A3', 'PITCH_D3, 30')
    entries.append(('baba_ground', inst1(6), ('path', [(note('A3'), note('D3'), 30 * tick, 1.)]), 0, 'CHAN_3648'))
    check('.channel CHAN_4929', 'SF1_INST_29', 'transpose   6', 'portamento  0x81, PITCH_A4', 'PITCH_BF5, 44')
    entries.append(('last_damage', inst1(29), ('path', [(note('A4') + 6, note('BF5') + 6, 44 * tick, 1.)]), 0, 'CHAN_4929'))
    get = seq.split('.layer LAYER_5BB4\n', 1)[1].split('\n.', 1)[0]
    get += seq.split('LAYER_5BAA:\n', 1)[1].split('end', 1)[0]
    notes = [(note(p), int(t) * tick, (int(v) / 127) ** 2) for p, t, v in
             re.findall(r'notedv\s+PITCH_(\w+),\s*(\d+),\s*(\d+)', get)]
    if len(notes) != 6:
        raise ValueError('NA_SE_SY_GET_ITEM changed')
    entries.append(('get_item', 'SAMPLE_0_0', ('triangle', notes), 0, 'CHAN_5B9C'))
    # M2e voices: Link's hurt (rand 3), knockdown fall (rand 2 -> take 0),
    # land damage (one take) through the shared CHAN_60F2 effect path.
    for name, label, effects in (('hurt', 'ARRAY_63C0', (37, 38, 39)),
                                 ('fall_l', 'ARRAY_6403', (43,)),
                                 ('land_hurt', 'ARRAY_64F9', (49,))):
        block = seq.split('.array ' + label, 1)[1].split('.array', 1)[0]
        for i, effect in enumerate(effects):
            if 'SF0_EFFECT_%d' % effect not in block:
                raise ValueError('Link voice array changed: ' + label)
            sample = font.find('.//Effect[@Name="EFFECT_%d"]' % effect).attrib['Sample']
            entries.append(('%s%d' % (name, i), sample, 60, .8, label))
    # NA_SE_VO_LI_DOWN_KID (CHAN_6424 -> LAYER_6428): transpose 1 over
    # PITCH_A0/BF0/B0 = EFFECT_1/2/3, 98/106/58 ticks (NTSC FRAMERATE_CONST).
    down = seq.split('.layer LAYER_6428\n', 1)[1].split('\n.', 1)[0]
    if not all(t in down for t in ('transpose   1', 'PITCH_A0, FRAMERATE_CONST(98',
                                   'PITCH_BF0, FRAMERATE_CONST(106', 'PITCH_B0, 58')):
        raise ValueError('Death voice layer changed')
    parts = []
    for effect, ticks in ((1, 98), (2, 106), (3, 58)):
        parts.append((font.find('.//Effect[@Name="EFFECT_%d"]' % effect).attrib['Sample'], ticks / 96))
    entries.append(('down', parts[0][0], ('effects', parts), 0, 'CHAN_6424'))
    # M2e system/body sounds from simple channels (render_channel); a channel
    # this cannot follow is left out and logged rather than guessed.
    simple = [('hp_recover', render_recovery(seq, RATE / 2), 'CHAN_596D')]
    simple.append(('tree_open',render_channel(seq,'CHAN_24A1',fonts,source,RATE/2),'CHAN_24A1'))
    for name, chan in DUNGEON_CHANNELS:
        simple.append((name,render_channel(seq,chan,fonts,source,RATE/2),chan))
    for name, chan in (('pl_damage', 'CHAN_076A'), ('body_hit', 'CHAN_0753'),
                       ('alarm', 'CHAN_5AA5'), ('heart_piece', 'CHAN_5B5B'),
                       ('decide', 'CHAN_58E9'), ('cursor', 'CHAN_5933')):
        try:
            simple.append((name, render_channel(seq, chan, fonts, source, RATE / 2), chan))
        except Unsupported as why:
            print('  skip  : %s (%s not followed)' % (name, why))
    bank, records, area_pcm = bytearray(), [], {}
    for name, sample, key, duration, label in entries:
        path = source / ('samples/SampleBank_0/Sample%03d.wav' % int(sample.rsplit('_',1)[1]))
        if not path.is_file():      # extracted as SampleNNN.half.wav (Soundfont 1 SFX)
            path = path.with_suffix('.half.wav')
        # Keep all four voices and their duration/pitch. Lower their stored
        # rate to make space for resident Navi without overlapping music RAM.
        # Bible rule (human, 2026-09-27): every SFX at half rate.
        sample_rate = RATE / 2
        if isinstance(key, tuple) and key[0] == 'triangle':
            pcm = render_triangle(key[1], sample_rate)
        elif isinstance(key, tuple) and key[0] == 'effects':
            pcm = b''
            for part_sample, seconds in key[1]:
                part_path = source / ('samples/SampleBank_0/Sample%03d.wav' % int(part_sample.rsplit('_', 1)[1]))
                if not part_path.is_file():
                    part_path = part_path.with_suffix('.half.wav')
                p_pcm, p_rate, p_unity = decode(part_path)
                part = render_path(p_pcm, p_rate, p_unity, [(p_unity, p_unity, seconds, 1.)], sample_rate)
                pcm += part + bytes(max(0, round(seconds * sample_rate) - len(part)))
        elif isinstance(key, tuple) and key[0] == 'path':
            pcm = render_path(*decode(path), key[1], sample_rate)
        elif name == 'navi_dash':
            pcm = fairy_audio.dash_sample(source, sys.modules[__name__])
        elif isinstance(key, tuple) and isinstance(key[0], tuple):
            source_pcm = decode(path)
            pcm = b''.join(bytes((round(((b - 256 if b > 127 else b)) * gain) & 255)
                                 for b in render(*source_pcm, k, seconds, output_rate=sample_rate))
                           + bytes(max(0, round(seconds * sample_rate) -
                                       len(render(*source_pcm, k, seconds, output_rate=sample_rate))))
                           for k, seconds, gain in key)
        elif isinstance(key, tuple):
            pcm = render_glide(*decode(path), key[0], key[1], duration, sample_rate)
        else:
            pcm = render(*decode(path), key, duration, output_rate=sample_rate)
        untrimmed_length = len(pcm)
        # PCM8 zero is exact digital silence. Keep every audible byte unchanged;
        # one-shot playback stops at LEA, with four zero guard bytes below.
        pcm = pcm.rstrip(b'\0') or bytes(1)
        if name in AREA_SOUNDS:
            area_pcm[name] = (pcm, dict(name=name, rate=sample_rate, source=label, sample=sample,
                                        trimmed_silence=untrimmed_length-len(pcm),
                                        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            continue
        records.append(dict(name=name, offset=len(bank), length=len(pcm), rate=sample_rate,
                            source=label, sample=sample, trimmed_silence=untrimmed_length-len(pcm), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        bank.extend(pcm)
        bank.extend(bytes(4 + (-len(bank) % 2)))
    for name, pcm, chan in simple:
        pcm = pcm.rstrip(b'\0') or bytes(1)
        if name in AREA_SOUNDS:
            area_pcm[name]=(pcm,dict(name=name,rate=RATE/2,source=chan,sample='channel render',trimmed_silence=0,sha256=hashlib.sha256(pcm).hexdigest()))
            continue
        records.append(dict(name=name, offset=len(bank), length=len(pcm), rate=RATE / 2,
                            source=chan, sample='channel render', trimmed_silence=0,
                            sha256=hashlib.sha256(pcm).hexdigest()))
        bank.extend(pcm)
        bank.extend(bytes(4 + (-len(bank) % 2)))
    wave, melody = rupee_melody(oot)
    records.append(dict(name='rupee_wave',offset=len(bank),length=len(wave),
                        source=melody['wave'],sample='source synthetic sawtooth',
                        sha256=melody['sha256']))
    bank.extend(wave)
    bank.extend(bytes(4 + (-len(bank) % 2)))
    area_base = BASE + len(bank)
    area_limit = 0x80000 - area_base
    area_banks = []
    for file_name, names in AREA_BANKS:
        blob, table = bytearray(), {}
        for name in names:
            pcm, record = area_pcm[name]
            table[name] = (len(blob), len(pcm))
            blob.extend(pcm)
            blob.extend(bytes(4 + (-len(blob) % 2)))
        if len(blob) > area_limit:
            raise ValueError('Area SFX bank %s exceeds sound RAM after core: %d > %d'
                             % (file_name, len(blob), area_limit))
        area_banks.append((file_name, bytes(blob), table))
    if BASE + len(bank) > 0x80000:
        raise ValueError('Action bank exceeds reserved sound RAM')
    out.mkdir(parents=True, exist_ok=True)
    (out/'ACTIONS.PCM').write_bytes(bank)
    for file_name, blob, _ in area_banks:
        if file_name:
            (out/file_name).write_bytes(blob)
    lines = ['/* Generated from local OoT samples; see action_audio.json. */',
             '#ifndef ACTION_AUDIO_DATA_H', '#define ACTION_AUDIO_DATA_H',
             '#define ACTION_PCM_BASE %d' % BASE, '#define ACTION_PCM_BYTES %d' % len(bank),
             '#define ACTION_PCM_COUNT %d' % len(records),
             'typedef struct { unsigned int offset; unsigned short length; } action_pcm_t;',
             'static const action_pcm_t action_pcm[] = {']
    lines += ['    {%d, %d},' % (r['offset'],r['length']) for r in records]
    lines += ['};']
    lines += ['#define ACTION_%s %d' % (r['name'].upper(), i) for i,r in enumerate(records)]
    # SCSP OCT for each sample's stored rate (44100 >> 2 = 11025 is 14).
    octave = lambda rate: 14 if rate == RATE else 13
    lines += ['static const unsigned char action_pcm_octave[ACTION_PCM_COUNT] = {%s};'
              % ','.join(str(octave(r.get('rate') or RATE)) for r in records)]
    lines += ['#define RUPEE_NOTE_COUNT 3', '#define RUPEE_TICKS_PER_SECOND 96',
              '#define RUPEE_BED_LEVEL %d' % melody['bed_level'],
              'static const unsigned short rupee_pitches[3] = {%s};' % ','.join(map(str,melody['pitches'])),
              'static const unsigned char rupee_ends[3] = {6,12,36};',
              'static const unsigned char rupee_levels[24] = {%s};' % ','.join(map(str,melody['levels']))]
    lines += ['', '/* Area SFX banks: loaded at SFX_AREA_BASE, after the core. */',
              '#define SFX_AREA_BASE %d' % area_base,
              '#define SFX_AREA_LIMIT %d' % area_limit,
              '#define SFX_BANK_COUNT %d' % len(area_banks),
              '#define AREA_SFX_COUNT %d' % len(AREA_SOUNDS)]
    lines += ['#define AREA_SFX_%s %d' % (n.upper(), i) for i, n in enumerate(AREA_SOUNDS)]
    lines += ['static const unsigned char area_sfx_octave[AREA_SFX_COUNT] = {%s};'
              % ','.join(str(14 if area_pcm[n][1]['rate'] == RATE else 13) for n in AREA_SOUNDS)]
    lines += ['static const char *const sfx_bank_file[SFX_BANK_COUNT] = {%s};'
              % ', '.join('"%s"' % f if f else '0' for f, _, _ in area_banks),
              'static const unsigned int sfx_bank_bytes[SFX_BANK_COUNT] = {%s};'
              % ', '.join(str(len(b)) for _, b, _ in area_banks),
              '/* length 0 = sound absent from that bank */',
              'static const action_pcm_t sfx_bank_pcm[SFX_BANK_COUNT][AREA_SFX_COUNT] = {']
    for _, _, table in area_banks:
        lines.append('    {%s},' % ', '.join('{%d, %d}' % table.get(n, (0, 0)) for n in AREA_SOUNDS))
    lines += ['};']
    lines += ['#endif']
    (out/'action_audio_data.h').write_text('\n'.join(lines)+'\n')
    area_json = [dict(file=f, bytes=len(b), samples=[dict(area_pcm[n][1], offset=o, length=l)
                                                     for n, (o, l) in t.items()])
                 for f, b, t in area_banks]
    (out/'action_audio.json').write_text(json.dumps(dict(base=BASE, bytes=len(bank), rate=RATE,
        limitations=__doc__, samples=records, rupee_melody=melody,
        area_base=area_base, area_limit=area_limit, area_banks=area_json), indent=2)+'\n')
    worst = max(len(b) for _, b, _ in area_banks)
    print('Action audio: core %d samples, %d bytes; area slot %d bytes, largest bank %d, '
          '%d sound RAM bytes spare' % (len(records), len(bank), area_limit, worst,
                                         area_limit - worst))
    for f, b, t in area_banks:
        print('  area bank %-12s %5d bytes  %s' % (f or '(none)', len(b), ' '.join(t) or '-'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    parser.add_argument('--source', type=Path, default=ROOT.parent/'shared/build/audio-source/extracted/assets/audio')
    parser.add_argument('--out', type=Path, default=ROOT/'build/generated')
    args = parser.parse_args()
    build(args.oot, args.source, args.out)
