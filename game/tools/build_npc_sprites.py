"""Bake NPCs into multi-direction 2D sprite cels (Saturn sprite impostors).

Source: build_npc_models.build(full=True) -> SPR<nn>.BIN/.ANM, the NPC's real
skeleton, animation and FULL textures (sprites have no face-only rule: a
texture is just baked pixels, same runtime cost). Every animation pose is
rendered from 5 directions (front, front-right, right, back-right, back);
the other 3 are the runtime's horizontal flip. Orthographic, z-buffered,
textures mapped exactly as VDP1 maps a KFR1 tile (A,B,C,C quad). One shared
15-colour palette per NPC, 4bpp cels.

Output NPC<nn>.SPR (big-endian), read by src/npc_sprite.c:
  0x00 'SPR1'  0x04 u16 width  0x06 u16 height  0x08 u16 dirs  0x0A u16 poses
  0x0C u16 ticks  0x0E s16 centre_y (Q4 world units above the actor origin)
  0x10 u16 texel (Q8 world units per texel)  0x12 s16 focus_y (world units)
  0x14 32 B CLUT (RGB555, entry 0 transparent)
  0x34 u16 tick->pose[ticks], padded to 4
  then cels[pose][dir], width*height/2 bytes each (4bpp, high nibble first).
Direction d covers phi = d*45 degrees, phi = angle of the camera seen from
the actor's local frame (0 = camera in front), see npc_sprite.c.
"""
import argparse
import math
from pathlib import Path
import struct

from PIL import Image

import build_npc_models as npcs
import build_link_model as link

DIRS = 5
TEXEL_MIN = 0.75    # world units per texel (small NPCs)
MAX_HEIGHT = 64     # texels; bigger NPCs get a coarser texel
MAX_POSES = 8       # per clip, sampled evenly over its ticks (cart budget)
SUPER = 2           # supersample factor
GENERIC_POSES = 6   # decomp NPCs: many clips each, so fewer poses and texels
GENERIC_HEIGHT = 56


def rgb555(c):
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)


