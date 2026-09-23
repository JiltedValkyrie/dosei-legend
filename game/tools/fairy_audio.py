"""OoT NAVY_FLY: retain the instrument's sustain loop, not a short dash chirp."""
import math
import struct
import xml.etree.ElementTree as ET


def dash_sample(source, audio):
    """CHAN_1B01: sustain the sample through the note and original pitch bend.

    The old renderer stopped at the raw sample end (~0.11 s at B5), losing
    both its loop and DF5->B5 portamento. The note lasts 72/96 seconds.
    """
    path = next((source / 'samples/SampleBank_0').glob('Sample092*.wav'))
    pcm, rate, unity = audio.decode(path)
    raw = path.read_bytes(); pos = 12
    while raw[pos:pos+4] != b'smpl':
        size = struct.unpack_from('<I', raw, pos+4)[0]
        pos += 8 + size + (size & 1)
    values = struct.unpack_from('<15I', raw, pos+8)
    start, end = values[11], values[12]+1
    output_rate = 5512.5
    output = bytearray(); x = 0.
    for i in range(round(output_rate * .75)):
        time = i / output_rate
        bend = min(1., time * 180 * (131072 // (256 * 3)) / (127 * 256))
        pitch = 2 ** ((audio.note('DF5') - unity) / 12) * (1 + (2 ** (10/12)-1) * (2 ** bend-1))
        playback = rate * pitch
        cutoff = min(1., output_rate / playback) * .95
        value = weight = 0.
        for j in range(int(x)-15, int(x)+17):
            d = x-j
            if abs(d) >= 16: continue
            z = math.pi * cutoff * d
            w = (math.sin(z)/z if z else 1.) * (.5+.5*math.cos(math.pi*d/16))
            index = start+(j-start) % (end-start) if j >= end else j
            value += (pcm[index] if index >= 0 else 0)*w
            weight += w
        tick = time * 180
        envelope = min(1., tick/35) if tick < 75 else max(0., 1-(tick-75)/105)
        envelope *= min(1., (round(output_rate*.75)-1-i)/64)
        # OoT applies squared note velocity, not full-scale sample gain.
        output.append(max(-127, min(127, round(value/weight * envelope * (65/127)**2 * .95 / 256))) & 255)
        x += playback/output_rate
    return bytes(output)


def flight_sample(oot, source, audio):
    seq = (oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
    block = seq.split('.channel CHAN_2582\n')[1].split('.channel')[0]
    for token in ('SF0_INST_69', 'ENVELOPE_67D8', 'legato', 'PITCH_A4', 'PITCH_D5', 'rjump'):
        if token not in block:
            raise ValueError('Review original NAVY_FLY sequence: ' + token)
    font = ET.parse(source / 'soundfonts/Soundfont_0.xml')
    sample = font.find('.//Instrument[@ProgramNumber="69"]').attrib['Sample']
    path = next((source / 'samples/SampleBank_0').glob('Sample%03d*.wav' % int(sample.rsplit('_', 1)[1])))
    pcm, rate, unity = audio.decode(path)
    raw = path.read_bytes()
    pos = 12
    while pos + 8 <= len(raw):
        size = struct.unpack_from('<I', raw, pos + 4)[0]
        if raw[pos:pos+4] == b'smpl':
            values = struct.unpack_from('<15I', raw, pos + 8)
            start, end = values[11], values[12] + 1  # WAV loop end is inclusive
            break
        pos += 8 + size + (size & 1)
    else:
        raise ValueError('Fairy sample needs original sustain loop')
    playback = rate * 2 ** ((audio.note('A4') - unity) / 12)
    output_rate = 11025
    ratio = output_rate / playback
    loop_start = round(start * ratio)
    loop_end = round(end * ratio)
    cutoff = min(1., ratio) * .95
    output = bytearray()
    for i in range(loop_end):
        x = i / ratio
        value = weight = 0.
        for j in range(int(x)-15, int(x)+17):
            d = x-j
            if abs(d) >= 16:
                continue
            z = math.pi * cutoff * d
            w = (math.sin(z)/z if z else 1.) * (.5 + .5*math.cos(math.pi*d/16))
            index = start + (j-start) % (end-start) if j >= end else j
            value += (pcm[index] if index >= 0 else 0) * w
            weight += w
        output.append(max(-127, min(127, round(value / weight * .95 / 256))) & 255)
    return bytes(output), loop_start


def tables(loop_start):
    # Source mode 0x81 bends A4 -> D5 over each repeated 32-tick note.
    extent = 2 ** (5 / 12) - 1
    pitch = [round(16384 * (1 + extent * (2 ** (i / 127) - 1))) for i in range(128)]
    level = [255] + [min(255, round(-20 * math.log10(i / 127) / .375)) for i in range(1, 128)]
    return ['#define NAVI_FLY_LOOP_START %d' % loop_start,
            'static const unsigned short navi_fly_pitch[128] = {' + ','.join(map(str, pitch)) + '};',
            'static const unsigned char navi_fly_level[128] = {' + ','.join(map(str, level)) + '};']
