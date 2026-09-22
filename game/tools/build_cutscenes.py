"""Bake OoT's opening cutscenes into integer tables the SH-2 can just step.

The four cutscenes of the new-game opening are read straight from the decomp's
extracted `.csdata.inc.c` files. Those are plain C macro calls, so no ROM read
and no segment pointers are involved -- the text of the macros IS the data.

Everything expensive happens here: the camera splines are evaluated with OoT's
own B-spline maths (a port of src/code/z_cutscene_spline.c, floats and all) and
written out as per-frame integer eye/at/yaw/pitch samples. The Saturn runtime
then owns no float, no spline and no script parser; it steps a table.

Two details that are easy to get wrong and change the result:

  * `func_800BB2B4` is called TWICE per rendered frame -- once for the eye
    spline and once for the at spline -- sharing ONE keyframe/curFrame pair
    (z_camera.c:5861). The spline therefore advances twice per frame. Baking it
    once per frame produces a camera that crawls at half speed.
  * A cutscene frame is one 20 Hz game tick, not a 60 Hz video frame.

Camera tracks go to CS<n>.BIN on the disc rather than into the binary: the four
of them are about 29 KB together and the gap between .bss and the SGL work area
is under 12 KB. Only the small event lists are linked.

Offline tool: floating point is allowed here and nowhere in game/src.
"""
import hashlib
import math
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import oot_messages                                             # noqa: E402

# The cutscene text is drawn across the whole screen, not inside the 34-column
# NPC box, so it keeps the original's own line breaks at full width.
MESSAGE_COLUMNS = 38
MESSAGE_LINES = 4

ROOT = pathlib.Path(__file__).resolve().parents[1]
OOT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
SCENES = OOT / 'extracted/ntsc-1.2/assets/scenes'

# One 20 Hz cutscene tick. The runtime steps the baked table at this rate.
CS_TICK_HZ = 20

# The opening chain, in the order CS_DESTINATION links them. `key` is what the
# runtime and the generated header call each one.
CUTSCENE_PATHS = [
    'indoors/link_home/gLinkHouseIntroSleepCs.csdata.inc.c',
    'overworld/spot00/gHyruleFieldIntroNightmareCs.csdata.inc.c',
    'overworld/spot04/gKokiriForestIntroNaviFlyingCs.csdata.inc.c',
    'indoors/link_home/gLinkHouseIntroWakeUpCs.csdata.inc.c',
]

# The BGM each cutscene's own scene layer sets, from its
# SCENE_CMD_SOUND_SETTINGS. This is NOT in the cutscene script: the Deku Tree's
# theme is spot04's scene music, and the script only ever stops it. Without it
# the speech played in silence and the stop had nothing to stop.
CUTSCENES = [
    dict(key='SLEEP',     scene='LINK_HOME', path=SCENES / CUTSCENE_PATHS[0],
         # link_home's cutscene layer is NA_BGM_GENERAL_SFX: ambience only.
         scene_bgm=None),
    dict(key='NIGHTMARE', scene='SPOT00',    path=SCENES / CUTSCENE_PATHS[1],
         # spot00's dream layer is NA_BGM_NO_MUSIC until Ganon's theme starts.
         scene_bgm=None),
    dict(key='NAVI_FLY',  scene='SPOT04',    path=SCENES / CUTSCENE_PATHS[2],
         scene_bgm='NA_BGM_DEKU_TREE_CS'),
    dict(key='WAKE_UP',   scene='LINK_HOME', path=SCENES / CUTSCENE_PATHS[3],
         scene_bgm=None),
]

# CS_DESTINATION values we honour, mapped to the next cutscene's key. The
# originals are entrance indices; the opening only ever chains within itself.
DESTINATIONS = {
    'CS_DEST_HYRULE_FIELD_INTRO_DREAM': 'NIGHTMARE',
    'CS_DEST_KOKIRI_FOREST_INTRO':      'NAVI_FLY',
    'CS_DEST_LINKS_HOUSE_INTRO':        'WAKE_UP',
}

# Screen transitions. The Saturn side has one fade primitive, so each original
# type is reduced to a colour and a direction; the timing is kept exactly.
TRANSITIONS = {
    'CS_TRANS_GRAY_FILL_IN':            ('GRAY',  'IN'),
    'CS_TRANS_BLACK_FILL_IN':           ('BLACK', 'IN'),
    'CS_TRANS_WHITE_FILL_IN':           ('WHITE', 'IN'),
    'CS_TRANS_GRAY_FILL_OUT':           ('GRAY',  'OUT'),
    'CS_TRANS_BLACK_FILL_OUT':          ('BLACK', 'OUT'),
    'CS_TRANS_WHITE_FILL_OUT':          ('WHITE', 'OUT'),
    'CS_TRANS_BLACK_FILL_OUT_TO_HALF':  ('BLACK', 'OUT_HALF'),
    'CS_TRANS_BLACK_FILL_IN_FROM_HALF': ('BLACK', 'IN_HALF'),
    'CS_TRANS_TRIGGER_INSTANCE':        ('BLACK', 'INSTANT'),
}

