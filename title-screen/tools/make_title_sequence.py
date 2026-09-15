#!/usr/bin/env python3
"""
Converts OoT's title theme sequence (Sequence_30 / NA_BGM_TITLE, seq id 30
decimal) into a flat, time-stamped note-event list for a simple SH2 player
driving Ponesound voices.

Source: the zeldaret/oot decomp's own disassembly of the sequence,
`extracted/ntsc-1.1/assets/audio/sequences/seq_30.seq` - a text format with
one instruction per line (`/* addr [bytes] */ mnemonic args`), grouped under
`.sequence`/`.channel`/`.layer` section headers, with mid-section `LABEL:`
markers for jump targets. This script is a small byte-code interpreter over
that text, not over the original binary - the text already carries correct
section boundaries and symbolic names (PITCH_*, SF6_INST_*), which is far
less error-prone to re-derive from raw opcodes.

## Why we treat the whole sequence as one repeating unit

The sequence has exactly one piece of control flow: a `jump SEQ_0027` near
the end. In the real engine, everything before SEQ_0027 (a ~0.6s pad/intro -
most of those channels DO call `ldlayer`, it isn't silent) plays exactly
once, and only SEQ_0027..jump repeats forever after. Modelling "play an
intro once, then loop a different region" needs a stateful player; instead
this script just treats [start of SEQ_0000 .. the jump] as ONE repeating
unit and lets the intro replay every lap along with the rest. At a ~67s loop
length, replaying a 0.6s pad once every lap is not something a listener
would notice, and it avoids a second code path on the Saturn for a one-shot
lead-in.

## The three-level virtual machine

SEQ level: owns the tempo map and dispatches `ldchan` to spawn channel
interpretation. CHAN level: sets per-channel instrument/pan/reverb (mostly
static here) and dispatches `ldlayer` to spawn layer interpretation, on the
channel's own local tick clock. LAYER level: where actual notes live,
again on its own local tick clock. `call`/`end` at CHAN and LAYER level are
real subroutine calls (a handful of short repeated riffs, e.g. CHAN_1071 is
a volume-swell figure called from multiple places) - handled with an
explicit return-address stack rather than by inlining, since two of them
recurse into shared sub-layers too (LAYER_10B3 etc).

All of this only has to be "close enough" for a decorative title-screen
loop: channel-level vibrato/filter/mute automation is read but ignored, and
`gate` is treated as a plain tick count for how long a note sounds (some
notes have gate > delay, which just means a legato overlap into the next
note's slot - left as-is rather than clamped, since Ponesound voices don't
fight over sounding simultaneously).

## Tempo and timing

z64 tempo is BPM against 48 ticks per quarter note, and seq 30 changes tempo
17 times across the loop for rubato. Rather than ship a tempo map to the
Saturn and integrate on-device, this script converts every event's tick
position to a 60Hz frame number up front (Saturn video is NTSC 60fps, and
the player advances one step per vblank), which keeps the SH2 player a
simple "does anything start this frame" scan.
"""
import re
import struct
import sys
from pathlib import Path

OOT_ROOT = Path(r"D:\Workspace-Claude\game-decomps\n64\oot")
SEQ_FILE = OOT_ROOT / "extracted/ntsc-1.1/assets/audio/sequences/seq_30.seq"
ASEQ_H = OOT_ROOT / "include/audio/aseq.h"

OUT_DIR = Path(__file__).resolve().parent.parent / "assets"
HEADER_OUT = OUT_DIR.parent / "title_sequence.h"
SAMPLES_HEADER = OUT_DIR.parent / "title_samples.h"

TICKS_PER_QUARTER = 48
FRAME_RATE = 60
LOOP_START_LABEL = "SEQ_0027"

# --------------------------------------------------------------------------
# Parsing: text disassembly -> {label: (kind, [(mnemonic, [args]), ...])}
# plus a label -> (section_label, instr_index) resolver for jump/call/branch
# targets, including mid-section `LABEL:` markers.
# --------------------------------------------------------------------------

LINE_RE = re.compile(
    r"^/\*\s*0x[0-9A-F]+\s*\[[^\]]*\]\s*\*/\s*(\w+)\s*(.*)$")
