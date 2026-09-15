#!/usr/bin/env python3
"""
Converts the OoT instrument samples the title theme needs into a form the
Saturn's SCSP can play directly, via the Ponesound driver.

Source: the ntsc-1.1 extraction's per-sample WAVs, which (unlike the
BANK_xx_INSTR_yyyy dump) are named after the sample IDs the soundfont
actually references and carry the metadata we need in standard chunks:
  - `smpl` chunk -> MIDI unity note + loop start/end (loop count is always
    0xFFFFFFFF here, i.e. sustain forever)
  - all are mono, 32000 Hz, signed 16-bit

The title theme is Sequence 30, which uses Soundfont 6 alone: five
instruments (programs 1, 10, 11, 13, 14) over seven distinct samples, with
10/11 and 13/14 sharing sample sets. Instruments 10, 11, 13 and 14 are split
across low/normal/high sample variants by note range.

Two Saturn-side constraints drive the output format:
  - Sound RAM is 512KB total and the driver reserves the first 47KB, but all
    seven samples at 16-bit come to ~569KB. Dropping to signed 8-bit (what
    SCSP wants for PCM_TYPE_8BIT) roughly halves that.
  - Ponesound's per-voice `playsize` and `LSA` (loop start) are both u16, so
    no sample may exceed 65535 frames.

Source rates are NOT uniform (32000, 22050 and 16000 all appear), so each
sample keeps its own native rate and the table carries it per entry;
resampling everything to one rate would upsample the 16kHz sources for no
quality gain and waste RAM. Only samples that break the u16 frame limit get
downsampled, and only by as much as that requires.

Every sample also gets trimmed to its loop end, since all loops here sustain
forever and nothing past the loop end is reachable.
"""
import struct
import sys
import wave
from pathlib import Path

SAMPLE_DIR = Path(r"D:\Workspace-Claude\game-decomps\n64\oot\extracted\ntsc-1.1"
                  r"\assets\audio\samples\SampleBank_0")

OUT_DIR = Path(__file__).resolve().parent.parent / "assets"
BLOB_OUT = OUT_DIR / "TITLE_SMP.RAW"
HEADER_OUT = OUT_DIR.parent / "title_samples.h"

# Ponesound's playsize/LSA fields are u16.
MAX_FRAMES = 0xFFFF

# Sample IDs referenced by Soundfont_6.xml, in the order we emit them.
SAMPLE_IDS = [115, 372, 373, 374, 356, 357, 358]

# From Soundfont_6.xml. (program, sample_lo, sample_norm, sample_hi,
# range_lo_name, range_hi_name, decay). range_lo/hi bound the *normal*
# sample's compass: notes below range_lo use sample_lo, above range_hi use
# sample_hi.
#
# `decay` collapses the soundfont's 3-point envelope down to the one thing
# that actually matters for balance here: whether the instrument sustains or
# fades. Env0 (INST_1) and Env1 (INST_10/11) hold at 29430/32700, so they
# sustain for the note's whole gate - decay 0. Env2 (INST_13) and Env3
# (INST_14) fall to 0 over 229 and 298 units respectively, i.e. struck
# sounds that must fade out; without this they sit at full level for the
# entire note and drown everything else, since both channels also run at
# vol 127. Units are envelope ticks, treated as 60Hz frames by the player.
INSTRUMENTS = [
    (1,  115, 115, 115, None,  None,   0),
    (10, 372, 373, 374, "EF3", "DF4",  0),
    (11, 372, 373, 374, "EF3", "DF4",  0),
    (13, 356, 357, 358, "A2",  "F4",  229),
    (14, 356, 357, 358, "G2",  "F4",  298),
]

# Indexed by z64 note number; pitch_names[39] == "C4". Mirrors
# tools/audio/extraction/tuning.py in the decomp.
PITCH_NAMES = (
    ["A0", "BF0", "B0"]
    + [f"{n}{o}" for o in range(1, 10)
       for n in ("C", "DF", "D", "EF", "E", "F", "GF", "G", "AF", "A", "BF", "B")]
    + ["C10", "DF10", "D10", "EF10", "E10", "F10"]
)


def note_name_to_midi(name):
    """z64 pitch name -> MIDI note number (z64 note 39 = C4 = MIDI 60)."""
    return (21 + PITCH_NAMES.index(name)) % 128


def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getnchannels() == 1, path
        assert w.getsampwidth() == 2, path
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    pcm = list(struct.unpack(f"<{len(frames) // 2}h", frames))
    return pcm, rate


def read_smpl_chunk(path):
    """Pull the MIDI unity note and loop points out of the WAV's `smpl` chunk."""
    data = path.read_bytes()
    assert data[:4] == b"RIFF", path

    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"smpl":
            body = data[pos + 8:pos + 8 + size]
            unity = struct.unpack("<I", body[12:16])[0]
            nloops = struct.unpack("<I", body[28:32])[0]
            if nloops:
                start, end = struct.unpack("<2I", body[36 + 8:36 + 16])
                return unity, start, end
            return unity, None, None
        pos += 8 + size + (size & 1)

    raise SystemExit(f"no smpl chunk in {path}")


def resample(pcm, src_rate, dst_rate):
    """Linear interpolation; good enough for 32k -> 22.05k on these sources."""
    if src_rate == dst_rate:
        return list(pcm)

    ratio = src_rate / dst_rate
    out_len = int(len(pcm) / ratio)
    out = []
    for i in range(out_len):
        src_pos = i * ratio
        idx = int(src_pos)
        frac = src_pos - idx
        a = pcm[idx]
        b = pcm[idx + 1] if idx + 1 < len(pcm) else a
        out.append(int(a + (b - a) * frac))
    return out