# Music. Each original sequence becomes one of our CD banks; see
# src/music_banks.c. A sequence with no bank yet is recorded as NONE rather
# than silently mapped to whatever is already playing.
SEQUENCES = {
    'NA_BGM_OPENING_GANON': 'NIGHTMARE',
    'NA_BGM_DEKU_TREE_CS':  'DEKU_TREE',
    'NA_BGM_NAVI_OPENING':  'NAVI',
}

# Player cue ids -> our Link clips. The originals are in z_player.c:15039-15042.
# Anything not listed holds the previous pose rather than guessing a clip.
PLAYER_CUES = {
    'PLAYER_CUEID_28': 'SLEEPING',     # func_80851F84, clink_op3_wait1
    'PLAYER_CUEID_29': 'TURN_OVER',    # func_80851E90, clink_op3_negaeri
    'PLAYER_CUEID_30': 'SIT_UP',       # gPlayerAnim_clink_op3_okiagari
    'PLAYER_CUEID_31': 'STAND_UP',     # gPlayerAnim_clink_op3_tatiagari
    'PLAYER_CUEID_3':  'LOOK_AROUND',  # CSACTION_5, gPlayerAnim_link_demo_bikkuri
    # CSACTION_8 -> func_808515A4 (z_player.c:15393), which loops the ordinary
    # standing idle, PLAYER_ANIMGROUP_nwait. We already have that clip.
    'PLAYER_CUEID_5':  'IDLE',
    # CSACTION_9, gPlayerAnim_link_demo_furimuki: Link turns and looks back.
    'PLAYER_CUEID_6':  'TURN_LOOK',
    # CSACTION_3 and _4 are { 0, NULL } in z_player.c:15003 -- the cue places
    # and turns Link but changes no animation. HOLD is the faithful mapping,
    # not a missing one, so it must be spelled out rather than left unmapped.
    'PLAYER_CUEID_1':  'HOLD',
    'PLAYER_CUEID_2':  'HOLD',
    'PLAYER_CUEID_4':  'HOLD',
}

# Commands with no Saturn meaning. Recorded in the generated header so their
# absence is a decision on the record rather than an oversight.
IGNORED = ('CS_UNK_DATA_LIST', 'CS_UNK_DATA',
           'CS_RUMBLE_CONTROLLER_LIST', 'CS_RUMBLE_CONTROLLER',
           'CS_LIGHT_SETTING_LIST', 'CS_LIGHT_SETTING',
           'CS_TIME_LIST', 'CS_TIME')

CALL = re.compile(r'(CS_[A-Z0-9_]+)\s*\(')


# ---- reading the macro files ------------------------------------------------

def split_args(text):
    """Split one macro's argument text on commas at paren depth 0."""
    args, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            args.append(text[start:i].strip())
            start = i + 1
    tail = text[start:].strip()
    if tail:
        args.append(tail)
    return args


def parse_calls(path):
    """Every CS_* macro call in the file, in order, as (name, [args])."""
    # The decomp's files carry Shift-JIS bytes in comments; the data is ASCII.
    source = path.read_text(encoding='utf-8', errors='replace')
    # Strip comments so a commented-out command cannot be read as data.
    source = re.sub(r'/\*.*?\*/', ' ', source, flags=re.S)
    source = re.sub(r'//[^\n]*', ' ', source)
    calls, at = [], 0
    while True:
        found = CALL.search(source, at)
        if not found:
            return calls
        depth, i = 1, found.end()
        while depth:
            if source[i] == '(':
                depth += 1
            elif source[i] == ')':
                depth -= 1
            i += 1
        calls.append((found.group(1), split_args(source[found.end():i - 1])))
        at = i


def number(text):
    """One macro argument as an int. CS_FLOAT(hex, f) keeps the float."""
    text = text.strip()
    if text.startswith('CS_FLOAT'):
        return float(split_args(text[text.index('(') + 1:-1])[1].rstrip('f'))
    if text.startswith('0x') or text.startswith('0X'):
        value = int(text, 16)
        # The macros write s16 fields as unsigned hex.
        return value - 0x10000 if 0x8000 <= value <= 0xFFFF else value
    return int(text, 0)


# ---- OoT's camera spline (z_cutscene_spline.c) ------------------------------

def spline_point(u, p0, p1, p2, p3):
    """func_800BB0A0: uniform cubic B-spline over four points.

    Each point is (x, y, z, roll, viewAngle), so the same weights produce the
    position and the two scalar channels in one pass, as the original does."""
    u = min(u, 1.0)
    c = ((1 - u) ** 3 / 6.0,
         u ** 3 / 2.0 - u * u + 2.0 / 3.0,
         -u ** 3 / 2.0 + u * u / 2.0 + u / 2.0 + 1.0 / 6.0,
         u ** 3 / 6.0)
    points = (p0, p1, p2, p3)
    return [sum(c[i] * points[i][k] for i in range(4)) for k in range(5)]