LOCAL_LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):$")
SECTION_RE = re.compile(r"^\.(sequence|channel|layer|filter)\s+(\S+)")


def load_pitch_table():
    table = {}
    pat = re.compile(r"#define\s+(PITCH_\w+)\s+(\d+)")
    for line in ASEQ_H.read_text().splitlines():
        m = pat.match(line.strip())
        if m:
            table[m.group(1)] = int(m.group(2))
    assert len(table) == 128, len(table)
    return table


PITCH = load_pitch_table()


def parse_arg(tok):
    tok = tok.strip()
    if tok.startswith("PITCH_"):
        # PITCH_ names resolve to z64 note numbers (aseq.h), but base_note
        # (from each WAV's smpl chunk) and range_lo/range_hi (via
        # note_name_to_midi below) are MIDI. Converting here means every
        # downstream consumer of a note value is uniformly in MIDI space -
        # z64 note numbers never leak out of this function.
        z64 = PITCH[tok]
        return (21 + z64) % 128
    if tok.startswith("SF6_INST_"):
        return int(tok.removeprefix("SF6_INST_"))
    if tok.startswith("0x") or tok.startswith("0X"):
        return int(tok, 16)
    if tok.startswith("0b") or tok.startswith("0B"):
        return int(tok, 2)
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    # Anything else (e.g. a bare label used as an arg) is returned as-is;
    # only jump/call/ldchan/ldlayer arg slots that need resolving hold these.
    return tok


def parse_sequence_file():
    sections = {}          # label -> {'kind': str, 'instrs': [(mnemonic, [args])]}
    resolve = {}            # any label -> (section_label, instr_index)

    current_label = None
    current_kind = None

    for raw_line in SEQ_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#include") or line.startswith(".startseq") \
                or line.startswith(".endseq"):
            continue

        m = SECTION_RE.match(line)
        if m:
            kind, label = m.group(1), m.group(2)
            if kind == "filter":
                current_label = None  # not interpreted; skip its body
                continue
            current_label = label
            current_kind = kind
            sections[label] = {"kind": kind, "instrs": []}
            resolve[label] = (label, 0)
            continue

        if current_label is None:
            continue  # inside a .filter block or before the first section

        m = LOCAL_LABEL_RE.match(line)
        if m:
            resolve[m.group(1)] = (current_label, len(sections[current_label]["instrs"]))
            continue

        m = LINE_RE.match(line)
        if not m:
            continue
        mnemonic, argstr = m.group(1), m.group(2).strip()
        args = [parse_arg(a) for a in argstr.split(",")] if argstr else []
        sections[current_label]["instrs"].append((mnemonic, args))

    return sections, resolve


# --------------------------------------------------------------------------
# Interpreter
# --------------------------------------------------------------------------

def sounding_ticks(delay, gate):
    """How long a note actually sounds, per AudioSeq_SeqLayerProcessScript.

    `gate` is NOT a duration - it's the trailing release portion expressed in
    1/256ths of `delay`:

        layer->gateDelay = (layer->gateTime * delay) >> 8;
        ...
        if (layer->delay <= layer->gateDelay) { Audio_SeqLayerNoteDecay(...) }

    `layer->delay` counts down from `delay`, and the note is released once
    the remainder falls to gateDelay. So the sounding portion is everything
    before that. gate=255 is near-staccato; gate=0 holds the full delay.
    """
    return delay - ((gate * delay) >> 8)


class NoteEvent:
    __slots__ = ("tick", "program", "note", "velocity", "sound_ticks", "pan",
                 "chan_vol")

    def __init__(self, tick, program, note, velocity, sound_ticks, pan, chan_vol):
        self.tick = tick
        self.program = program
        self.note = note
        self.velocity = velocity
        self.sound_ticks = sound_ticks
        self.pan = pan
        # Channel volume sampled at note-on. The sequence automates this
        # heavily (continuous swells via `vol` + `cdelay`, plus the shared
        # CHAN_1071 swell subroutine), and it is the main thing balancing
        # the parts against each other - note velocity alone is not enough.
        self.chan_vol = chan_vol


def timeline_lookup(timeline, tick):
    """timeline: [(tick, value), ...] ascending. -> value in effect at tick."""
    value = timeline[0][1]
    for t, v in timeline:
        if t <= tick:
            value = v
        else:
            break
    return value


