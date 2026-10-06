"""List every US 1.2 SFX and sequence, and render a short host preview.

SFX come from the decomp bank tables (channel label + NA_SE name). Preview
walks that channel in seq_0 and plays the first samples or a simple tone.
Music uses the existing sequence baker for a few seconds. Offline only.
"""
import math
import re
import struct
import wave
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]

BANKS = (
    ('Player', 'playerbank_table.h', 0x800),
    ('Item', 'itembank_table.h', 0x1800),
    ('Environment', 'environmentbank_table.h', 0x2800),
    ('Enemy', 'enemybank_table.h', 0x3800),
    ('System', 'systembank_table.h', 0x4800),
    ('Ocarina', 'ocarinabank_table.h', 0x5800),
    ('Voice', 'voicebank_table.h', 0x6800),
)
TYPE_ORDER = {name: i for i, (name, _, _) in enumerate(BANKS)}
TYPE_ORDER['Music'] = len(BANKS)
PITCHES = ['C', 'DF', 'D', 'EF', 'E', 'F', 'GF', 'G', 'AF', 'A', 'BF', 'B']
RATE = 22050
PREVIEW_SECONDS = 1.6
MUSIC_SECONDS = 8
ROW = re.compile(
    r'DEFINE_SFX\(\s*(CHAN_[0-9A-Fa-f]+)\s*,\s*(NA_SE_[A-Z0-9_]+)')
SEQ_ROW = re.compile(
    r'DEFINE_SEQUENCE\s*\(\s*Sequence_(\d+)\s*,\s*(NA_BGM_[A-Z0-9_]+)')
OPCODE = re.compile(r'/\*.*?\*/\s*(\w+)\s*(.*)')
LABEL = re.compile(r'\.(?:channel|layer|sequence)\s+(\w+)|(\w+):')


def decomp_root():
    import sys
    sys.path.insert(0, str(ROOT / 'tools/launcher'))
    import project_config
    return Path(project_config.read_paths(ROOT)['oot_decomp'])


def audio_source():
    import sys
    sys.path.insert(0, str(ROOT / 'tools/music-workshop'))
    import music_assets
    source, error = music_assets.find_source(ROOT)
    if source is None:
        raise ValueError(error)
    return source


def pitch_name(name):
    match = re.fullmatch(r'(C|DF|D|EF|E|F|GF|G|AF|A|BF|B)(\d+)', name)
    if not match:
        raise ValueError(name)
    return 12 * (int(match[2]) + 1) + PITCHES.index(match[1])


def _arg(token):
    token = token.strip().split()[0].rstrip(')')
    if token.startswith('PITCH_'):
        return pitch_name(token[6:])
    match = re.fullmatch(r'SF(\d+)_(INST|EFFECT)_(\d+)', token)
    if match:
        return (match[2].lower(), int(match[1]), int(match[3]))
    if token.startswith('FONTANY_INSTR_'):
        return ('synth', token[14:])
    try:
        return int(token, 0)
    except ValueError:
        return token


def parse_seq(text):
    code, labels = [], {}
    for line in text.splitlines():
        line = line.strip()
        found = LABEL.match(line)
        if found:
            labels[found[1] or found[2]] = len(code)
        found = OPCODE.match(line)
        if not found:
            continue
        raw = found[2]
        args = [_arg(part) for part in raw.split(',')] if raw else []
        code.append((found[1], args))
    return code, labels


def sfx_catalog(oot):
    folder = Path(oot) / 'include/tables/sfx'
    rows = []
    for kind, filename, base in BANKS:
        text = (folder / filename).read_text(errors='replace')
        index = 0
        for match in ROW.finditer(text):
            rows.append(dict(
                kind=kind, name=match[2], channel=match[1],
                sfx_id=base + index, sequence=None))
            index += 1
    return rows