class Spline:
    """func_800BB2B4. `key` and `frame` are shared between the eye and at
    splines of one shot, exactly as the camera's rwData is."""

    def __init__(self, points):
        # (continueFlag, roll, nextPointFrame, viewAngle, x, y, z)
        self.points = [(p[0], ((int(p[1]) + 128) % 256) - 128, *p[2:])
                       for p in points]

    def stopped(self, key):
        for i in range(3):
            index = key + i
            if index >= len(self.points) or self.points[index][0] == 'CS_CAM_STOP':
                return True
        return False

    def sample(self, state):
        """One call. Returns (pos, roll, fov) or None at the end, and advances
        the shared state the way the original does."""
        key = state['key']
        if self.stopped(key):
            return None
        window = [[self.points[key + i][4], self.points[key + i][5],
                   self.points[key + i][6], self.points[key + i][1],
                   self.points[key + i][3]] for i in range(4)]
        out = spline_point(state['frame'], *window)
        speed1 = speed2 = 0.0
        if key + 1 < len(self.points) and self.points[key + 1][2] != 0:
            speed1 = 1.0 / self.points[key + 1][2]
        if key + 2 < len(self.points) and self.points[key + 2][2] != 0:
            speed2 = 1.0 / self.points[key + 2][2]
        advance = max(0.0, state['frame'] * (speed2 - speed1) + speed1)
        state['frame'] += advance
        if state['frame'] >= 1.0:
            state['key'] += 1
            index = state['key'] + 3
            if index >= len(self.points) or \
                    self.points[index][0] == 'CS_CAM_STOP':
                state['key'] = 0
            state['frame'] -= 1.0
        return (out[0], out[1], out[2]), out[3], out[4]


def bake_shot(eye_spline, at_spline, frames):
    """Per-frame (eye, at, roll, fov) for one shot, with the shared-state
    double advance the original performs."""
    state = {'key': 0, 'frame': 0.0}
    track = []
    for _ in range(frames):
        eye = eye_spline.sample(state)
        at = at_spline.sample(state)
        if eye is None or at is None:
            break
        track.append((eye[0], at[0], at[1], at[2]))
    return track


def look_angles(eye, at):
    """Integer yaw/pitch in 65536 units, matching the runtime camera's
    convention (see demo.c: pitch is negated relative to OoT's)."""
    dx, dy, dz = at[0] - eye[0], at[1] - eye[1], at[2] - eye[2]
    flat = math.hypot(dx, dz)
    yaw = round(math.atan2(dx, dz) * 65536 / math.tau)
    pitch = round(math.atan2(dy, flat) * 65536 / math.tau) if flat else 0
    return (yaw + 32768) % 65536 - 32768, (pitch + 32768) % 65536 - 32768


def clamp16(value, what):
    value = int(round(value))
    if not -32768 <= value <= 32767:
        raise ValueError('%s out of s16 range: %d' % (what, value))
    return value


# ---- turning one file into a cutscene ---------------------------------------

