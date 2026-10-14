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


CVQ1_SECTOR = 2048
CVQ1_HEADER = 32


def cvq1_pose_bytes(vertices):
    return (24 + vertices * 3 + 3) & ~3


def quantize_track(path, chunk_poses=32):
    """CVA1 -> CVQ1 in place: every pose keeps its own per-axis range, 8 bits
    per coordinate (max error = range / 510 Q6 units), so a large boss track
    needs no single contiguous block. src/cutscene_actor.c reads it.

      0x00 'CVQ1', u32 vertices, poses, ticks, chunk_poses, pose_bytes,
      0x18 u32 chunk_sectors, first_sector; 0x20 u16 tick->pose[ticks].
      Chunk c (chunk_poses poses) starts at sector first + c * chunk_sectors
      and is zero-padded to it. Pose: s32 base[3], s32 step[3] (FIXED, the
      draw's Q6 * 1024 scale, Y already negated), then u8 q[vertices][3];
      point = base + q * step.
    Returns the worst error in world units."""
    data = path.read_bytes()
    magic, vertices, poses, ticks = struct.unpack_from('>4sIII', data)
    if magic != b'CVA1':
        raise ValueError('%s: not CVA1' % path)
    order = struct.unpack_from('>%dH' % ticks, data, 16)
    at = 16 + ticks * 2
    pose_bytes = cvq1_pose_bytes(vertices)
    chunk_sectors = (chunk_poses * pose_bytes + CVQ1_SECTOR - 1) // CVQ1_SECTOR
    head = struct.pack('>4s7I', b'CVQ1', vertices, poses, ticks, chunk_poses, pose_bytes,
                       chunk_sectors, 0)
    head += struct.pack('>%dH' % ticks, *order)
    first = (len(head) + CVQ1_SECTOR - 1) // CVQ1_SECTOR
    head = head[:28] + struct.pack('>I', first) + head[32:]
    out = bytearray(head + bytes(first * CVQ1_SECTOR - len(head)))
    worst = 0.0
    for c in range(0, poses, chunk_poses):
        chunk = bytearray()
        for p in range(c, min(poses, c + chunk_poses)):
            vals = struct.unpack_from('>%dh' % (vertices * 3), data, at + p * vertices * 6)
            axes = [[vals[i * 3 + a] * (-1 if a == 1 else 1) for i in range(vertices)] for a in range(3)]
            base, step, q = [], [], []
            for w in axes:
                lo, hi = min(w), max(w)
                s = round((hi - lo) * 1024 / 255)
                base.append(lo * 1024)
                step.append(s)
                q.append([0 if not s else min(255, max(0, round((v - lo) * 1024 / s))) for v in w])
                for v, k in zip(w, q[-1]):
                    worst = max(worst, abs(lo * 1024 + k * s - v * 1024) / 65536)
            rec = struct.pack('>6i', *(base + step))
            rec += bytes(q[a][i] for i in range(vertices) for a in range(3))
            chunk += rec + bytes(pose_bytes - len(rec))
        out += chunk + bytes(chunk_sectors * CVQ1_SECTOR - len(chunk))
    path.write_bytes(bytes(out))
    print('  motion: %s CVQ1, %d poses in %d-pose chunks, %d bytes, max error %.3f world units' %
          (path.name, poses, chunk_poses, len(out), worst))
    return worst
