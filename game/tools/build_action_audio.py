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
BASE = 0x76400  # above largest music bank end (484178), aligned to 1 KiB
RATE = 11025
# seq_0.prg.seq layer, instrument, note, bounded one-shot seconds.
EFFECTS = (
    ('swing', 'LAYER_0F91', 27, 'D2', .45),
    ('shield', 'LAYER_11EF', 28, 'F3', .45),
    ('cut', 'LAYER_222C', 47, 'G3', .30),
    ('equip', 'CHAN_0FA5', 29, 'A3', .40),
    ('message', 'LAYER_5A68', 84, 'G4', .18),
    ('footstep', 'LAYER_0333', 5, 'A3', .10),
    ('roll', 'CHAN_0731', 27, 'D2', .18),
    ('rupee', 'LAYER_587A', 91, 'C5', .30),  # NA_SE_SY_GET_RUPY sample layer
    ('navi_dash', 'CHAN_1B01', 69, 'B5', .65),  # NA_SE_EV_FAIRY_DASH
)

# Per-area SFX banks (demo plan M0). Core = ACTIONS.PCM, resident in every
# gameplay scene (Link, UI, Navi, rupee). Area sounds live in one swappable
# bank loaded right after the core on scene load; bank 0 is "no area sounds".
# A sound may appear in several banks. Scenes pick a bank by `sfx` in
# build_scene_table.SCENES. OPENING.PCM still replaces the whole region.
AREA_SOUNDS = ('cut',)
AREA_BANKS = (
    (None, ()),                     # 0: interiors, nothing area-specific
    ('SFXFRST.PCM', ('cut',)),      # 1: outdoor forest (grass cutting)
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
    entries = []
    for name, layer, inst, pitch, duration in EFFECTS:
        prefix = '.channel ' if layer.startswith('CHAN_') else '.layer '
        block = seq.split(prefix+layer+'\n', 1)[1].split('\n.channel', 1)[0]
        if prefix == '.layer ': block = block.split('\n.layer', 1)[0]
        if 'SF0_INST_%d' % inst not in block or 'PITCH_'+pitch not in block:
            raise ValueError('OoT SFX layer changed: '+layer)
        sample = font.find('.//Instrument[@ProgramNumber="%d"]' % inst).attrib['Sample']
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
    # Only EFFECT_35 fits the sound RAM left above the area bank (the second
    # take is logged in BUG_FEATURE_LOG).
    climb_array = seq.split('.array ARRAY_63AB', 1)[1].split('.array', 1)[0]
    for i, effect in enumerate((35,)):
        if 'SF0_EFFECT_%d' % effect not in climb_array:
            raise ValueError('Child climb-end voice array changed')
        sample = font.find('.//Effect[@Name="EFFECT_%d"]' % effect).attrib['Sample']
        entries.append(('climb%d' % i, sample, 60, .6, 'ARRAY_63AB'))
    bank, records, area_pcm = bytearray(), [], {}
    for name, sample, key, duration, label in entries:
        path = source / ('samples/SampleBank_0/Sample%03d.wav' % int(sample.rsplit('_',1)[1]))
        # Keep all four voices and their duration/pitch. Lower their stored
        # rate to make space for resident Navi without overlapping music RAM.
        sample_rate = (RATE / 2 if name.startswith(('voice', 'climb')) or name == 'navi_dash'
                       else RATE)
        pcm = (fairy_audio.dash_sample(source, sys.modules[__name__]) if name == 'navi_dash'
               else render(*decode(path), key, duration, output_rate=sample_rate))
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
    parser.add_argument('--oot', type=Path, default=Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    parser.add_argument('--source', type=Path, default=ROOT.parent/'shared/build/audio-source/extracted/assets/audio')
    parser.add_argument('--out', type=Path, default=ROOT/'build/generated')
    args = parser.parse_args()
    build(args.oot, args.source, args.out)