def read_cutscene(entry):
    """Parse one .csdata.inc.c into {frames, camera track, events}."""
    calls = parse_calls(entry['path'])
    if not calls or calls[0][0] != 'CS_HEADER':
        raise ValueError('%s does not start with CS_HEADER' % entry['path'])

    out = dict(key=entry['key'], scene=entry['scene'], header_frames=0,
               frames=0, track=[], text=[], actor_cues=[], player_cues=[],
               transitions=[], music=[], destination=None, stop_frame=None,
               ignored=set(), misc=[])

    eye_shots, at_shots, pending = [], [], None
    actor_channels, current_channel = [], 0
    for name, args in calls:
        if name in IGNORED:
            out['ignored'].add(name)
            continue
        if name == 'CS_HEADER':
            out['header_frames'] = number(args[1])
        elif name in ('CS_CAM_EYE_SPLINE', 'CS_CAM_AT_SPLINE'):
            pending = dict(kind=name, start=number(args[0]),
                           end=number(args[1]), points=[])
            (eye_shots if name == 'CS_CAM_EYE_SPLINE' else at_shots).append(pending)
        elif name == 'CS_CAM_POINT':
            if pending is None:
                raise ValueError('CS_CAM_POINT outside a spline')
            pending['points'].append((args[0].strip(), number(args[1]),
                                      number(args[2]), number(args[3]),
                                      number(args[4]), number(args[5]),
                                      number(args[6])))
        elif name == 'CS_TEXT':
            out['text'].append(dict(id=number(args[0]), start=number(args[1]),
                                    end=number(args[2])))
        elif name == 'CS_TEXT_NONE':
            out['text'].append(dict(id=None, start=number(args[0]),
                                    end=number(args[1])))
        elif name == 'CS_ACTOR_CUE_LIST':
            # Each list names a cue channel, and each channel is one actor on
            # screen. The dream has two: the rider being chased and the chaser.
            channel = re.fullmatch(r'CS_CMD_ACTOR_CUE_(\d+)_\d+', args[0].strip())
            if channel is None:
                raise ValueError('Unknown actor cue channel ' + args[0])
            current_channel = int(channel[1])
        elif name == 'CS_ACTOR_CUE':
            actor_cue = cue(args)
            actor_cue['channel'] = current_channel
            out['actor_cues'].append(actor_cue)
        elif name == 'CS_PLAYER_CUE':
            entry_cue = cue(args)
            entry_cue['clip'] = PLAYER_CUES.get(args[0].strip())
            out['player_cues'].append(entry_cue)
        elif name == 'CS_TRANSITION':
            kind = TRANSITIONS.get(args[0].strip())
            if kind is None:
                raise ValueError('unmapped transition ' + args[0])
            out['transitions'].append(dict(colour=kind[0], direction=kind[1],
                                           start=number(args[1]),
                                           end=number(args[2])))
        elif name in ('CS_START_SEQ', 'CS_STOP_SEQ'):
            out['music'].append(dict(bank=SEQUENCES.get(args[0].strip()),
                                     sequence=args[0].strip(),
                                     stop=(name == 'CS_STOP_SEQ'),
                                     start=number(args[1])))
        elif name == 'CS_DESTINATION':
            out['destination'] = dict(dest=args[0].strip(),
                                      next=DESTINATIONS.get(args[0].strip()),
                                      start=number(args[1]))
        elif name == 'CS_MISC':
            if args[0].strip() == 'CS_MISC_STOP_CUTSCENE':
                out['stop_frame'] = number(args[1])
            else:
                kind = args[0].strip()
                if kind not in ('CS_MISC_RAIN', 'CS_MISC_LIGHTNING',
                                'CS_MISC_SET_CSFLAG_0', 'CS_MISC_SET_LOCKED_VIEWPOINT'):
                    raise ValueError('Unimplemented CS_MISC: ' + kind)
                out['misc'].append(dict(kind=kind, start=number(args[1]), end=number(args[2])))

    # The header's frameCount is an allotment, not a length: every one of these
    # cutscenes declares 3000 and none runs anywhere near it. The real end is
    # whichever comes first of CS_DESTINATION and CS_MISC_STOP_CUTSCENE, and
    # failing both, the last frame any event or shot touches. Baking the
    # declared 3000 would put 42 KB per cutscene on the disc for nothing.
    if entry.get('scene_bgm'):
        out['music'].insert(0, dict(bank=SEQUENCES.get(entry['scene_bgm']),
                                    sequence=entry['scene_bgm'],
                                    stop=False, start=0))
    # The macros arrive grouped by list, not in time order: the stop at frame
    # 192 was written after the start at 200. The runtime walks this with one
    # cursor, so it has to be in frame order or a cue is skipped outright.
    out['music'].sort(key=lambda m: m['start'])
    # Transitions arrive grouped by list too, and the runtime walks them in
    # order looking for the one covering this frame. An older transition later
    # in the file would otherwise win over the current one and the screen fade
    # would jump backwards. Same fault the music cues had.
    out['transitions'].sort(key=lambda f: f['start'])
    # Preserve source order: the last active cue in file order wins.

    out['frames'] = cutscene_length(out, eye_shots, at_shots)
    out['track'] = bake_camera(eye_shots, at_shots, out['frames'], out['scene'])
    return out


def cutscene_length(out, eye_shots, at_shots):
    ends = [0]
    for item in out['text'] + out['transitions']:
        ends.append(item['end'])
    for item in out['actor_cues'] + out['player_cues']:
        ends.append(item['end'])
    for item in out['music']:
        ends.append(item['start'])
    for shot in eye_shots + at_shots:
        ends.append(shot['end'])
    last = max(ends)
    # A cutscene that hands off does so before its own events finish; the
    # frames after the handoff are never seen.
    for stop in (out['stop_frame'],
                 out['destination']['start'] if out['destination'] else None):
        if stop is not None:
            last = min(last, stop)
    return min(last + 1, out['header_frames'])


def cue(args):
    """Keep authored rotation; each actor decides how to use it."""
    return dict(id=args[0].strip(), start=number(args[1]), end=number(args[2]),
                rot_y=number(args[4]),
                start_pos=(number(args[6]), number(args[7]), number(args[8])),
                end_pos=(number(args[9]), number(args[10]), number(args[11])))