def to_signed8(pcm):
    out = bytearray(len(pcm))
    for i, s in enumerate(pcm):
        v = (s + 128) >> 8          # round-to-nearest on the way to 8-bit
        v = max(-128, min(127, v))
        out[i] = v & 0xFF
    return out


def main():
    if not SAMPLE_DIR.is_dir():
        sys.exit(f"sample directory not found: {SAMPLE_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    blob = bytearray()
    entries = {}

    for sid in SAMPLE_IDS:
        path = SAMPLE_DIR / f"Sample{sid}.wav"
        if not path.is_file():
            sys.exit(f"missing sample: {path}")

        pcm, rate = read_wav(path)
        unity, loop_start, loop_end = read_smpl_chunk(path)

        # Trim to the end of the loop: nothing past it is ever reachable,
        # since every loop here sustains forever.
        if loop_end is not None and loop_end < len(pcm):
            pcm = pcm[:loop_end]

        # Keep the native rate unless doing so breaks the u16 frame limit,
        # in which case drop just far enough to fit (with a little slack so
        # rounding can't push us back over).
        out_rate = rate
        if len(pcm) > MAX_FRAMES:
            out_rate = int(rate * (MAX_FRAMES - 64) / len(pcm))

        resampled = resample(pcm, rate, out_rate)
        scaled_loop = (int(loop_start * out_rate / rate)
                       if loop_start is not None else 0)

        assert len(resampled) <= MAX_FRAMES, (sid, len(resampled))

        peak = max(abs(s) for s in resampled) if resampled else 0
        data = to_signed8(resampled)

        # SCSP reads sample data on even addresses.
        if len(blob) & 1:
            blob.append(0)

        entries[sid] = {
            "offset": len(blob),
            "length": len(data),
            "loop_start": scaled_loop,
            "base_note": unity,
            "base_rate": out_rate,
        }
        blob.extend(data)

        note = "" if out_rate == rate else f"  (downsampled from {rate})"
        print(f"Sample{sid:<4d} {len(pcm):6d} -> {len(data):6d} frames  "
              f"{out_rate:5d}Hz  loop@{scaled_loop:<6d} note={unity:3d}  "
              f"peak={peak / 32768:.2f}{note}")

    BLOB_OUT.write_bytes(blob)

    sample_index = {sid: i for i, sid in enumerate(SAMPLE_IDS)}

    with open(HEADER_OUT, "w") as f:
        f.write("/* Generated by tools/make_title_samples.py - do not hand-edit. */\n")
        f.write("#ifndef TITLE_SAMPLES_H\n#define TITLE_SAMPLES_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write(f"#define TITLE_SAMPLE_COUNT {len(SAMPLE_IDS)}\n")
        f.write(f"#define TITLE_INSTRUMENT_COUNT {len(INSTRUMENTS)}\n\n")

        f.write("/* To sound MIDI note n from a sample, play it at\n"
                " *   base_rate * 2^((n - base_note) / 12)\n"
                " * which the player turns into an SCSP OCT/FNS pitch word. */\n")
        f.write("typedef struct {\n"
                "        uint32_t offset;     /* byte offset into asset_title_samples */\n"
                "        uint16_t length;     /* frames; 1 byte per frame at 8-bit */\n"
                "        uint16_t loop_start; /* frame index; every sample loops forever */\n"
                "        uint16_t base_rate;  /* Hz the sample data is stored at */\n"
                "        uint8_t  base_note;  /* MIDI note produced at base_rate */\n"
                "} title_sample_t;\n\n")

        f.write("typedef struct {\n"
                "        uint8_t  program;\n"
                "        uint8_t  sample_lo;\n"
                "        uint8_t  sample_norm;\n"
                "        uint8_t  sample_hi;\n"
                "        uint8_t  range_lo;   /* notes below this use sample_lo */\n"
                "        uint8_t  range_hi;   /* notes above this use sample_hi */\n"
                "        uint16_t decay;      /* frames to fade to silence; 0 = sustains */\n"
                "} title_instrument_t;\n\n")

        f.write("static const title_sample_t title_samples[TITLE_SAMPLE_COUNT] = {\n")
        for sid in SAMPLE_IDS:
            e = entries[sid]
            f.write(f"        {{ {e['offset']:6d}, {e['length']:5d}, "
                    f"{e['loop_start']:5d}, {e['base_rate']:5d}, "
                    f"{e['base_note']:3d} }}, /* Sample{sid} */\n")
        f.write("};\n\n")

        f.write("static const title_instrument_t title_instruments[TITLE_INSTRUMENT_COUNT] = {\n")
        for program, lo, norm, hi, rlo, rhi, decay in INSTRUMENTS:
            range_lo = note_name_to_midi(rlo) if rlo else 0
            range_hi = note_name_to_midi(rhi) if rhi else 127
            f.write(f"        {{ {program:3d}, {sample_index[lo]}, "
                    f"{sample_index[norm]}, {sample_index[hi]}, "
                    f"{range_lo:3d}, {range_hi:3d}, {decay:4d} }},\n")
        f.write("};\n\n#endif /* !TITLE_SAMPLES_H */\n")

    print(f"\nwrote {BLOB_OUT} ({len(blob)} bytes, "
          f"{len(blob) / 1024:.1f} KB of 512KB sound RAM)")
    print(f"wrote {HEADER_OUT}")


if __name__ == "__main__":
    main()
