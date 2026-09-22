"""Offline EnViewer opening animation playback and compact vertex tracks.

Tracks retain source-frame poses and use Q6 world coordinates. Repeated poses
share storage; runtime lookup is independent of rendering frame rate.
"""
import struct

import build_cutscenes as cutscenes


def timeline(kind, lengths):
    """EnViewer_UpdateImpl's layer-4 cue branches, in update order."""
    cs = cutscenes.read_cutscene(cutscenes.CUTSCENES[1])
    prefix = 'gYoungGanondorfHorseback'
    if kind == 'ganon':
        clip, speed, loop = prefix + 'IdleAnim', 1, True
    elif kind == 'horse_ganon':
        clip, speed, loop = 'gHorseGanonRearingAnim', 1, False
    elif kind == 'horse_zelda':
        clip, speed, loop = 'gHorseZeldaGallopingAnim', 3, True
    else:
        clip, speed, loop = 'initial', 3, True
    frame, state, timer, cue_id = 0, 0, 0, 0
    for tick in range(cs['frames']):
        for cue in cs['actor_cues']:
            if cue['channel'] == 1 and tick > cue['start'] and tick <= cue['end']:
                cue_id = int(cue['id'], 0)
        # Five viewers decrement the shared timer in actor-list order.
        check_timer = max(0, timer - (4 if kind == "ganon" else 5))
        timer = max(0, timer - 5)
        end = lengths[clip] - 1
        finished = not loop and frame == end
        frame = (frame + speed) % lengths[clip] if loop else min(end, frame + speed)
        target, target_loop, morph = clip, loop, 0
        if kind in ('ganon', 'horse_ganon'):
            if cue_id == 2 and check_timer == 0:
                target = prefix + 'IdleAnim' if kind == 'ganon' else 'gHorseGanonIdleAnim'
                target_loop = True
            elif cue_id == 1:
                timer = 100
                target = prefix + 'RearAnim' if kind == 'ganon' else 'gHorseGanonRearingAnim'
                target_loop = True
            elif kind == 'ganon':
                if state == 0 and cue_id == 4:
                    target, target_loop, state, morph = prefix + 'LookSidewaysStartAnim', False, 1, 5
                elif state == 1 and finished:
                    target, target_loop, state, morph = prefix + 'LookSidewaysLoopAnim', True, 2, 5
                elif state == 2 and cue_id == 5:
                    target, target_loop, state, morph = prefix + 'MagicChargeUpStartAnim', False, 3, 5
                elif state == 3 and finished:
                    target, target_loop, state, morph = prefix + 'MagicChargeUpLoopAnim', True, 4, 5
        if target != clip:
            clip, frame, loop = target, 0, target_loop
        yield clip, frame, morph


def write_track(path, frames):
    """CVA1: vertex count, unique pose count, ticks, tick->pose, Q6 xyz."""
    unique, lookup, indices = [], {}, []
    vertices = None
    for points in frames:
        if vertices is None:
            vertices = len(points)
        if len(points) != vertices:
            raise ValueError('Animation topology changed')
        values = [round(v * 64) for point in points for v in point]
        if any(v < -32768 or v > 32767 for v in values):
            raise ValueError('Animation exceeds Q6 coordinate range')
        packed = struct.pack('>%dh' % len(values), *values)
        if packed not in lookup:
            lookup[packed] = len(unique)
            unique.append(packed)
        indices.append(lookup[packed])
    data = struct.pack('>4sIII', b'CVA1', vertices, len(unique), len(indices))
    data += struct.pack('>%dH' % len(indices), *indices) + b''.join(unique)
    path.write_bytes(data)
    print('  motion: %s, %d poses, %d bytes' % (path.name, len(unique), len(data)))