def bake_camera(eye_shots, at_shots, frames, scene=None):
    """Per-frame camera for the whole cutscene.

    Shots are paired in order: OoT emits one CS_CAM_AT_SPLINE for each
    CS_CAM_EYE_SPLINE, and the pair shares spline state. Frames not covered by
    any shot hold the last sample, which is what the original does when no
    cutscene camera command is active.
    """
    track = [None] * frames
    for eye, at in zip(eye_shots, at_shots):
        if len(eye['points']) < 4 or len(at['points']) < 4:
            continue                      # a spline needs four control points
        span = max(0, min(eye['end'], frames) - eye['start'])
        shot = bake_shot(Spline(eye['points']), Spline(at['points']), span)
        for i, sample in enumerate(shot):
            at_frame = eye['start'] + i
            if 0 <= at_frame < frames:
                track[at_frame] = sample

    baked, last = [], None
    for sample in track:
        if sample is None:
            sample = last
        last = sample
        if sample is None:
            baked.append((0, 0, 0, 0, 0, 0, 0))
            continue
        eye, look, roll, fov = sample
        yaw, pitch = look_angles(eye, look)
        # Store the SGL screen distance rather than the fov, by the same rule
        # build_scene_table.py uses for a prerendered room's fixed camera: half
        # the 240-line picture over tan(fov/2). The SH-2 has no tangent, and
        # the runtime held the gameplay distance of 240 for every shot, which
        # is a far wider field than these 25-32 degree shots want -- the whole
        # dream was framed wrongly for it.
        half = max(1.0, fov) * math.pi / 360.0
        distance = 120.0 / math.tan(half) if half > 0 else 240.0
        # View_SetScale scales every homogeneous projection component,
        # including W (guPerspectiveF); it does not change the field of view.
        baked.append((clamp16(eye[0], 'eye x'), clamp16(eye[1], 'eye y'),
                      clamp16(eye[2], 'eye z'), yaw,
                      # look_angles() already returns the RENDERER's
                      # convention -- positive is up, measured from eye to at.
                      # demo.c negates a bgCam pitch because OoT *stores* one
                      # the other way round; negating this one too pointed
                      # every shot at the ground and put the camera under the
                      # floor for the whole dream.
                      pitch, clamp16(roll * 256, 'roll'),
                      clamp16(min(distance, 32000.0), 'screen distance')))
    return baked


# ---- output -----------------------------------------------------------------

TRACK_FORMAT = '>7h'            # x, y, z, yaw, pitch, roll, fov*100
TRACK_BYTES = struct.calcsize(TRACK_FORMAT)


def pack_track(track):
    return b''.join(struct.pack(TRACK_FORMAT, *point) for point in track)


def collect_messages(cutscenes, messages):
    """Every message the opening shows, parsed into pages and coloured runs.

    The ids come from the cutscenes' own CS_TEXT commands, so nothing is
    included that the opening does not actually say, and nothing it does say
    can be left out.
    """
    wanted = []
    for cs in cutscenes:
        for item in cs['text']:
            if item['id'] and item['id'] not in wanted:
                wanted.append(item['id'])
    out = []
    for text_id in sorted(wanted):
        message = messages.get(text_id)
        if not message:
            raise SystemExit('cutscene text 0x%04X is not in the message table'
                             % text_id)
        pages = oot_messages.parse_pages(message['body'],
                                         max_lines=MESSAGE_LINES,
                                         max_columns=MESSAGE_COLUMNS)
        if not pages:
            raise SystemExit('cutscene text 0x%04X has no English pages'
                             % text_id)
        out.append(dict(id=text_id, pages=pages,
                        box=message['box'], position=message['position']))
    return out