def run_layer(sections, resolve, label, base_tick, program, pan, notes, vol_timeline):
    """Interpret a LAYER section (and any called sub-layers) starting at
    base_tick (already an absolute SEQ_0027-relative tick), appending
    NoteEvents. Returns nothing meaningful - layers don't return a value the
    caller needs."""

    # (section_label, instr_index) call stack for `call`/`end`.
    stack = []
    sec, idx = label, 0
    local_tick = 0
    cur_delay = 0

    while True:
        instrs = sections[sec]["instrs"]
        if idx >= len(instrs):
            if stack:
                sec, idx = stack.pop()
                continue
            return

        mnemonic, args = instrs[idx]
        idx += 1

        if mnemonic == "ldelay":
            local_tick += args[0]
        elif mnemonic == "notedvg":
            pitch, delay, vel, gate = args
            tick = base_tick + local_tick
            notes.append(NoteEvent(tick, program, pitch, vel,
                                   sounding_ticks(delay, gate), pan,
                                   timeline_lookup(vol_timeline, tick)))
            cur_delay = delay   # lastDelay, for a following notevg
            local_tick += delay
        elif mnemonic == "notedv":
            # NOTEDV explicitly zeroes gateTime rather than carrying the
            # previous note's, so it always sounds for its full delay.
            pitch, delay, vel = args
            tick = base_tick + local_tick
            notes.append(NoteEvent(tick, program, pitch, vel,
                                   sounding_ticks(delay, 0), pan,
                                   timeline_lookup(vol_timeline, tick)))
            cur_delay = delay
            local_tick += delay
        elif mnemonic == "notevg":
            # NOTEVG reuses lastDelay and does not update it.
            pitch, vel, gate = args
            tick = base_tick + local_tick
            notes.append(NoteEvent(tick, program, pitch, vel,
                                   sounding_ticks(cur_delay, gate), pan,
                                   timeline_lookup(vol_timeline, tick)))
            local_tick += cur_delay
        elif mnemonic == "call":
            target = args[0]
            stack.append((sec, idx))
            sec, idx = resolve[target]
        elif mnemonic == "end":
            if stack:
                sec, idx = stack.pop()
            else:
                return
        elif mnemonic == "jump":
            sec, idx = resolve[args[0]]
        # transpose/legato/nolegato/env/stereo/bendfine/instr/etc: expressive
        # detail not needed for a decorative background loop - ignored.


