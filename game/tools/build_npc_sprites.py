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
HERO_HEIGHT = 90    # story heroes: ~1.4x linear, 2x pixels (human 2026-10-04)
MAX_POSES = 8       # per clip, sampled evenly over its ticks (cart budget)
SUPER = 2           # supersample factor
GENERIC_POSES = 4   # Complete scene clip libraries must fit, not just idle.
GENERIC_HEIGHT = 32
# Approved size cuts (Astra 2026-10-13, tools/heap_peak_model.py): Hyrule
# Field's Zelda escape/flashback layers hold child Zelda and Impa with the
# Field stream; the child night layer's running man needs a smaller block;
# Dodongo's Cavern's two Lizalfos skeletons are half its sprite heap. Fewer
# poses keep every clip and its source timing (tick -> pose).
GENERIC_POSE_CAP = {'object_zl4': 2, 'object_im': 2, 'object_mm': 2, 'object_zf': 3}


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
    pal += [0] * (45 - len(pal))  # Pillow can return fewer entries for tiny stock icons.
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


def bake_generic(oot, rom_dir, work, out, core, only_objects=None,
                 extra_sources=(), extra_objects=(), extra_animation_objects=None):
    """Decomp NPC objects (oot_core_import GENERIC_NPC_SOURCES): every Skeleton,
    every Animation the actor sources name. Intermediate G<oid3><nn>.SPR
    plus {object, limbs, animation symbol, clip file, skeleton symbol} rows;
    build_sprite_keys packs complete SPR2 libraries after object linking."""
    import xml.etree.ElementTree as ET
    import build_actor_model as actor
    import build_core_skins as skins
    imp = skins.load_importer()
    import field_enemy_sources
    import water_temple_sources
    import child_route_npcs
    import child_route_shops
    import ranch_sources
    import child_common_npcs
    import child_reward_npcs
    import child_mask_sources
    import child_minigame_sources
    import child_fairy_sources
    import child_route_props
    import child_legend_sources
    import dodongo_enemy_sources
    import owl_sources
    import courtyard_sources
    required_objects = (field_enemy_sources.OBJECTS + water_temple_sources.SPRITE_OBJECTS +
                        child_route_npcs.OBJECTS + dodongo_enemy_sources.SPRITE_OBJECTS +
                        child_route_shops.SPRITE_OBJECTS + owl_sources.OBJECTS + child_common_npcs.OBJECTS + child_reward_npcs.OBJECTS + child_mask_sources.OBJECTS + child_minigame_sources.SPRITE_OBJECTS + child_fairy_sources.OBJECTS + courtyard_sources.OBJECTS + child_route_props.SPRITE_OBJECTS + tuple(extra_objects))
    _enums, sym_ids = imp.object_ids(oot)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    text = ''.join((oot / src).read_text(encoding='utf-8', errors='replace')
                   for src in [s for _, s in imp.GENERIC_NPC_SOURCES] + field_enemy_sources.SOURCES +
                   water_temple_sources.SPRITE_SOURCES + list(dodongo_enemy_sources.SPRITE_SOURCES) +
                   [child_route_shops.KEEPER_SOURCE] + list(child_legend_sources.SOURCES) + list(extra_sources))
    wanted = sorted(name for name in set(imp.OBJECTS) | set(extra_objects)
                    if name in (imp.SPRITE_OBJECTS | set(extra_objects)) and name.upper() in text.upper())
    if only_objects is not None:
        missing = set(only_objects) - set(wanted)
        if missing:
            raise ValueError(f'No source sprite object: {sorted(missing)}')
        wanted = [name for name in wanted if name in only_objects]
    rows, files = [], 0
    for name in wanted:
        if name in ranch_sources.OBJECTS or name in child_common_npcs.HY_OBJECTS:
            continue  # Source Skin geometry is decoded offline by the horse baker below.
        oid = sym_ids[name]
        xml_path = oot / 'assets' / 'xml' / 'objects' / (name + '.xml')
        if not xml_path.exists():
            continue
        root = ET.parse(xml_path)
        data = link.read_object(oot, name, rom_dir)
        animation_objects = [child_route_npcs.ANIMATION_OBJECTS.get(name, name)]
        animation_objects += list(child_route_shops.ANIMATION_OBJECTS.get(name, ()))
        animation_objects += list(child_reward_npcs.ANIMATION_OBJECTS.get(name, ()))
        animation_objects += list((extra_animation_objects or {}).get(name, ()))
        anims, shop_anims = [], set()
        for animation_object in dict.fromkeys(animation_objects):
            animation_root = root if animation_object == name else ET.parse(
                oot / 'assets' / 'xml' / 'objects' / (animation_object + '.xml'))
            animation_data = data if animation_object == name else link.read_object(oot, animation_object, rom_dir)
            anims.extend((a.attrib['Name'], int(a.attrib['Offset'], 16), animation_data)
                         for a in animation_root.iter('Animation')
                         if not a.attrib.get('Offset', '.').startswith('.') and a.attrib['Name'] in text)
            if animation_object in child_route_shops.ANIMATION_OBJECTS.get(name, ()):
                shop_anims.update(a.attrib['Name'] for a in animation_root.iter('Animation'))
        skels = [k for k in root.iter('Skeleton') if not k.attrib.get('Offset', '.').startswith('.')]
        if name in child_common_npcs.OBJECTS:
            skels = [k for k in skels if k.attrib['Name'] in text]
        variants = ((0, 1) if name in ('object_skb', 'object_tite', 'object_firefly', 'object_owl', 'object_st', 'object_dog', 'object_ssh', 'object_cs', 'object_mm', 'object_skj', 'object_sd', 'object_ossan', 'object_bg') else
                    (0, 1, 2, 3, 4) if name == 'object_po_field' else
                    (0, 1, 2, 3) if name == 'object_daiku' else (0,))
        for n, skel, variant in [(n, skel, v) for n, skel in enumerate(skels[:4]) for v in variants]:
            skel_off = int(skel.attrib['Offset'], 16)
            try:
                bin_path = work / ('G%03X%X_%d.BIN' % (oid, n, variant))
                owners, locals_, limbs, count = full_skin(oot, rom_dir, name, data, skel_off,
                                                          xml_path, keep, bin_path, variant=variant)
                faces, _, _ = read_model(bin_path, None)
                if name == 'object_gndd':
                    # Source EnGanonMant is visual cloth only. Bake a hanging
                    # cape with its original texture and each pose's neck.
                    cape = Image.open(oot / 'extracted/ntsc-1.2/assets/overlays/ovl_En_Ganon_Mant/gMantTex.rgba16.png').convert('RGBA')
                    pixels = [[tuple(cape.getpixel((x,y))[:3]) if cape.getpixel((x,y))[3] else None
                               for x in range(cape.width)] for y in range(cape.height)]
                    first_cape = len(owners)
                    faces += [((first_cape,first_cape+1,first_cape+2),cape.width,cape.height,pixels,1),
                              ((first_cape,first_cape+2,first_cape+3),cape.width,cape.height,pixels,2)]
            except Exception as exc:
                if name in required_objects:
                    raise ValueError(f'{name} variant {variant}: required enemy sprite failed') from exc
                print('  sprite: %s %s left out: %r' % (name, skel.attrib.get('Name'), exc))
                continue
            bind = max(math.dist((0, 0, 0), l) for l in locals_) * .01 + 1
            clips = []
            mine = anims
            if len(skels) > 1:      # gCowBodySkel -> gCowBody*Anim, gCowTailSkel -> gCowTail*
                stem = skel.attrib['Name'].replace('Skel', '').replace('Skeleton', '')
                mine = [a for a in anims if a[0].startswith(stem)] or anims
            if name == 'object_owl':
                mine = [a for a in anims if a[0] in owl_sources.ANIMATIONS[skel.attrib['Name']]]
            if name == 'object_gndd':
                mine = [a for a in anims if a[0] in courtyard_sources.VIEWER_ANIMS]
            for anim_name, off, animation_data in mine:
                try:
                    frames = struct.unpack_from('>h', animation_data, off)[0]
                    poses = []
                    for f in range(frames):
                        _, rt, rot = actor.read_animation(animation_data, off, count, f)
                        if name == 'object_zl4' and anim_name in courtyard_sources.moving_animations(oot):
                            rt = (0,rt[1],0) # same offline XZ anchors move source actor
                        if name == 'object_owl' and variant:
                            # Source EnOwl_OverrideLimbDraw: limb 3 head flip.
                            rot = list(rot)
                            rot[2] = (rot[2][0] + 0x8000, rot[2][1], rot[2][2])
                        if name == 'object_ei':
                            rt = (rt[0], rt[1], rt[2] + 2000) # source root OverrideLimbDraw
                        if name == 'object_firefly':
                            rt = (rt[0], rt[1] + 2300, rt[2]) # source root OverrideLimbDraw
                        if name == 'object_mu':
                            rt = (rt[0], rt[1], rt[2] - 560) # source dancing-couple model offset
                        if name == 'object_peehat':
                            rot = list(rot)
                            rot[3] = (-round(f * 65536 / max(frames, 1)), rot[3][1], rot[3][2])
                        pose = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rot, rt)}
                        poses.append([tuple(v * .01 for v in (lc if name == 'object_po_field' and variant >= 2
                                                              else link.transform(*pose[ow], lc)))
                                      for ow, lc in zip(owners, locals_)])
                        if name == 'object_gndd':
                            nx,ny,nz=(v*.01 for v in pose[link.HEAD_LIMB][1])
                            poses[-1] += [(nx-15,ny-7,nz-8),(nx+15,ny-7,nz-8),
                                          (nx+25,ny-117,nz-23),(nx-25,ny-117,nz-23)]
                        if name == 'object_st' and variant:
                            s, c = math.sin(math.radians(-80)), math.cos(math.radians(-80))
                            poses[-1] = [(x, y*c-(z+2)*s, y*s+(z+2)*c) for x, y, z in poses[-1]]
                except Exception:
                    if name in required_objects:
                        raise
                    continue
                if not poses:
                    continue
                # An animation for another skeleton reads garbage joints.
                reach = max(math.hypot(p[0], p[2]) for pose in poses for p in pose)
                if reach > 6 * bind + 100:
                    continue
                clips.append((anim_name, off, poses))
            if not clips:
                if name in required_objects:
                    raise ValueError(f'{name} {skel.attrib["Name"]}: required sprite has no animation clips')
                continue
            cap = GENERIC_POSE_CAP.get(name, GENERIC_POSES)
            layout = layout_of([sample(c[2], list(range(len(c[2]))), cap)[0] for c in clips],
                               GENERIC_HEIGHT)
            for anim_name, off, poses in clips:
                dest = out / ('G%03X%02X.SPR' % (oid, files % 256))
                write_sprite(faces, poses, list(range(len(poses))), dest,
                             work / (dest.stem + '_sprites.png'), layout, cap)
                # Shared bodies use different compacted animation objects.
                # Reserve variant8 for keeper clips, avoiding key collisions
                # with a normal Goron's same-offset animation header.
                key_variant = variant | (9 if name == "object_oF1d_map" and anim_name.startswith("object_gm_") else 8 if anim_name in shop_anims else 0)
                rows.append((oid, count, anim_name, files % 256, skel.attrib['Name'], key_variant))
                files += 1
        if name == 'object_owl':
            # Source shortcut cue 2 can select Perch on the flying clock.
            # Share the perching pixels under that source identity too.
            for row in list(rows):
                if row[0] == oid and row[4] == 'gOwlPerchingSkel':
                    rows.append((oid, 21, row[2], row[3], 'gOwlFlyingSkel', row[5]))
    for name, skel_name, anim_name, display_lists in child_route_npcs.STATIC_CLIPS:
        if only_objects is not None and name not in only_objects:
            continue
        oid = sym_ids[name]
        data = link.read_object(oot, name, rom_dir)
        xml_path = oot / 'assets/xml/objects' / (name + '.xml')
        bin_path = work / ('G%03X_%s.BIN' % (oid, anim_name))
        _, locals_ = static_skin(name, data, xml_path, keep, display_lists, bin_path)
        faces, _, _ = read_model(bin_path, None)
        poses = [[tuple(v * .01 for v in lc) for lc in locals_]]
        dest = out / ('G%03X%02X.SPR' % (oid, files % 256))
        write_sprite(faces, poses, [0], dest, work / (dest.stem + '_sprites.png'),
                     layout_of([poses], GENERIC_HEIGHT), GENERIC_POSES)
        rows.append((oid, 0, anim_name, files % 256, skel_name, 0))
        files += 1
    # Skeleton-less actors (Spikes): one pose per source draw state. The key
    # pair is two of the object's display-list symbols; variants select the
    # display lists the source Draw would submit.
    static_sprites = dict(water_temple_sources.STATIC_SPRITES)
    static_sprites.update(dodongo_enemy_sources.STATIC_SPRITES)
    static_sprites.update(child_route_props.STATIC_SPRITES)
    static_sprites.update(child_mask_sources.STATIC_SPRITES)
    for name, (skel_name, anim_name, states) in static_sprites.items():
        if only_objects is not None and name not in only_objects:
            continue
        oid = sym_ids[name]
        data = link.read_object(oot, name, rom_dir)
        xml_path = oot / 'assets' / 'xml' / 'objects' / (name + '.xml')
        baked = []
        for variant, lists_named in enumerate(states):
            bin_path = work / ('G%03XS_%d.BIN' % (oid, variant))
            owners, locals_ = static_skin(name, data, xml_path, keep, lists_named, bin_path)
            faces, _, _ = read_model(bin_path, None)
            baked.append((faces, [[tuple(v * .01 for v in lc) for lc in locals_]]))
        # One cel size and texel for every state: one VDP1 slot per archive.
        layout = layout_of([poses for _, poses in baked], GENERIC_HEIGHT)
        for variant, (faces, poses) in enumerate(baked):
            dest = out / ('G%03X%02X.SPR' % (oid, files % 256))
            write_sprite(faces, poses, [0], dest, work / (dest.stem + '_sprites.png'),
                         layout, GENERIC_POSES)
            rows.append((oid, 0, anim_name, files % 256, skel_name, variant))
            files += 1
    # ROM offsets are only for offline posing. The imported object is compacted
    # and linked again; make resolves these names AFTER linking the new blobs.
    import json
    if set(child_route_shops.STOCK_OBJECTS) <= imp.SPRITE_OBJECTS:
        from build_shop_sprites import bake as bake_stock
        rows += bake_stock(oot, rom_dir, work, out, files, only_objects)
    if any(name == 'ACTOR_EN_BDFIRE' for name, _ in imp.GENERIC_NPC_SOURCES):
        # This source object also contains the exempt boss's real skeleton.
        # It must never enter SPRITE_OBJECTS or the skeletal NPC bake loop.
        from build_dodongo_fire_sprites import bake as bake_bdfire
        rows += bake_bdfire(oot, rom_dir, work, out, len(rows), only_objects)
    if set(ranch_sources.OBJECTS) <= imp.SPRITE_OBJECTS:
        from build_ranch_sprites import bake as bake_horses
        rows += bake_horses(oot, rom_dir, work, out, len(rows), only_objects)
    if set(child_common_npcs.HY_OBJECTS) <= imp.SPRITE_OBJECTS:
        from build_child_common_sprites import bake as bake_hylians
        rows += bake_hylians(oot, rom_dir, work, out, len(rows), only_objects)
    if any(a == 'ACTOR_EN_STH' for a, _ in imp.GENERIC_NPC_SOURCES):
        from build_child_reward_sprites import bake as bake_token_family
        rows += bake_token_family(oot, rom_dir, work, out, len(rows), only_objects)
    if 'object_god_lgt' in imp.SPRITE_OBJECTS:
        from build_child_legend_sprites import bake as bake_gods
        rows += bake_gods(oot, rom_dir, work, out, len(rows), only_objects)
    (core / 'generic_sprites.json').write_text(json.dumps(rows) + '\n')
    print('generic sprites: %d sheets' % len(rows))