def music_catalog(oot):
    text = (Path(oot) / 'include/tables/sequence_table.h').read_text(errors='replace')
    rows = []
    for match in SEQ_ROW.finditer(text):
        number = int(match[1])
        if number == 0:
            continue
        rows.append(dict(
            kind='Music', name=match[2], channel='',
            sfx_id=None, sequence=number))
    return rows


def catalog(oot=None):
    oot = Path(oot) if oot else decomp_root()
    rows = sfx_catalog(oot) + music_catalog(oot)
    rows.sort(key=lambda row: (TYPE_ORDER[row['kind']], row['name']))
    return rows


def _walk(code, labels, start, notes, limit):
    """Follow one channel or layer. Parallel layers share t = 0."""
    pc = labels[start]
    inst = None
    transpose = 0
    time = 0.0
    stack = []
    seen = 0
    while seen < 800 and time < limit and 0 <= pc < len(code):
        seen += 1
        op, args = code[pc]
        pc += 1
        if op == 'instr' and args:
            inst = args[0]
        elif op == 'transpose' and args and isinstance(args[0], int):
            transpose += (args[0] + 128) % 256 - 128 if args[0] > 127 else args[0]
        elif op in ('notedv', 'notedvg') and args and isinstance(args[0], int):
            ticks = args[1] if len(args) > 1 and isinstance(args[1], int) else 12
            vel = args[2] if len(args) > 2 and isinstance(args[2], int) else 80
            if inst is not None and vel:
                notes.append((time, max(0.05, ticks / 96), args[0] + transpose, vel, inst))
            time += max(0, ticks) / 96
        elif op in ('delay', 'cdelay', 'ldelay') and args and isinstance(args[0], int):
            time += args[0] / 96
        elif op == 'delay1':
            time += 1 / 96
        elif op == 'ldlayer' and len(args) > 1 and args[1] in labels:
            _walk(code, labels, args[1], notes, limit)
        elif op == 'call' and args and args[0] in labels and len(stack) < 4:
            stack.append(pc)
            pc = labels[args[0]]
        elif op == 'end':
            if not stack:
                return
            pc = stack.pop()
        elif op in ('jump', 'rjump') and args and args[0] in labels:
            pc = labels[args[0]]
        elif op == 'rand':
            continue


def collect_notes(seq_text, channel, limit=PREVIEW_SECONDS):
    code, labels = parse_seq(seq_text)
    if channel not in labels:
        raise ValueError('missing channel ' + channel)
    notes = []
    _walk(code, labels, channel, notes, limit)
    return notes


def _wav_pcm(path):
    with wave.open(str(path)) as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError('need mono pcm16: ' + str(path))
        rate = wav.getframerate()
        pcm = struct.unpack('<%dh' % wav.getnframes(), wav.readframes(wav.getnframes()))
    unity = None
    raw = path.read_bytes()
    pos = 12
    while pos + 8 <= len(raw):
        kind, size = struct.unpack_from('<4sI', raw, pos)
        if kind == b'smpl':
            unity = struct.unpack_from('<I', raw, pos + 20)[0]
            break
        pos += 8 + size + (size & 1)
    if unity is None:
        unity = 60
    return pcm, rate, unity


class SampleCache:
    def __init__(self, source):
        self.source = Path(source)
        self.fonts = {}
        self.pcm = {}

    def font(self, number):
        if number not in self.fonts:
            path = self.source / ('soundfonts/Soundfont_%d.xml' % number)
            self.fonts[number] = ET.parse(path).getroot()
        return self.fonts[number]

    def sample_name(self, inst):
        kind, font, number = inst
        root = self.font(font)
        if kind == 'inst':
            node = root.find('.//Instrument[@ProgramNumber="%d"]' % number)
        else:
            node = root.find('.//Effect[@Name="EFFECT_%d"]' % number)
        if node is None:
            raise ValueError('no %s %s %d in soundfont %d' % (kind, kind, number, font))
        for key in ('Sample', 'SampleLo', 'SampleHi'):
            if node.attrib.get(key):
                return node.attrib[key]
        raise ValueError('instrument has no sample')

    def load(self, name):
        if name in self.pcm:
            return self.pcm[name]
        match = re.fullmatch(r'SAMPLE_(\d+)_(\d+)', name)
        if not match:
            raise ValueError('bad sample name ' + name)
        path = self.source / ('samples/SampleBank_%s/Sample%03d.wav'
                              % (match[1], int(match[2])))
        if not path.is_file():
            path = path.with_suffix('.half.wav')
        self.pcm[name] = _wav_pcm(path)
        return self.pcm[name]