def run_channel(sections, resolve, label, base_tick, notes,
                init_program=None, init_pan=64, init_vol=127):
    """Interpret a CHAN section, dispatching ldlayer into run_layer(). Notes
    from all its layers are appended to the shared `notes` list.

    `instr`/`pan` are per-hardware-channel-slot state in the real engine: a
    channel script that never calls `instr` (like every loop-body channel
    here) keeps whatever the slot's PREVIOUS script left it at, rather than
    defaulting to nothing. init_program/init_pan carry that forward from
    whatever ran in this slot before. Returns the final (program, pan) so a
    caller can thread state across successive ldchan calls on the same slot.

    Several intro channels call `ldlayer` BEFORE the `instr`/`pan` that are
    meant to apply to it (e.g. CHAN_007A: ldlayer, ..., instr SF6_INST_1, all
    with no delay between them). In the real engine, non-time-consuming
    opcodes within one instant all take effect before any note actually
    sounds - only delay/cdelay actually advance the clock. So `ldlayer` here
    doesn't spawn its layer immediately; it's queued and flushed (with
    whatever program/pan is current BY THEN) right before the next
    delay/cdelay, or at end-of-script.

    Layers are also not RUN during that walk, only recorded: a layer's notes
    need to sample the channel's volume at each note's own tick, and channel
    volume keeps being automated for the rest of the script (often long
    after the ldlayer that spawned the layer). So phase 1 walks the channel
    to build the complete volume timeline and collect spawns, and phase 2
    replays the layers against that finished timeline.
    """

    stack = []
    sec, idx = label, 0
    local_tick = 0
    program = init_program
    pan = init_pan
    vol = init_vol
    vol_timeline = [(base_tick, vol)]
    pending_layers = []  # [(tick, layer_label), ...] not yet attributed
    spawns = []          # [(tick, layer_label, program, pan), ...]

    def flush_pending():
        for tick, layer_label in pending_layers:
            spawns.append((tick, layer_label, program, pan))
        pending_layers.clear()

    while True:
        instrs = sections[sec]["instrs"]
        if idx >= len(instrs):
            if stack:
                sec, idx = stack.pop()
                continue
            flush_pending()
            break

        mnemonic, args = instrs[idx]
        idx += 1

        if mnemonic in ("delay", "cdelay"):
            flush_pending()
            local_tick += args[0]
        elif mnemonic == "instr":
            program = args[0]
        elif mnemonic == "pan":
            pan = args[0]
        elif mnemonic == "vol":
            vol = args[0]
            vol_timeline.append((base_tick + local_tick, vol))
        elif mnemonic == "ldlayer":
            _slot, layer_label = args
            pending_layers.append((base_tick + local_tick, layer_label))
        elif mnemonic == "call":
            target = args[0]
            stack.append((sec, idx))
            sec, idx = resolve[target]
        elif mnemonic == "end":
            if stack:
                sec, idx = stack.pop()
            else:
                flush_pending()
                break
        elif mnemonic == "jump":
            sec, idx = resolve[args[0]]
        # reverb/notepri/vibdepth/vibfreq/filter/mutebhv/noshort/short:
        # expressive detail not needed here - ignored.

    # Phase 2: now that vol_timeline is complete, replay the layers.
    for tick, layer_label, prog, pn in spawns:
        run_layer(sections, resolve, layer_label, tick, prog, pn, notes,
                  vol_timeline)

    return program, pan, vol


def run_sequence(sections, resolve):
    """Interpret the SEQ section from its true start up to (but not
    including) the wraparound `jump SEQ_0027`, i.e. the intro plus one lap
    of the main loop, as a single unit. Returns (notes, tempo_events,
    loop_length_ticks). tempo_events is [(tick, bpm), ...].

    channel_slot_state threads (program, pan, vol) across successive `ldchan`
    calls on the same hardware slot within this one pass - needed because
    every loop-body channel (CHAN_017F etc.) never sets `instr` itself and
    relies on whatever the intro channel for that slot left behind. The same
    goes for volume: CHAN_0C91/CHAN_0CA3 (the two loudest parts) never set
    `vol` in the loop body at all and inherit 127 from the intro."""

    channel_slot_state = {}  # slot -> (program, pan, vol)
    notes = []
    tempo_events = []

    sec, idx = "SEQ_0000", 0
    tick = 0

    while True:
        instrs = sections[sec]["instrs"]
        mnemonic, args = instrs[idx]
        idx += 1

        if mnemonic == "tempo":
            tempo_events.append((tick, args[0]))
        elif mnemonic == "delay":
            tick += args[0]
        elif mnemonic == "ldchan":
            slot, chan_label = args
            init_program, init_pan, init_vol = channel_slot_state.get(
                slot, (None, 64, 127))
            channel_slot_state[slot] = run_channel(
                sections, resolve, chan_label, tick, notes,
                init_program, init_pan, init_vol)
        elif mnemonic == "jump":
            target_sec, target_idx = resolve[args[0]]
            if (target_sec, target_idx) == resolve[LOOP_START_LABEL]:
                break  # the wraparound - this marks the loop's end
            sec, idx = target_sec, target_idx
            continue
        elif mnemonic == "end":
            break
        # vol/mutescale/mutebhv/initchan/freechan: not needed for playback.

    assert tempo_events, "no tempo changes found - tempo map would be empty"
    return notes, tempo_events, tick


# --------------------------------------------------------------------------
# Tick -> frame conversion
# --------------------------------------------------------------------------