def read_model(bin_path, anm_path):
    data = bin_path.read_bytes()
    (magic, _, nverts, nfaces, vo, fo, to, tbytes, _, *_rest) = struct.unpack_from('>9I3i4I', data)
    faces = []
    for i in range(nfaces):
        a, b, c, d, pix, clut, size, flags = struct.unpack_from('>4HIIHH', data, fo + 20 * i)
        w, h = (size >> 8) * 8, size & 255
        palette = [struct.unpack_from('>H', data, to + clut + 2 * k)[0] for k in range(16)]
        texels = []
        for y in range(h):
            row = []
            for x in range(w):
                byte = data[to + pix + (y * w + x) // 2]
                index = byte >> 4 if x % 2 == 0 else byte & 15
                colour = palette[index]
                row.append(None if index == 0 or colour == 0 else rgb555(colour))
            texels.append(row)
        faces.append(((a, b, c), w, h, texels, 0 if d == c else 1))
        if d != c:
            faces.append(((a, c, d), w, h, texels, 2))
    if anm_path is None:
        return faces, None, None
    anm = anm_path.read_bytes()
    _, verts, poses, ticks = struct.unpack_from('>4sIII', anm)
    if verts != nverts:
        raise ValueError('SPR model/animation vertex mismatch')
    order = struct.unpack_from('>%dH' % ticks, anm, 16)
    base = 16 + 2 * ticks
    pose_points = []
    for p in range(poses):
        values = struct.unpack_from('>%dh' % (verts * 3), anm, base + p * verts * 6)
        pose_points.append([tuple(v / 64 for v in values[i * 3:i * 3 + 3]) for i in range(verts)])
    return faces, pose_points, list(order)


def view(points, phi):
    """Camera at local angle phi (atan2(x, z)) -> screen x right, y up, depth
    toward the camera. Same numbers as the SGL draw: x' = x cos + z sin."""
    s, c = math.sin(phi), math.cos(phi)
    out = []
    for x, y, z in points:
        rx = x * c - z * s      # RotY(-phi)
        rz = x * s + z * c
        out.append((-rx, y, rz))
    return out


def render(faces, pts, width, height, centre_y, texel):
    sw, sh = width * SUPER, height * SUPER
    scale = SUPER / texel
    colour = [None] * (sw * sh)
    depth = [-1e9] * (sw * sh)
    proj = [((x * scale) + sw / 2, sh / 2 - (y - centre_y) * scale, z) for x, y, z in pts]
    for (ia, ib, ic), w, h, texels, quad in faces:
        A, B, C = proj[ia], proj[ib], proj[ic]
        det = (B[0] - A[0]) * (C[1] - A[1]) - (C[0] - A[0]) * (B[1] - A[1])
        if abs(det) < 1e-9:
            continue
        x0 = max(0, int(math.floor(min(A[0], B[0], C[0]))))
        x1 = min(sw - 1, int(math.ceil(max(A[0], B[0], C[0]))))
        y0 = max(0, int(math.floor(min(A[1], B[1], C[1]))))
        y1 = min(sh - 1, int(math.ceil(max(A[1], B[1], C[1]))))
        for py in range(y0, y1 + 1):
            fy = py + 0.5
            for px in range(x0, x1 + 1):
                fx = px + 0.5
                s = ((fx - A[0]) * (C[1] - A[1]) - (C[0] - A[0]) * (fy - A[1])) / det
                t = ((B[0] - A[0]) * (fy - A[1]) - (fx - A[0]) * (B[1] - A[1])) / det
                if s < -1e-6 or t < -1e-6 or s + t > 1 + 1e-6:
                    continue
                z = A[2] + s * (B[2] - A[2]) + t * (C[2] - A[2])
                k = py * sw + px
                if z <= depth[k]:
                    continue
                # VDP1 quad A,B,C,D=C: P = A + (1-v)u(B-A) + v(C-A).
                v = min(max(t, 0.0), 1.0)
                u = s / (1 - v) if v < 1 - 1e-6 else 0.0
                if quad == 1:
                    u, v = s + t, t
                elif quad == 2:
                    u, v = s, s + t
                tx = min(w - 1, max(0, int(u * w)))
                ty = min(h - 1, max(0, int(v * h)))
                texel = texels[ty][tx]
                if texel is None:
                    continue
                depth[k] = z
                colour[k] = texel
    img = Image.new('RGBA', (width, height))
    for y in range(height):
        for x in range(width):
            got = [colour[(y * SUPER + j) * sw + x * SUPER + i]
                   for j in range(SUPER) for i in range(SUPER)]
            got = [g for g in got if g]
            if len(got) * 2 >= SUPER * SUPER:
                img.putpixel((x, y), tuple(sum(g[k] for g in got) // len(got) for k in range(3)) + (255,))
    return img


def sample(poses, order, cap=None):
    """At most cap (MAX_POSES) poses, evenly over the clip's ticks."""
    cap = cap or MAX_POSES
    if len(poses) <= cap:
        return poses, order
    ticks = len(order)
    picks = [j * ticks // cap for j in range(cap)]
    return [poses[order[t]] for t in picks], [t * cap // ticks for t in range(ticks)]


def bake(oot, rom_dir, work, out, model):
    npcs.build(oot, rom_dir, work, model, full=True)
    faces, poses, order = read_model(work / ('SPR%02d.BIN' % model), work / ('SPR%02d.ANM' % model))
    write_sprite(faces, poses, order, out / ('NPC%02d.SPR' % model), work / ('NPC%02d_sprites.png' % model))


def layout_of(pose_lists, max_height=MAX_HEIGHT):
    """Cel size/texel/centre covering every pose (one size per skeleton, so
    one VDP1 slot fits all of its animations)."""
    pts = [p for poses in pose_lists for pose in poses for p in pose]
    ys = [p[1] for p in pts]
    radius = max(math.hypot(p[0], p[2]) for p in pts)
    ymin, ymax = min(ys), max(ys)
    texel = max(TEXEL_MIN, (ymax - ymin) / (max_height - 2))
    width = (int(math.ceil(2 * radius / texel)) + 2 + 7) & ~7
    height = int(math.ceil((ymax - ymin) / texel)) + 2
    return width, height, texel, (ymin + ymax) / 2, ymax


def write_sprite(faces, poses, order, dest, preview_path, layout=None, cap=None):
    poses, order = sample(poses, order, cap)
    width, height, texel, centre_y, ymax = layout or layout_of([poses])
    images = [[render(faces, view(pose, d * math.pi / 4), width, height, centre_y, texel)
               for d in range(DIRS)] for pose in poses]
    # One palette: stack every cel, quantize opaque pixels to 15 colours.
    sheet = Image.new('RGB', (width, height * len(images) * DIRS))
    mask = []
    for n, img in enumerate(c for row in images for c in row):
        sheet.paste(img.convert('RGB'), (0, n * height))
        mask.append(img.getchannel('A'))
    quant = sheet.quantize(colors=15, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette()[:45]
    clut = [0] + [(1 << 15) | (pal[i * 3] >> 3) | ((pal[i * 3 + 1] >> 3) << 5) |
                  ((pal[i * 3 + 2] >> 3) << 10) for i in range(15)]
    cels = bytearray()
    for n, alpha in enumerate(mask):
        for y in range(height):
            row = []
            for x in range(width):
                row.append(quant.getpixel((x, n * height + y)) + 1 if alpha.getpixel((x, y)) else 0)
            for x in range(0, width, 2):
                cels.append(row[x] << 4 | row[x + 1])
    focus_y = round(ymax * 0.85)
    data = struct.pack('>4s5HhHh', b'SPR1', width, height, DIRS, len(poses), len(order),
                       round(centre_y * 16), round(texel * 256), focus_y)
    data += struct.pack('>16H', *clut)
    data += struct.pack('>%dH' % len(order), *order) + bytes((-2 * len(order)) % 4)
    data += cels
    dest.write_bytes(data)
    preview = Image.new('RGBA', (width * DIRS, height * len(images)))
    for p, row in enumerate(images):
        for d, img in enumerate(row):
            preview.paste(img, (d * width, p * height))
    preview.save(preview_path)
    print('  sprite: %s %dx%d, %d poses x %d dirs, %d bytes' %
          (dest.name, width, height, len(poses), DIRS, len(data)))


def bake_generic(oot, rom_dir, work, out, core):
    """Decomp NPC objects (oot_core_import GENERIC_NPC_SOURCES): every Skeleton,
    every Animation the actor sources name. G<oid3><nn>.SPR + generic_sprites.h
    { object id, limb count, animation offset, file number } for the host."""
    import xml.etree.ElementTree as ET
    import build_actor_model as actor
    import build_core_skins as skins
    imp = skins.load_importer()
    _enums, sym_ids = imp.object_ids(oot)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    text = ''.join((oot / src).read_text(encoding='utf-8', errors='replace')
                   for _a, src in imp.GENERIC_NPC_SOURCES)
    wanted = sorted(name for name in imp.OBJECTS if name.upper() in text.upper())
    rows, files = [], 0
    for name in wanted:
        oid = sym_ids[name]
        xml_path = oot / 'assets' / 'xml' / 'objects' / (name + '.xml')
        if not xml_path.exists():
            continue
        root = ET.parse(xml_path)
        data = link.read_object(oot, name, rom_dir)
        anims = [(a.attrib['Name'], int(a.attrib['Offset'], 16)) for a in root.iter('Animation')
                 if not a.attrib.get('Offset', '.').startswith('.') and a.attrib['Name'] in text]
        skels = [k for k in root.iter('Skeleton') if not k.attrib.get('Offset', '.').startswith('.')]
        for n, skel in enumerate(skels[:4]):
            skel_off = int(skel.attrib['Offset'], 16)
            try:
                bin_path = work / ('G%03X%X.BIN' % (oid, n))
                owners, locals_, limbs, count = full_skin(oot, rom_dir, name, data, skel_off,
                                                          xml_path, keep, bin_path)
                faces, _, _ = read_model(bin_path, None)
            except Exception as exc:
                print('  sprite: %s %s left out: %r' % (name, skel.attrib.get('Name'), exc))
                continue
            bind = max(math.dist((0, 0, 0), l) for l in locals_) * .01 + 1
            clips = []
            mine = anims
            if len(skels) > 1:      # gCowBodySkel -> gCowBody*Anim, gCowTailSkel -> gCowTail*
                stem = skel.attrib['Name'].replace('Skel', '').replace('Skeleton', '')
                mine = [a for a in anims if a[0].startswith(stem)] or anims
            for anim_name, off in mine:
                try:
                    frames = struct.unpack_from('>h', data, off)[0]
                    poses = []
                    for f in range(frames):
                        _, rt, rot = actor.read_animation(data, off, count, f)
                        pose = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rot, rt)}
                        poses.append([tuple(v * .01 for v in link.transform(*pose[ow], lc))
                                      for ow, lc in zip(owners, locals_)])
                except Exception:
                    continue
                if not poses:
                    continue
                # An animation for another skeleton reads garbage joints.
                reach = max(math.hypot(p[0], p[2]) for pose in poses for p in pose)
                if reach > 6 * bind + 100:
                    continue
                clips.append((anim_name, off, poses))
            if not clips:
                continue
            layout = layout_of([sample(c[2], list(range(len(c[2]))), GENERIC_POSES)[0] for c in clips],
                               GENERIC_HEIGHT)
            for anim_name, off, poses in clips:
                dest = out / ('G%03X%02X.SPR' % (oid, files % 256))
                write_sprite(faces, poses, list(range(len(poses))), dest,
                             work / (dest.stem + '_sprites.png'), layout, GENERIC_POSES)
                rows.append((oid, count, anim_name, files % 256))
                files += 1
    # ROM offsets are only for offline posing. The imported object is compacted
    # and linked again; make resolves these names AFTER linking the new blobs.
    import json
    (core / 'generic_sprites.json').write_text(json.dumps(rows) + '\n')
    print('generic sprites: %d sheets' % len(rows))


def full_skin(oot, rom_dir, obj, data, skel_off, xml_path, keep, bin_path):
    """build_core_skins.skin_object faces with FULL textures (sprite source)."""
    import xml.etree.ElementTree as ET
    import build_actor_model as actor
    root = ET.parse(xml_path)
    names = {int(e.attrib['Offset'], 16): e.attrib['Name'] for e in root.iter()
             if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}
    table, count = actor.read_skeleton(data, skel_off)
    limbs, addresses = actor.read_limbs(data, table, count)
    head = next((i for i, a in enumerate(addresses) if 'Head' in names.get(a & 0xFFFFFF, '')), None)
    link.HEAD_LIMB, link.LIMB_NONE = (head if head is not None else -1), 0xFF
    placed = link.walk_skeleton(limbs, [(0, 0, 0)] * count, (0, 0, 0))
    poses = {i: (m, o) for i, m, o, _ in placed}
    lists = link.LimbLists(b'', b'')
    tex = [(e.attrib['Name'], int(e.attrib['Offset'], 16)) for e in root.iter('Texture')
           if not e.attrib.get('Offset', '.').startswith('.')]

    def first(*keys):
        for key in keys:
            for nm, off in tex:
                if key in nm:
                    return off
        return 0
    enddl = struct.pack('>II', 0xDF000000, 0)
    lists.segments = {6: data, 4: keep, 8: data[first('EyeOpen', 'Eye'):],
                      9: data[first('MouthClosed', 'Mouth'):],
                      10: enddl, 11: enddl, 12: enddl, 13: enddl}
    lists.matrix_limbs = [i for i, _, _, d in placed if d]
    faces = []
    for i, _, _, display in placed:
        if not display:
            continue
        lists.prim = (255, 255, 255, 255)
        lists.current_limb = i
        start = len(lists.faces)
        lists.walk(display)
        for original in lists.faces[start:]:
            face = dict(original)
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['vertices'] = [link.transform(*poses[owner], v[:3]) + tuple(v[3:])
                                for v, owner in zip(face['vertices'], face['vertex_limbs'])]
            face['limb'] = i
            face['full_texture'] = True
            faces.append(face)
    if not faces:
        raise ValueError('no faces')
    link.apply_primitive_colour(faces)
    faces = link.scale_faces(faces, 0.01)
    _, _, owners, locals_ = link.write_model(faces, bin_path, skinned=True, character=False)
    return owners, locals_, limbs, count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=Path)
    root = Path(__file__).resolve().parents[1]
    ap.add_argument('--out', type=Path, default=root / 'build/generated/npcs')
    ap.add_argument('--work', type=Path, default=root / 'build/generated/sprites')
    ap.add_argument('--model', type=int, action='append')
    ap.add_argument('--generic', action='store_true', help='also decomp NPC objects (OOT_CORE)')
    ap.add_argument('--generic-only', action='store_true', help='only decomp NPC objects')
    ap.add_argument('--story-only', action='store_true', help='only cutscene riders, horses and owl')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.story_only:
        for name in ('GANON', 'ZELDA', 'IMPA', 'HZELDA', 'HGANON', 'OWLPERCH', 'OWLFLY'):
            folder = root / 'build/generated' / ('owl' if name.startswith('OWL') else '')
            faces, poses, order = read_model(folder / (name + '.BIN'), folder / (name + '.ANM'))
            write_sprite(faces, poses, order, args.out / (name + '.SPR'),
                         args.work / (name + '_sprites.png'))
        return
    for model in [] if args.generic_only else args.model if args.model is not None else list(range(npcs.SHOPKEEPER + 1)) + [19, 20, 21, 22]:
        bake(args.oot, args.rom_dir, args.work, args.out, model)   # C NPCs (not Saria clips)
    core = root / 'build/oot-core'
    if (args.generic or args.generic_only) and core.exists():
        bake_generic(args.oot, args.rom_dir, args.work, args.out, core)


if __name__ == '__main__':
    main()