def _tone(kind, key, count):
    freq = 440 * 2 ** ((key - 69) / 12)
    out = []
    for i in range(count):
        t = i / RATE
        phase = (freq * t) % 1
        if kind in ('SQUARE', '4PULSE'):
            sample = 0.35 if phase < 0.5 else -0.35
        elif kind == '8PULSE':
            sample = 0.35 if phase < 0.125 else -0.35
        elif kind == 'SAWTOOTH':
            sample = 0.35 * (2 * phase - 1)
        elif kind == 'NOISE':
            sample = 0.25 * (((i * 1103515245 + 12345) & 65535) / 32768 - 1)
        else:
            sample = 0.4 * math.sin(2 * math.pi * freq * t)
        if kind == 'BELL':
            sample *= math.exp(-4 * t)
        out.append(sample)
    return out


def _place(mix, start, samples, velocity):
    begin = int(start * RATE)
    gain = (max(1, min(127, velocity)) / 127) ** 2
    for i, sample in enumerate(samples):
        at = begin + i
        if at >= len(mix):
            break
        mix[at] += sample * gain


def _resample(pcm, source_rate, unity, key, seconds):
    count = min(int(seconds * RATE), int(PREVIEW_SECONDS * RATE))
    step = source_rate * 2 ** ((key - unity) / 12) / RATE
    out = []
    pos = 0.0
    for _ in range(count):
        index = int(pos)
        if index + 1 >= len(pcm):
            break
        frac = pos - index
        out.append((pcm[index] + (pcm[index + 1] - pcm[index]) * frac) / 32768)
        pos += step
    return out


def render_sfx(channel, source, seq_text, cache=None):
    notes = collect_notes(seq_text, channel)
    if not notes:
        raise ValueError('no notes in ' + channel)
    cache = cache or SampleCache(source)
    mix = [0.0] * int(PREVIEW_SECONDS * RATE)
    used = 0
    for start, seconds, key, velocity, inst in notes:
        if isinstance(inst, tuple) and inst[0] == 'synth':
            audio = _tone(inst[1], key, int(min(seconds, PREVIEW_SECONDS) * RATE))
        elif isinstance(inst, tuple):
            pcm, rate, unity = cache.load(cache.sample_name(inst))
            audio = _resample(pcm, rate, unity, key, seconds)
        else:
            continue
        _place(mix, start, audio, velocity)
        used += 1
    if not used:
        raise ValueError('nothing playable in ' + channel)
    peak = max(1e-6, max(abs(s) for s in mix))
    pcm = [max(-32767, min(32767, int(s / peak * 28000))) for s in mix]
    buf = BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(struct.pack('<%dh' % len(pcm), *pcm))
    return buf.getvalue()


def render_music(sequence, source, seconds=MUSIC_SECONDS):
    import sys
    import tempfile
    sys.path.insert(0, str(ROOT / 'tools/music-workshop'))
    import music_assets
    import build_title_audio as audio
    built = music_assets.render(source, sequence, stop_at_loop=True)
    path = Path(tempfile.gettempdir()) / 'dosei-audio-music-preview.wav'
    audio.preview(path, seconds, built['frames'], built['levels'],
                  built['cooked'], built['samples'])
    return path.read_bytes()