def build_tick_to_ms(tempo_events, loop_end_tick):
    """tempo_events: [(tick, bpm), ...] sorted ascending, first at tick 0.
    Returns a function tick -> milliseconds via piecewise integration."""

    ms_per_tick = 60000.0 / (TICKS_PER_QUARTER)  # divided by bpm below

    # Precompute cumulative ms at the start of each tempo segment.
    segment_start_ms = [0.0]
    for i in range(1, len(tempo_events)):
        prev_tick, prev_bpm = tempo_events[i - 1]
        cur_tick, _ = tempo_events[i]
        seg_ms = (cur_tick - prev_tick) * (ms_per_tick / prev_bpm)
        segment_start_ms.append(segment_start_ms[-1] + seg_ms)

    def tick_to_ms(tick):
        # Find the last tempo segment starting at or before `tick`.
        i = 0
        for j, (t, _bpm) in enumerate(tempo_events):
            if t <= tick:
                i = j
            else:
                break
        seg_tick, seg_bpm = tempo_events[i]
        return segment_start_ms[i] + (tick - seg_tick) * (ms_per_tick / seg_bpm)

    total_ms = tick_to_ms(loop_end_tick)
    return tick_to_ms, total_ms


# --------------------------------------------------------------------------
# Resolving (program, note) -> (sample_index, playback_rate)
#
# Done here rather than on the Saturn because the SH2 build has no pow()/
# libm, and this only needs a small, regular table already produced by
# tools/make_title_samples.py - reparsing its generated header (rather than
# re-deriving the tables by hand a second time) means the two scripts can't
# silently drift apart.
# --------------------------------------------------------------------------

SAMPLE_ROW_RE = re.compile(
    r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}")
INSTR_ROW_RE = re.compile(
    r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}")


def load_sample_tables():
    if not SAMPLES_HEADER.is_file():
        sys.exit(f"{SAMPLES_HEADER} not found - run make_title_samples.py first")

    text = SAMPLES_HEADER.read_text()

    samples_block = text.split("title_samples[")[1].split("};")[0]
    samples = [
        {"offset": int(m.group(1)), "length": int(m.group(2)),
         "loop_start": int(m.group(3)), "base_rate": int(m.group(4)),
         "base_note": int(m.group(5))}
        for m in SAMPLE_ROW_RE.finditer(samples_block)
    ]

    instr_block = text.split("title_instruments[")[1].split("};")[0]
    instruments = {
        int(m.group(1)): {
            "sample_lo": int(m.group(2)), "sample_norm": int(m.group(3)),
            "sample_hi": int(m.group(4)), "range_lo": int(m.group(5)),
            "range_hi": int(m.group(6)), "decay": int(m.group(7)),
        }
        for m in INSTR_ROW_RE.finditer(instr_block)
    }

    assert samples and instruments, "failed to parse title_samples.h tables"
    return samples, instruments