def emit_messages(messages, h, c):
    """Pooled runs/lines/pages, the same shape kokiri_dialogue.c uses."""
    boxes = sorted({m['box'] for m in messages})
    positions = sorted({m['position'] for m in messages})
    colours = sorted({colour for m in messages for page in m['pages']
                      for line in page['lines'] for _, colour in line['runs']})
    advances = ['button', 'delay', 'fade']

    h += ['/* Text the opening speaks, from the real US 1.2 message table.',
          '** A line is a list of coloured runs: COLOR() changes colour partway',
          '** through a line, so colour cannot be a property of the line. */',
          'typedef enum {']
    h += ['    CUTSCENE_COLOUR_%s = %d,' % (name, i)
          for i, name in enumerate(colours)]
    h += ['    CUTSCENE_COLOUR_COUNT = %d' % len(colours),
          '} cutscene_colour_t;', '', 'typedef enum {']
    h += ['    CUTSCENE_ADVANCE_%s = %d,' % (name.upper(), i)
          for i, name in enumerate(advances)]
    h += ['} cutscene_advance_t;', '',
          '/* The original box styles these messages use. */', 'typedef enum {']
    h += ['    CUTSCENE_BOX_%s = %d,' % (name.replace('TEXTBOX_TYPE_', ''), i)
          for i, name in enumerate(boxes)]
    h += ['} cutscene_box_t;', '', 'typedef enum {']
    h += ['    CUTSCENE_POS_%s = %d,' % (name.replace('TEXTBOX_POS_', ''), i)
          for i, name in enumerate(positions)]
    h += ['} cutscene_position_t;', '',
          'typedef struct { const char *text; unsigned char colour; }'
          ' cutscene_run_t;',
          '/* `indent` is the original\'s SHIFT, halved to character cells:',
          '** the narration is centred with it. */',
          'typedef struct { unsigned short first_run; unsigned char runs,'
          ' indent; } cutscene_line_t;',
          'typedef struct { unsigned short first_line; unsigned char lines;',
          '                 unsigned char advance; unsigned short delay; }'
          ' cutscene_page_t;',
          'typedef struct { unsigned short id; unsigned short first_page;',
          '                 unsigned char pages, box, position; }'
          ' cutscene_message_t;', '']

    runs, lines, pages, entries = [], [], [], []
    for message in messages:
        first_page = len(pages)
        for page in message['pages']:
            first_line = len(lines)
            for line in page['lines']:
                first_run = len(runs)
                runs.extend(line['runs'])
                lines.append((first_run, len(line['runs']), line['indent']))
            pages.append((first_line, len(page['lines']),
                          advances.index(page['advance']), page['delay']))
        entries.append((message['id'], first_page, len(message['pages']),
                        boxes.index(message['box']),
                        positions.index(message['position'])))

    h += ['#define CUTSCENE_RUN_COUNT     %d' % len(runs),
          '#define CUTSCENE_LINE_COUNT    %d' % len(lines),
          '#define CUTSCENE_PAGE_COUNT    %d' % len(pages),
          '#define CUTSCENE_MESSAGE_COUNT %d' % len(entries),
          '#define CUTSCENE_MESSAGE_COLUMNS %d' % MESSAGE_COLUMNS,
          '#define CUTSCENE_MESSAGE_LINES   %d' % MESSAGE_LINES, '',
          'extern const cutscene_run_t     cutscene_runs[CUTSCENE_RUN_COUNT];',
          'extern const cutscene_line_t    cutscene_text_lines[CUTSCENE_LINE_COUNT];',
          'extern const cutscene_page_t    cutscene_pages[CUTSCENE_PAGE_COUNT];',
          'extern const cutscene_message_t cutscene_messages[CUTSCENE_MESSAGE_COUNT];',
          '']

    c.append('const cutscene_run_t cutscene_runs[CUTSCENE_RUN_COUNT] = {')
    c += ['    {"%s",CUTSCENE_COLOUR_%s},' % (escape(text), colour)
          for text, colour in runs]
    c += ['};', '',
          'const cutscene_line_t cutscene_text_lines[CUTSCENE_LINE_COUNT] = {']
    c += ['    {%d,%d,%d},' % line for line in lines]
    c += ['};', '', 'const cutscene_page_t cutscene_pages[CUTSCENE_PAGE_COUNT] = {']
    c += ['    {%d,%d,%d,%d},' % page for page in pages]
    c += ['};', '',
          'const cutscene_message_t cutscene_messages[CUTSCENE_MESSAGE_COUNT] = {']
    c += ['    {0x%04X,%d,%d,%d,%d},' % entry for entry in entries]
    c += ['};', '']
    return len(runs), len(lines), len(pages)