def static_skin(obj, data, xml_path, keep, display_lists, bin_path, prim=(255, 255, 255, 255)):
    """Faces of whole-object display lists drawn with the actor matrix only."""
    import xml.etree.ElementTree as ET
    root = ET.parse(xml_path)
    named = {e.attrib['Name']: int(e.attrib['Offset'], 16) for e in root.iter()
             if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}
    link.HEAD_LIMB, link.LIMB_NONE = -1, 0xFF
    lists = link.LimbLists(b'', b'')
    enddl = struct.pack('>II', 0xDF000000, 0)
    # Segment 7 is the func_8002EBCC/ED80 reflection setup list: no geometry.
    lists.segments = {6: data, 4: keep, 7: enddl, 8: enddl, 9: enddl, 10: enddl, 11: enddl, 12: enddl, 13: enddl}
    lists.matrix_limbs = [0]
    faces = []
    lists.prim = prim
    if obj == 'object_efc_star_field':
        lists.prim = (255, 155, 55, 255)  # source EnFireRock_Draw
    for name in display_lists:
        lists.current_limb = 0
        start = len(lists.faces)
        lists.walk(0x06000000 | named[name])
        for original in lists.faces[start:]:
            face = dict(original)
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['limb'] = 0
            face['full_texture'] = True
            faces.append(face)
    if not faces:
        raise ValueError(f'{obj}: no faces in {display_lists}')
    link.apply_primitive_colour(faces)
    faces = link.scale_faces(faces, 0.01)
    _, _, owners, locals_ = link.write_model(faces, bin_path, skinned=True, character=False)
    return owners, locals_