def resolve_note(samples, instruments, program, note):
    """-> (sample_index, playback_rate_hz)."""
    instr = instruments[program]
    if note < instr["range_lo"]:
        sample_index = instr["sample_lo"]
    elif note > instr["range_hi"]:
        sample_index = instr["sample_hi"]
    else:
        sample_index = instr["sample_norm"]

    s = samples[sample_index]
    rate = round(s["base_rate"] * (2.0 ** ((note - s["base_note"]) / 12.0)))
    return sample_index, rate


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def main():
    if not SEQ_FILE.is_file():
        sys.exit(f"sequence file not found: {SEQ_FILE}")
    if not ASEQ_H.is_file():
        sys.exit(f"aseq.h not found: {ASEQ_H}")

    samples, instruments = load_sample_tables()

    sections, resolve = parse_sequence_file()
    notes, tempo_events, loop_end_tick = run_sequence(sections, resolve)
    tempo_events.sort(key=lambda te: te[0])

    tick_to_ms, total_ms = build_tick_to_ms(tempo_events, loop_end_tick)

    notes.sort(key=lambda n: n.tick)

    programs = sorted({n.program for n in notes})
    print(f"parsed {len(notes)} note events across instrument programs {programs}")
    print(f"loop length: {loop_end_tick} ticks, {total_ms / 1000:.2f}s, "
          f"{len(tempo_events)} tempo changes")

    loop_frames = round(total_ms * FRAME_RATE / 1000.0)
    if loop_frames > 0xFFFF:
        sys.exit(f"loop is {loop_frames} frames, exceeds u16 - shouldn't "
                 f"happen for a title loop, check tempo parsing")

    # rate is a uint16_t on the Saturn side, so 65535 is the hard ceiling.
    # (Ponesound's own PCM_CALC_OCT/FNS encoding can express up to roughly
    # 88kHz, and its convert_bitrate_to_pitchword takes an int in our copy -
    # upstream's signed short overflowed and indexed logtbl[] out of bounds
    # for anything over 32767.) Extreme transpositions are legitimate here:
    # a low split sample stretched near the top of its assigned range can
    # sit 1-2 octaves above its own root, which is just how this soundfont
    # is authored. Clamp rather than error.
    RATE_MAX = 65535
    clamped = 0

    events = []
    rate_min, rate_max = 999999, 0
    for n in notes:
        frame = round(tick_to_ms(n.tick) * FRAME_RATE / 1000.0)
        # A note landing exactly on the wrap boundary belongs to frame 0 of
        # the next lap, not one-past-the-end of this one.
        frame %= max(loop_frames, 1)
        duration_ms = n.sound_ticks * (60000.0 / TICKS_PER_QUARTER) / \
            [bpm for t, bpm in tempo_events if t <= n.tick][-1]
        duration_frames = max(1, round(duration_ms * FRAME_RATE / 1000.0))

        sample_index, rate = resolve_note(samples, instruments, n.program, n.note)
        if rate > RATE_MAX:
            clamped += 1
            rate = RATE_MAX
        rate_min, rate_max = min(rate_min, rate), max(rate_max, rate)

        # Note velocity scaled by the channel's volume at note-on. Without
        # the channel term, every part plays at full tilt and the two
        # vol-127 channels bury everything else.
        level = (n.velocity * n.chan_vol) // 127
        level = max(0, min(127, level))

        decay = instruments[n.program]["decay"]

        events.append((frame, duration_frames, sample_index, rate, level,
                       n.pan, decay))

    events.sort(key=lambda e: e[0])
    print(f"playback rates span {rate_min}-{rate_max} Hz across all "
          f"transposed notes")
    if clamped:
        print(f"clamped {clamped}/{len(events)} events to {RATE_MAX} Hz "
              f"(would have exceeded the u16 rate field / SCSP's sane range)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(HEADER_OUT, "w") as f:
        f.write("/* Generated by tools/make_title_sequence.py - do not hand-edit.\n")
        f.write(" * NA_BGM_TITLE (Sequence_30): intro + main loop as one repeating unit. */\n")
        f.write("#ifndef TITLE_SEQUENCE_H\n#define TITLE_SEQUENCE_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write(f"#define TITLE_SEQUENCE_EVENT_COUNT {len(events)}\n")
        f.write(f"#define TITLE_SEQUENCE_LOOP_FRAMES {loop_frames}\n\n")

        f.write("/* sample_index/rate are pre-resolved on the host (program+note range\n"
                " * lookup, and base_rate*2^((note-base_note)/12)) since the SH2 build\n"
                " * has no pow()/libm - see resolve_note() in the generator. The player\n"
                " * just feeds rate straight to Ponesound's pitchword conversion. */\n")
        f.write("typedef struct {\n"
                "        uint16_t start_frame;    /* at TITLE_SEQUENCE_LOOP_FRAMES wraparound */\n"
                "        uint16_t duration_frames;\n"
                "        uint8_t  sample_index;   /* into title_samples[] */\n"
                "        uint16_t rate;           /* Hz to play the sample at */\n"
                "        uint8_t  level;          /* 0-127: note velocity x channel volume */\n"
                "        uint8_t  pan;            /* 0-127, 64 = centre (z64 convention) */\n"
                "        uint16_t decay;          /* frames to fade to silence; 0 = sustains */\n"
                "} title_note_event_t;\n\n")

        f.write("static const title_note_event_t title_sequence[TITLE_SEQUENCE_EVENT_COUNT] = {\n")
        for frame, dur, sample_index, rate, level, pan, decay in events:
            f.write(f"        {{ {frame:5d}, {dur:5d}, {sample_index:2d}, {rate:6d}, "
                    f"{level:3d}, {pan:3d}, {decay:4d} }},\n")
        f.write("};\n\n#endif /* !TITLE_SEQUENCE_H */\n")

    print(f"wrote {HEADER_OUT}")


if __name__ == "__main__":
    main()