def escape(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


def emit(cutscenes, header_path, source_path, cd_dir, messages):
    keys = [c['key'] for c in cutscenes]
    ignored = sorted(set().union(*(c['ignored'] for c in cutscenes)))

    h = ['/* Generated by tools/build_cutscenes.py. Do not edit. */',
         '#ifndef DOSEI_CUTSCENES_H', '#define DOSEI_CUTSCENES_H',
         '#include <stdint.h>', '',
         '/* One cutscene frame is a %d Hz tick, as in the original. */'
         % CS_TICK_HZ,
         '#define CUTSCENE_TICK_HZ %d' % CS_TICK_HZ,
         '#define CUTSCENE_TRACK_BYTES %d' % TRACK_BYTES,
         '',
         '/* Commands in the source cutscenes with no Saturn meaning, dropped',
         '** deliberately: %s. */' % (', '.join(ignored) if ignored else 'none'),
         '',
         'typedef enum {']
    h += ['    CUTSCENE_%s = %d,' % (key, i) for i, key in enumerate(keys)]
    h += ['    CUTSCENE_COUNT = %d' % len(keys), '} cutscene_id_t;', '']
    clips = sorted({c['clip'] for cs in cutscenes for c in cs['player_cues']})
    banks = sorted({m['bank'] for cs in cutscenes for m in cs['music']
                    if m['bank']})
    colours = sorted({f['colour'] for cs in cutscenes
                      for f in cs['transitions']})
    directions = sorted({f['direction'] for cs in cutscenes
                         for f in cs['transitions']})
    scenes = sorted({cs['scene'] for cs in cutscenes})

    h += ['/* Link\'s pose for a player cue. HOLD is not a clip: the cue moves',
          '** or turns him without changing the animation, which is what',
          '** several of the originals genuinely do. */',
          'typedef enum {']
    h += ['    CUTSCENE_CLIP_%s = %d,' % (clip, i)
          for i, clip in enumerate(clips)]
    h += ['    CUTSCENE_CLIP_COUNT = %d' % len(clips), '} cutscene_clip_t;', '']

    h += ['/* Music banks the opening asks for. NONE means the original played',
          '** a sequence this port has no bank for; the runtime leaves the',
          '** current score alone rather than substituting another. */',
          'typedef enum {', '    CUTSCENE_BANK_NONE = 0,']
    h += ['    CUTSCENE_BANK_%s = %d,' % (bank, i + 1)
          for i, bank in enumerate(banks)]
    h += ['    CUTSCENE_BANK_COUNT = %d' % (len(banks) + 1),
          '} cutscene_bank_t;', '']

    h += ['typedef enum {']
    h += ['    CUTSCENE_FADE_%s = %d,' % (name, i)
          for i, name in enumerate(colours)]
    h += ['    CUTSCENE_FADE_COLOUR_COUNT = %d' % len(colours),
          '} cutscene_fade_colour_t;', '', 'typedef enum {']
    h += ['    CUTSCENE_FADE_%s = %d,' % (name, i)
          for i, name in enumerate(directions)]
    h += ['    CUTSCENE_FADE_DIRECTION_COUNT = %d' % len(directions),
          '} cutscene_fade_direction_t;', '']

    h += ['/* Which scene each cutscene plays in. Kept separate from the',
          '** scene_table indices: the opening needs scenes that are not',
          '** extracted yet, and the runtime resolves these to table entries',
          '** so a missing one is a handled case rather than a link error. */',
          'typedef enum {']
    h += ['    CUTSCENE_SCENE_%s = %d,' % (name, i)
          for i, name in enumerate(scenes)]
    h += ['    CUTSCENE_SCENE_COUNT = %d' % len(scenes),
          '} cutscene_scene_t;', '']

    h += ['/* `dist` is the SGL screen distance for the shot fov, computed',
          '** offline: the SH-2 has no tangent. */',
          'typedef struct { short x, y, z, yaw, pitch, roll, dist; }'
          ' cutscene_point_t;', '',
          '/* Event lists. Frames are cutscene ticks from the start. */',
          'typedef struct { unsigned short id; short start, end; }'
          ' cutscene_text_t;',
          'typedef struct { unsigned char clip; short start, end;'
          ' short x, y, z, ex, ey, ez; unsigned short yaw, id; }'
          ' cutscene_cue_t;',
          'typedef struct { unsigned char colour, direction; short start, end; }'
          ' cutscene_fade_t;',
          'typedef struct { unsigned char bank, stop; short start; }'
          ' cutscene_music_t;', '',
          'typedef struct {',
          '    const char             *track_file;  /* CS<n>.BIN on the disc */',
          '    unsigned short          frames;',
          '    unsigned char           scene;       /* scene_table index */',
          '    short                   stop_frame;  /* -1: none */',
          '    short                   destination; /* cutscene_id_t, -1: end */',
          '    short                   destination_frame;',
          '    const cutscene_text_t  *text;   unsigned char text_count;',
          '    const cutscene_cue_t   *cues;   unsigned char cue_count;',
          '    const cutscene_fade_t  *fades;  unsigned char fade_count;',
          '    const cutscene_music_t *music;  unsigned char music_count;',
          '    /* Actors the shot places. `clip` is the cue channel, which is',
          '    ** one actor on screen -- the dream has two. */',
          '    const cutscene_cue_t   *actor_cues;',
          '    unsigned char           actor_cue_count;',
          '} cutscene_t;', '',
          'extern const cutscene_t cutscenes[CUTSCENE_COUNT];', '']

    c = ['/* Generated by tools/build_cutscenes.py. Do not edit. */',
         '#include "cutscenes.h"', '']
    emit_messages(messages, h, c)
    misc_kinds = ['CS_MISC_RAIN', 'CS_MISC_LIGHTNING', 'CS_MISC_SET_CSFLAG_0',
                  'CS_MISC_SET_LOCKED_VIEWPOINT']
    events = [(i, misc_kinds.index(e['kind']), e['start'], e['end'])
              for i, cs in enumerate(cutscenes) for e in cs['misc']]
    h += ['typedef struct { unsigned char scene, kind; short start, end; } cutscene_misc_t;',
          '#define CUTSCENE_MISC_COUNT %d' % len(events),
          'extern const cutscene_misc_t cutscene_misc[CUTSCENE_MISC_COUNT];']
    c += ['const cutscene_misc_t cutscene_misc[CUTSCENE_MISC_COUNT] = {']
    c += ['    {%d,%d,%d,%d},' % e for e in events]
    c += ['};', '']
    h += ['#endif']
    for index, cs in enumerate(cutscenes):
        c.append('static const cutscene_text_t text_%d[] = {' % index)
        for item in cs['text']:
            c.append('    {0x%04X,%d,%d},' % (item['id'] if item['id'] else 0,
                                              item['start'], item['end']))
        c += ['};', '']
        c.append('static const cutscene_cue_t actor_cues_%d[] = {' % index)
        for item in cs['actor_cues']:
            c.append('    {%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d},' %
                     (item['channel'], item['start'], item['end'],
                      item['start_pos'][0], item['start_pos'][1],
                      item['start_pos'][2], item['end_pos'][0],
                      item['end_pos'][1], item['end_pos'][2],
                      item['rot_y'] & 0xFFFF, int(item['id'].split('_')[-1], 0)))
        c += ['};', '']
        c.append('static const cutscene_cue_t cues_%d[] = {' % index)
        for item in cs['player_cues']:
            clip = 'CUTSCENE_CLIP_' + (item['clip'] or 'HOLD')
            c.append('    {%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d},' %
                     (clip, item['start'], item['end'],
                      item['start_pos'][0], item['start_pos'][1],
                      item['start_pos'][2], item['end_pos'][0],
                      item['end_pos'][1], item['end_pos'][2],
                      item['rot_y'] & 0xFFFF, int(item['id'].split('_')[-1], 0)))
        c += ['};', '']
        c.append('static const cutscene_fade_t fades_%d[] = {' % index)
        for item in cs['transitions']:
            c.append('    {CUTSCENE_FADE_%s,CUTSCENE_FADE_%s,%d,%d},' %
                     (item['colour'], item['direction'],
                      item['start'], item['end']))
        c += ['};', '']
        c.append('static const cutscene_music_t music_%d[] = {' % index)
        for item in cs['music']:
            c.append('    {CUTSCENE_BANK_%s,%d,%d},' %
                     (item['bank'] or 'NONE', 1 if item['stop'] else 0,
                      item['start']))
        c += ['};', '']

    c.append('const cutscene_t cutscenes[CUTSCENE_COUNT] = {')
    for index, cs in enumerate(cutscenes):
        destination = -1
        destination_frame = -1
        if cs['destination'] and cs['destination']['next']:
            destination = keys.index(cs['destination']['next'])
            destination_frame = cs['destination']['start']
        c.append('    { "CS%d.BIN", %d, CUTSCENE_SCENE_%s, %d, %d, %d,'
                 ' text_%d, %d, cues_%d, %d, fades_%d, %d, music_%d, %d,'
                 ' actor_cues_%d, %d },' %
                 (index, len(cs['track']), cs['scene'],
                  cs['stop_frame'] if cs['stop_frame'] is not None else -1,
                  destination, destination_frame,
                  index, len(cs['text']), index, len(cs['player_cues']),
                  index, len(cs['transitions']), index, len(cs['music']),
                  index, len(cs['actor_cues'])))
    c += ['};', '']

    header_path.write_text('\n'.join(h) + '\n')
    source_path.write_text('\n'.join(c) + '\n')
    for index, cs in enumerate(cutscenes):
        (cd_dir / ('CS%d.BIN' % index)).write_bytes(pack_track(cs['track']))


def set_oot(root):
    """Point the tool at a decomp checkout. The other build_*.py tools take
    --oot the same way, so build.sh can pass one path to all of them."""
    global OOT, SCENES
    OOT = pathlib.Path(root)
    SCENES = OOT / 'extracted/ntsc-1.2/assets/scenes'
    for entry, original in zip(CUTSCENES, CUTSCENE_PATHS):
        entry['path'] = SCENES / original


def build():
    header = ROOT / 'build/generated/cutscenes.h'
    source = ROOT / 'build/generated/cutscenes.c'
    cd_dir = ROOT / 'build/cd'
    cd_dir.mkdir(parents=True, exist_ok=True)
    header.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(pathlib.Path(__file__).read_bytes())
    for entry in CUTSCENES:
        if not entry['path'].is_file():
            raise SystemExit('missing cutscene source: %s' % entry['path'])
        digest.update(entry['path'].read_bytes())
    signature = '/* ' + digest.hexdigest() + ' */'
    if header.exists() and header.read_text().startswith(signature) and \
            all((cd_dir / ('CS%d.BIN' % i)).is_file()
                for i in range(len(CUTSCENES))):
        print('Cutscenes: cached')
        return

    baked = [read_cutscene(entry) for entry in CUTSCENES]
    messages = collect_messages(baked, oot_messages.load_messages(OOT))
    emit(baked, header, source, cd_dir, messages)
    header.write_text(signature + '\n' + header.read_text())
    for cs, entry in zip(baked, CUTSCENES):
        print('Cutscene %-9s %4d frames, %2d text, %2d cues, %2d fades, '
              '%d music, %5d track bytes' %
              (cs['key'], cs['frames'], len(cs['text']),
               len(cs['player_cues']), len(cs['transitions']),
               len(cs['music']), len(cs['track']) * TRACK_BYTES))
    coloured = sum(1 for m in messages for page in m['pages']
                   for line in page['lines'] for _, colour in line['runs']
                   if colour != oot_messages.DEFAULT_COLOUR)
    print('Cutscene text: %d messages, %d pages, %d coloured runs' %
          (len(messages),
           sum(len(m['pages']) for m in messages), coloured))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', help='decomp checkout to read cutscenes from')
    options = parser.parse_args()
    if options.oot:
        set_oot(options.oot)
    sys.exit(build())