def full_skin(oot, rom_dir, obj, data, skel_off, xml_path, keep, bin_path, variant=0, custom=None):
    """build_core_skins.skin_object faces with FULL textures (sprite source)."""
    import xml.etree.ElementTree as ET
    import build_actor_model as actor
    if obj == 'object_mu':
        from build_child_common_sprites import HylianLists
        recipe = dict(obj=obj, variant=0, colour8=(0,50,160,0), colour9=(255,255,255,0))
        custom = dict(walker=lambda: HylianLists(recipe))
    root = ET.parse(xml_path)
    names = {int(e.attrib['Offset'], 16): e.attrib['Name'] for e in root.iter()
             if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}
    table, count = actor.read_skeleton(data, skel_off)
    limbs, addresses = actor.read_limbs(data, table, count)
    head = next((i for i, a in enumerate(addresses) if 'Head' in names.get(a & 0xFFFFFF, '')), None)
    link.HEAD_LIMB, link.LIMB_NONE = (head if head is not None else -1), 0xFF
    placed = link.walk_skeleton(limbs, [(0, 0, 0)] * count, (0, 0, 0))
    poses = {i: (m, o) for i, m, o, _ in placed}
    lists = custom['walker']() if custom and 'walker' in custom else link.LimbLists(b'', b'')
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
    named = {v: k for k, v in names.items()}
    if custom:
        lists.segments.update(custom.get('segments', {}))
    if obj == 'object_ei':
        lists.segments[8] = enddl # source ACTOR_SETUP_OPA_DL material commands
    if obj == 'object_ts':
        lists.segments[8] = data[named['object_ts_Tex_000970']:]
    if obj == 'object_bg' and variant:
        lists.segments[8] = data[named['gBowlingGirlEyeClosedTex']:]
    if obj == 'object_mm':
        lists.segments[8] = data[named['gRunningManMouthClosedTex']:]
    if obj == 'object_ssh':
        lists.segments[8] = data[named['object_ssh_Tex_0007E0']:]
    if obj == 'object_zf':
        # Source Draw installs texture/setup command lists, not face pixels.
        lists.segments[7] = lists.segments[8] = lists.segments[9] = enddl
    if obj == 'object_tite':
        textures = ('object_tite_Tex_001300', 'object_tite_Tex_001700', 'object_tite_Tex_001900') if variant else (
                    'object_tite_Tex_001B00', 'object_tite_Tex_001F00', 'object_tite_Tex_002100')
        for segment, texture in zip((8, 9, 10), textures):
            lists.segments[segment] = data[named[texture]:]
    if obj == 'object_po_field':
        # These are generated material/display-list segments, not face textures.
        lists.segments.update({8: enddl, 9: enddl, 10: enddl, 12: enddl})
        if variant >= 3:
            tex = 'gBigPoeSoulTex' if variant == 4 else 'gPoeFieldSoulTex'
            lists.segments[9] = data[named[tex]:]
    if obj == 'object_firefly':
        # Source Draw env alpha: 255 normal body lerps to TEXEL1 (gKeese*),
        # 0 fire body keeps TEXEL0 (gFireKeese*). Ice Keese use the normal body.
        lists.env_alpha = 0 if variant else 255
    if obj == 'object_du':
        # Darunia's nose is a third material segment, unlike most NPCs.
        lists.segments[10] = data[first('NoseSerious', 'Nose'):]
    if obj == 'object_dy_obj':
        lists.segments[9] = lists.segments[8]
        lists.segments[10] = data[named['gGreatFairyMouthClosedTex']:]
    if obj == 'object_zl4':
        lists.segments[9] = lists.segments[8]
        lists.segments[10] = data[first('MouthNeutral','Mouth'):]
    if obj in ('object_im','object_gndd'):
        lists.segments[9] = lists.segments[8]
    shop_head = None
    if obj == 'object_km1':
        # EnOssan's Kokiri body switches segment 6 for its separate head.
        shop_head = link.read_object(oot, 'object_masterkokirihead', rom_dir)
        head_xml = ET.parse(oot / 'assets/xml/objects/object_masterkokirihead.xml')
        head_names = {e.attrib['Name']: int(e.attrib['Offset'], 16) for e in head_xml.iter()
                      if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}
        lists.segments[8] = lists.segments[9] = lists.segments[12] = enddl
        lists.segments[10] = shop_head[head_names['gKokiriShopkeeperEyeDefaultTex']:]
    lists.matrix_limbs = [i for i, _, _, d in placed if d]
    faces = []
    for i, _, _, display in placed:
        if custom and hasattr(lists, 'material'):
            lists.material = (255, 255, 255, 255)
        if obj == 'object_ossan' and variant and i == 7:
            display = 0x06000000 | named['gObjectOssanEnSyatekiManDL_007E28']
        if obj == 'object_hs' and i in (9, 10, 12):
            continue  # Source carpenter son's alternate body parts are hidden.
        if custom and 'head_offset' in custom and i == 14:
            lists.segments[6] = custom['head_data']
            display = 0x06000000 | custom['head_offset']
        if shop_head is not None:
            lists.segments[6] = shop_head if i == 14 else data
            if i == 14:
                display = 0x06000000 | head_names['gKokiriShopkeeperHeadDL']
        if obj == 'object_skb' and variant == 1 and i in (10, 11):
            continue
        if obj == 'object_ssh' and variant and i in (3,4,7):
            display = 0x06000000 | named[{3:'object_ssh_DL_0046C0',4:'object_ssh_DL_004080',7:'object_ssh_DL_004DE8'}[i]]
        if obj == 'object_st' and variant:
            gold = {23:'004788', 8:'0046F0', 14:'004658', 11:'0045C0', 26:'004820',
                    20:'0048B8', 17:'004950', 29:'0049E8', 5:'003FB0', 4:'0043D8'}
            if i+1 in gold: display = 0x06000000 | named['object_st_DL_' + gold[i+1]]
        if obj == 'object_po_field':
            if variant == 1 and i in (0, 7, 8):
                display = 0x06000000 | named[{0: 'gBigPoeFaceDL', 7: 'gBigPoeCloakDL', 8: 'gBigPoeBodyDL'}[i]]
            if variant == 2:
                if i != 6:
                    continue
                display = 0x06000000 | named['gPoeFieldLanternDL']
            if variant >= 3:
                if i != 0:
                    continue
                display = 0x06000000 | named['gPoeFieldSoulDL']
        # Source PostLimbDraw: a normal-body Keese draws gKeeseEyesDL on the
        # one-based KEESE_LIMB_HEAD (27) matrix; fire variant 1 has none.
        eyes = obj == 'object_firefly' and variant == 0 and i == 26
        if not display and not eyes:
            continue
        lists.prim = (255, 255, 255, 255)
        lists.current_limb = i
        start = len(lists.faces)
        if display:
            lists.walk(display)
        if custom:
            for extra in custom.get('extra_lists', {}).get(i, ()):
                lists.walk(extra)
        if obj == 'object_tk' and i == 13:
            lists.walk(0x06000000 | named['gDampeShovelDL'])
        if custom and custom.get('bag') and i == 7:
            lists.walk(0x06000000 | named['gHylianMan2BagDL'])
        if obj == 'object_po_field' and i == 6:
            lists.walk(0x06000000 | named['gPoeFieldLanternTopDL'])
        if eyes:
            lists.walk(0x06000000 | named['gKeeseEyesDL'])
        if obj == 'object_daiku' and i == 14:
            # Source PostLimbDraw selects one of four carpenter heads.
            head_name = ('object_daiku_DL_005BD0', 'object_daiku_DL_005AC0',
                         'object_daiku_DL_005990', 'object_daiku_DL_005880')[variant]
            lists.walk(0x06000000 | named[head_name])
        if variant and obj in ('object_cs','object_mm','object_skj','object_sd'):
            from build_child_mask_sprites import attachment
            lists.faces.extend(attachment(oot, rom_dir, obj, i, keep))
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
    if obj == 'object_dog':
        for face in faces:
            face['prim'] = ((150,100,50,255) if variant else (255,255,200,255))
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
            hero = not name.startswith('OWL')
            write_sprite(faces, poses, order, args.out / (name + '.SPR'),
                         args.work / (name + '_sprites.png'),
                         layout_of([poses], HERO_HEIGHT) if hero else None)
        return
    for model in [] if args.generic_only else args.model if args.model is not None else list(range(npcs.SHOPKEEPER + 1)) + [19, 20, 21, 22]:
        bake(args.oot, args.rom_dir, args.work, args.out, model)   # C NPCs (not Saria clips)
    core = root / 'build/oot-core'
    if (args.generic or args.generic_only) and core.exists():
        bake_generic(args.oot, args.rom_dir, args.work, args.out, core)


if __name__ == '__main__':
    main()
