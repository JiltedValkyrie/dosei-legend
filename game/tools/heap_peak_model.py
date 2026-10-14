#!/usr/bin/env python3
"""Offline, conservative model of Jo heap (jo_malloc) peaks during scene loads.

Replays the real allocator (joengine malloc.c compiled through
src/heap_profile.c: zone order, 8-byte headers, 4-byte rounding,
FAST / REUSE_BLOCK / SAME_SIZE behaviours, tail split on reuse, merge and
retry on OOM) over scripted allocation sequences built from the shipped
disc files in build/cd and the generated tables:

  boot residents -> scene_flow_load(prev) -> in-play steady state
  -> scene_flow_load(next) -> scene music swap -> core meshes/tools
  -> in-play transients (area music change, cutscene track, save I/O,
     room-change mesh reload)

for every registered scene, every room, child and adult, with door-graph
predecessors plus the heaviest steady states (warps) and the title path.
Fixed carves (OOC/OOB/OAP scene carve, OOTCORE, NESMSG, low RAM tables)
are not heap and are ignored.

Exit status: 0 = every scenario fits, 1 = a required allocation (or the
sprite 85 % guard) fails somewhere, 2 = inputs missing.

Windows/Linux python, standard library only.
"""
import argparse
import copy
import json
import re
import struct
import sys
from pathlib import Path

GAME = Path(__file__).resolve().parents[1]
HDR = 8                         # jo_memory_block {short zone; unsigned size;}
FAST, REUSE, SAME = 'fast', 'reuse', 'same'
SECTOR_BUFFER = 2048            # jo_fs_open read buffer (__jo_fs_read_buffer_size)
SPRITE_GUARD_PERCENT = 85       # oot_core_host.c CORE_SPRITE_HEAP_PERCENT
CORE_MESHES_MAX = 40
LOAD_CHUNK = 8192               # music.c swap staging
LEVEL_CHUNK = 32768             # music.c envelope tables: 32 KB chunks


def levels_free(h):
    h.free_prefix('music.levels.')


def levels_alloc(h, size, label):
    """music.c levels_alloc: one FAST block per 32 KB (last one short)."""
    try:
        for i, at in enumerate(range(0, size, LEVEL_CHUNK)):
            h.malloc('music.levels.%02d' % i, min(LEVEL_CHUNK, size - at), FAST, label)
    except OutOfMemory:
        levels_free(h)                  # a failed set is freed whole
        raise
MESH_STRUCT = 68                # sizeof(struct actor_mesh) on SH-2
POINT_BYTES, POLYGON_BYTES, ATTR_BYTES = 12, 20, 12
SAVE_IO_BYTES = 8192            # assumption: backup file contents + comment
SDK_SMALL = [32] * 8            # assumption: Jo list nodes / callbacks
SAVE_SCENE_COUNT = 11
SCENE_SPOT00, SCENE_KOKIRI_SHOP = 10, 2
AGE_FLIP_SCENES = (55, 56)      # SCENE_TOKINOMA, SCENE_KENJYANOMA
TOOLS = {'child': ['ITMBOM.SPR', 'ITMCHU.SPR', 'ITMBOO.SPR', 'ITMEXP.SPR'],
         'adult': ['ITMARW.SPR', 'ITMBOM.SPR', 'ITMCHU.SPR', 'ITMHKT.SPR', 'ITMHKC.SPR',
                   'ITMEXP.SPR', 'ITMMAG.SPR']}


def rnd(n):
    return (n + HDR + 3) & ~3


# --------------------------------------------------------------------------
# Allocator replay
# --------------------------------------------------------------------------
class OutOfMemory(Exception):
    pass


class Heap:
    """Blocks per zone: [start, size, free, key]; they tile [0, high)."""

    def __init__(self, zones):
        self.names = [z[0] for z in zones]
        self.caps = [z[1] for z in zones]
        self.blocks = [[] for _ in zones]
        self.high = [0] * len(zones)
        self.total = sum(self.caps)
        self.live = 0
        self.keys = {}          # key -> block (insertion ordered)
        self.reset_peak()

    def clone(self):
        return copy.deepcopy(self)

    def reset_peak(self):
        # Peak = largest live total seen at an allocation from here on (the
        # predecessor's residency counts only while it is still live then).
        self.peak = 0
        self.peak_snapshot = self.snapshot()
        self.peak_label = 'start'
        self.zones_used = set()
        self.largest = (0, '')

    def zone_live(self, z):
        return sum(b[1] for b in self.blocks[z] if not b[2])

    def holes(self, z):
        """Merged free runs inside [0, high) plus the top gap."""
        out, run = [], 0
        for b in self.blocks[z]:
            if b[2]:
                run += b[1]
            else:
                if run:
                    out.append(run)
                run = 0
        out.append(run + self.caps[z] - self.high[z])
        return out

    def snapshot(self):
        snap = []
        for z in range(len(self.caps)):
            live = self.zone_live(z)
            snap.append({'zone': self.names[z], 'capacity': self.caps[z], 'live': live,
                         'free': self.caps[z] - live, 'largest_hole': max(self.holes(z))})
        return snap

    def guard_limit(self):
        """Smallest live total that trips `percent() > 85`."""
        t64 = self.total // 64 or 1
        return ((t64 * (SPRITE_GUARD_PERCENT + 1) + 99) // 100) * 64

    def percent(self):
        # heap_profile.c jo_memory_usage_percent (integer form).
        t64 = self.total // 64 or 1
        return (self.live // 64) * 100 // t64

    # -- SDK + wrapper ---------------------------------------------------
    def _take(self, z, idx, need):
        b = self.blocks[z][idx]
        b[2] = False
        if b[1] - need >= HDR + 4:          # wrapper tail split
            tail = [b[0] + need, b[1] - need, True, None]
            b[1] = need
            self.blocks[z].insert(idx + 1, tail)
        return b

    def _bump(self, z, need):
        if self.high[z] + need > self.caps[z]:
            return None
        b = [self.high[z], need, False, None]
        self.blocks[z].append(b)
        self.high[z] += need
        return b

    def _scan(self, z, need, exact):
        for i, b in enumerate(self.blocks[z]):
            if b[2] and (b[1] == need if exact else b[1] >= need):
                return i
        return None

    def _try(self, need, beh):
        for z in range(len(self.caps)):
            if beh == FAST:
                b = self._bump(z, need)
                if b:
                    return z, b
                i = self._scan(z, need, False)
                if i is not None:
                    return z, self._take(z, i, need)
            elif beh == REUSE:
                i = self._scan(z, need, False)
                if i is not None:
                    return z, self._take(z, i, need)
                b = self._bump(z, need)
                if b:
                    return z, b
            else:                              # SAME_BLOCK_SIZE wrapper
                i = self._scan(z, need, True)
                if i is not None:
                    return z, self._take(z, i, need)
                b = self._bump(z, need)
                if b:
                    return z, b
        return None

    def _reduce(self):
        for z in range(len(self.caps)):
            merged = []
            for b in self.blocks[z]:
                if b[2] and merged and merged[-1][2]:
                    merged[-1][1] += b[1]
                else:
                    merged.append(b)
            if merged and merged[-1][2]:
                self.high[z] = merged[-1][0]
                merged.pop()
            self.blocks[z] = merged

    def malloc(self, key, n, beh, label=''):
        if key in self.keys:
            raise ValueError('duplicate heap key %s' % key)
        need = rnd(n)
        got = self._try(need, beh)
        if not got:
            self._reduce()
            got = self._try(need, beh)
        if not got:
            raise OutOfMemory('%s: %d B (%s)' % (label or key, n, beh))
        z, b = got
        b[3] = key
        self.keys[key] = (z, b)
        self.live += b[1]
        self.zones_used.add(self.names[z])
        if b[1] > self.largest[0]:
            self.largest = (b[1], label or key)
        if self.live > self.peak:
            self.peak = self.live
            self.peak_snapshot = self.snapshot()
            self.peak_label = label or key
        return z

    def free(self, key):
        z, b = self.keys.pop(key)
        self.live -= b[1]
        lst = self.blocks[z]
        if b[0] + b[1] == self.high[z]:
            lst.pop()                          # SDK: retract only this block
            self.high[z] = b[0]
        else:
            b[2] = True
            b[3] = None

    def free_prefix(self, prefix, order=None):
        keys = [k for k in self.keys if k.startswith(prefix)]
        if order == 'sorted':
            keys.sort()
        for k in keys:
            self.free(k)

    def has(self, key):
        return key in self.keys

    def transient(self, n, beh, label):
        key = '~tmp.%s' % label
        self.malloc(key, n, beh, label)
        self.free(key)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
def define(path, name, default=None):
    text = path.read_text(errors='replace') if path.exists() else ''
    m = re.search(r'#\s*define\s+%s\s+(0x[0-9A-Fa-f]+|\d+)u?\b' % name, text)
    if not m:
        if default is None:
            raise SystemExit('missing #define %s in %s' % (name, path))
        return default
    return int(m.group(1), 0)


def make_var(path, name, default):
    m = re.search(r'^%s\s*\??=\s*(\S+)' % name, path.read_text(errors='replace'), re.M)
    return int(m.group(1), 0) if m else default


def digit(v):
    return chr(ord('0') + v) if v < 10 else chr(ord('A') + v - 10)


def scene_file(scene, ext):
    if scene < 36:
        return 'S%s.%s' % (digit(scene), ext)
    return 'Z%s%s.%s' % (digit(scene // 36), digit(scene % 36), ext)


class Inputs:
    def __init__(self, cd, notes):
        self.cd = cd
        self.notes = notes
        self.sizes = {p.name.upper(): p.stat().st_size for p in cd.iterdir() if p.is_file()}
        self.missing = set()
        self.from_budget = set()
        self.ooc_cache = {}
        self.params = {}
        self.layer_masks = {}
        budget = GAME / 'build' / 'oot-core' / 'generic_sprites.budget.json'
        if budget.exists():
            for lib in json.loads(budget.read_text()).get('libraries', []):
                if lib['file'].upper() not in self.sizes:
                    self.sizes[lib['file'].upper()] = lib['bytes']
                    self.from_budget.add(lib['file'].upper())
        gen = GAME / 'build' / 'generated'
        core = GAME / 'build' / 'oot-core'
        src = GAME / 'src'
        self.wram = make_var(GAME / 'makefile', 'JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC', 35840)
        self.bank2 = define(src / 'ram_cart.h', 'RAM_CART_BANK2_BYTES')
        self.fixed_src = define(src / 'ram_cart.h', 'RAM_CART_FIXED_BYTES')   # OOT_CORE branch first
        self.low_heap = define(src / 'ram_low.h', 'RAM_LOW_HEAP_BYTES')
        self.scenecol_addr = make_var(GAME / 'makefile', 'OOT_SCENECOL_ADDR', 0x02710000)
        self.musictrg = define(src / 'music_banks.h', 'MUSICTRG_BYTES')
        self.tile_count = define(gen / 'kokiri_scene.h', 'KOKIRI_TILE_COUNT')
        ls, al = gen / 'link_scene.h', gen / 'adult_link.h'
        self.link = {k: define(ls, 'LINK_' + k) for k in ('POLYGON_COUNT', 'TILE_COUNT', 'PIXEL_BYTES')}
        self.adult = {k: define(al, 'ADULT_LINK_' + k) for k in ('POLYGON_COUNT', 'TILE_COUNT', 'PIXEL_BYTES')}
        self.load_scenes()
        pg = GAME / 'build' / 'player-migration' / 'player_groups.json'
        self.player_groups = json.loads(pg.read_text()) if pg.exists() else None
        # Scene packs (build/oot-core/sources.mk OOT_PACK_<stem>_SCENE/_ACTORS).
        mk = GAME / 'build' / 'oot-core' / 'sources.mk'
        text = mk.read_text() if mk.exists() else ''
        scenes = dict(re.findall(r'^OOT_PACK_(\w+)_SCENE = (\d+)', text, re.M))
        acts = dict(re.findall(r'^OOT_PACK_(\w+)_ACTORS = (.*)$', text, re.M))
        self.pack_actors = {int(v): set(acts.get(k, '').split()) for k, v in scenes.items()}
        if not self.player_groups:
            notes.append('player_groups.json missing: no Player demand groups modelled')
        self.load_sprite_rows(core / 'generic_sprites.h')
        self.load_meshes(core / 'generic_meshes.h')
        self.load_native(gen)
        self.load_cutscenes(gen / 'cutscenes.c')
        lvl = [s for n, s in self.sizes.items() if n.endswith('.LVL')]
        hdr = [s for n, s in self.sizes.items() if re.match(r'M[0-9A-F]{2}\.HDR$', n)]
        if not lvl:
            raise SystemExit('no .LVL music level files in %s' % cd)
        self.lvl_max, self.lvl_min = max(lvl), min(lvl)
        self.hdr_max = max(hdr) if hdr else 0
        self.load_music()

    def size(self, name, required=True):
        s = self.sizes.get(name.upper())
        if s is None and required:
            self.missing.add(name.upper())
        return s

    # -- scene table ---------------------------------------------------
    def load_scenes(self):
        d = (self.cd / 'SCENETAB.BIN').read_bytes()
        self.scenetab = len(d)
        names = {}
        for m in re.finditer(r'#\s*define\s+SCENE_(\w+)\s+(\d+)\b',
                             (GAME / 'build/generated/scene_table.h').read_text()):
            if m.group(1) not in ('COUNT', 'SPAWN_COUNT', 'DOOR_COUNT', 'ENTRANCE_COUNT',
                                  'NEW_GAME_SCENE', 'NEW_GAME_SPAWN', 'GENERIC_FIRST'):
                names.setdefault(int(m.group(2)), m.group(1))
        count = define(GAME / 'build/generated/scene_table.h', 'SCENE_COUNT')
        src = (GAME / 'build/generated/scene_table.c').read_text()
        off = {k: int(v) for k, v in
               re.findall(r'(scene_entries|scene_doors|scene_entrances) = \([^)]*\)\(data \+ (\d+)\)', src)}
        self.scenes = []
        for i in range(count):
            e = d[off['scene_entries'] + i * 26: off['scene_entries'] + i * 26 + 26]
            self.scenes.append({'index': i, 'name': names.get(i, str(i)), 'image': e[0],
                                'panorama': e[1], 'rooms': e[16], 'save_scene': e[21],
                                'seq': e[23], 'oot_scene': e[24]})
        self.preds = {i: set() for i in range(count)}
        self.keep_preds = {i: set() for i in range(count)}
        doors = (off['scene_entrances'] - off['scene_doors']) // 24
        for k in range(doors):
            b = d[off['scene_doors'] + k * 24: off['scene_doors'] + k * 24 + 24]
            if b[14] < count and b[15] < count and b[14] != b[15]:
                self.preds[b[15]].add(b[14])
                if b[17]:
                    self.keep_preds[b[15]].add(b[14])

    # -- core sprite rows / OOC blobs ------------------------------------
    def load_sprite_rows(self, path):
        self.sprite_rows = [(int(o, 16), int(f, 16)) for o, _, f in
                            re.findall(r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+)\s*\}',
                                       path.read_text())]
        self.sprite_rows.append((0xFFF, 0))      # reward atlas row

    def ooc(self, scene):
        if scene not in self.ooc_cache:
            self.ooc_cache[scene] = self._ooc(scene)
        return self.ooc_cache[scene]

    def _ooc(self, scene):
        name = scene_file(scene, 'OOC')
        p = self.cd / name
        if not p.exists():
            self.missing.add(name)
            self.params[scene] = {}
            self.layer_masks[scene] = [0] * 4
            return [], set()
        d = p.read_bytes()
        base = self.scenecol_addr
        w = struct.unpack('>17I', d[:68])
        rooms, layers, lptr, optr, nobj = w[1], w[2], w[3], w[4], w[5]
        objs = [struct.unpack('>H', d[optr - base + 2 * i: optr - base + 2 * i + 2])[0] for i in range(nobj)]
        # Format 5 (oot_scene_blob.h): per-layer object masks; sprites and
        # object slots follow only the destination layer's objects.
        if w[8] == 0x4F4F4305 and w[15] and w[16]:
            self.layer_masks[scene] = list(struct.unpack('>%dI' % w[16], d[w[15] - base: w[15] - base + 4 * w[16]]))
        else:
            self.layer_masks[scene] = [(1 << nobj) - 1] * 4
            self.notes.append('%s: pre-format-5 blob, every layer loads every object' % name)
        actors = set()
        params = self.params.setdefault(scene, {})
        for r in range(rooms * layers):
            at = lptr - base + r * 24
            aptr, n = struct.unpack('>IH', d[at:at + 6])
            if not aptr or not n:
                continue
            for k in range(n):
                ent = d[aptr - base + k * 16: aptr - base + k * 16 + 16]
                aid = struct.unpack('>h', ent[:2])[0] & 0x1FFF
                actors.add(aid)
                params.setdefault(aid, set()).add(struct.unpack('>H', ent[14:16])[0])
        return objs, actors

    def layer_objects(self, scene, layer):
        """objects[] of OotScene_LayerObjects(blob, layer)."""
        objs = self.ooc(scene)[0]
        masks = self.layer_masks[scene]
        mask = masks[layer] if layer < len(masks) else masks[0]
        return [o for k, o in enumerate(objs) if mask >> k & 1]

    def age_layers(self, scene, age):
        """Scene layers an age can load: day/night of its own age plus every
        cutscene layer the scene has (entrance cutscenes of either age)."""
        self.ooc(scene)
        n = len(self.layer_masks[scene])
        return (([0, 1] if age == 'child' else [2, 3]) + list(range(4, n)))

    def load_meshes(self, path):
        self.meshes = []
        self.actor_dirs = {}
        for kind, obj, idx, actor in re.findall(r'\{\s*(\d+),\s*0x([0-9A-Fa-f]+),\s*(\d+),\s*(ACTOR_\w+)\s*\}',
                                                path.read_text()):
            kind, obj, idx = int(kind), int(obj, 16), int(idx)
            if kind > 1:
                continue
            f = ('K%03X.MSH' % idx) if kind == 0 else ('Q%03X%02X.MSH' % (obj, idx))
            self.meshes.append((kind, obj, f, actor))
        self.actor_ids = {}
        for cand in (GAME / 'build/oot-core/decomp/include/tables/actor_table.h',
                     GAME.parents[2] / 'game-decomps/n64/oot/include/tables/actor_table.h'):
            if cand.exists():
                for hexid, name in re.findall(r'/\*\s*0x([0-9A-Fa-f]+)\s*\*/\s*DEFINE_ACTOR\w*\((?:\w+,\s*)?(ACTOR_\w+)',
                                              cand.read_text()):
                    self.actor_ids[name] = int(hexid, 16)
                self.actor_dirs = {int(i, 16): n for i, n in re.findall(
                    r'/\*\s*0x([0-9A-Fa-f]+)\s*\*/\s*DEFINE_ACTOR\s*\((\w+),', cand.read_text())}
                break
        if not self.actor_ids:
            self.notes.append('actor_table.h not found: every generic mesh counted in every generic scene')

    # -- native C tables (legacy scenes) ---------------------------------
    def load_native(self, gen):
        c = (gen / 'kokiri_actors.c').read_text()
        h = (gen / 'kokiri_actors.h').read_text()
        kinds = {k: int(v) for k, v in re.findall(r'#\s*define\s+KOKIRI_NPC_(MIDO|SARIA|CHILD)\s+(\d+)', h)}

        def table(name):
            m = re.search(name + r'\[[^\]]*\]\s*=\s*\{(.*?)\n\};', c, re.S)
            return [[int(x, 0) if re.match(r'-?(0x)?[0-9A-Fa-f]+$', x) else x
                     for x in (t.strip() for t in row.split(','))]
                    for row in re.findall(r'\{([^{}]*)\}', m.group(1))] if m else []
        self.npcs = []
        for row in table('kokiri_npcs'):
            kind = kinds.get(row[5].replace('KOKIRI_NPC_', ''), row[5]) if isinstance(row[5], str) else row[5]
            model = 0 if kind == kinds['MIDO'] else 1 if kind == kinds['SARIA'] else 2 + (row[4] & 255)
            self.npcs.append((row[7], model))
        self.props = [(r[6], r[3], r[4]) for r in table('kokiri_world_props')]     # scene, id, param
        self.chests = [r[6] for r in table('kokiri_chests')]
        navi = (gen / 'navi_npcs.h').read_text()
        self.navi_models = [int(m) for m in re.findall(r'\{[^{}]*,\s*(\d+)\s*\}', navi.split('=', 1)[1])]

    # -- music: which level table can be resident in each scene ----------
    def load_music(self):
        """Per scene: largest LVL (and area HDR) among the sequences it can play.

        Candidates: scene header seq; NA_BGM_* named in the scene's decomp
        asset sources (CS_START_SEQ ...); in the decomp overlay of every actor
        listed in any room/layer; in Player and src/code (ocarina fanfares);
        the C scene_music()/cutscene rules for legacy scenes. A kept theme
        (keep_music) is the predecessor's table, resident through the load."""
        import os
        oot = Path(os.environ.get('DOSEI_OOT', str(GAME.parents[2] / 'game-decomps/n64/oot')))
        seqt = oot / 'include/tables/sequence_table.h'
        gen = GAME / 'build' / 'generated'
        cs = ('CSGANON.LVL', 'CSNAVI.LVL', 'CSDEKU.LVL', 'FAIRYGET.LVL', 'FOREST.LVL',
              'STONE.LVL', 'HOUSE.LVL', 'TITLE.LVL')
        self.cs_lvl = max(self.sizes.get(f, 0) for f in cs) or self.lvl_max
        self.title_lvl = self.sizes.get('TITLE.LVL', self.lvl_max)
        if not seqt.exists():
            self.notes.append('decomp sequence_table.h not found: every scene uses the largest LVL/HDR')
            self.scene_lvl = {e['index']: self.lvl_max for e in self.scenes}
            self.scene_hdr = {e['index']: self.hdr_max for e in self.scenes}
            self.scene_lvl_src = {e['index']: 'global max' for e in self.scenes}
            return
        names = re.findall(r'^\s*DEFINE_SEQUENCE\w*\s*\(\s*\w+\s*,\s*(NA_BGM_\w+)', seqt.read_text(), re.M)
        seq_id = {n: i for i, n in enumerate(names)}
        ids = gen / 'song_ids.h'
        if ids.exists():
            for n, v in re.findall(r'(NA_BGM_\w+)\s*=\s*(\d+)', ids.read_text()):
                if seq_id.get(n, int(v)) != int(v):
                    raise SystemExit('sequence_table.h order disagrees with song_ids.h for %s' % n)
        banks = dict(re.findall(r'music_bank_t\s+music_bank_(\w+)\s*=\s*\{\s*"[^"]*",\s*"([^"]+)"',
                                (GAME / 'src/music_banks.c').read_text()))
        inc = (gen / 'song_routes.inc').read_text()
        routes = {n: banks.get(b) for n, b in re.findall(r'SONG_BANK\((NA_BGM_\w+),\s*(\w+)\)', inc)}
        routes.update({n: None for n in re.findall(r'SONG_CD\((NA_BGM_\w+),', inc)})

        def lvl_of(name):
            if name in routes:
                f = routes[name]
                return (self.sizes.get(f.upper(), 0) if f else 0), 0, f or 'CD-DA'
            i = seq_id.get(name)
            if i is None:
                return 0, 0, ''
            f = 'M%02X.LVL' % i
            return self.sizes.get(f, 0), self.sizes.get('M%02X.HDR' % i, 0), f

        def tokens(paths):
            out = set()
            for p in paths:
                try:
                    out |= set(re.findall(r'NA_BGM_\w+', p.read_text(errors='replace')))
                except OSError:
                    pass
            return out
        glob = tokens(sorted((oot / 'src/code').glob('*.c')) +
                      sorted((oot / 'src/overlays/actors/ovl_player_actor').glob('*.c')))
        sroot = oot / 'extracted' / 'ntsc-1.2' / 'assets' / 'scenes'
        scene_dirs = {d.name.lower(): d for d in sroot.glob('*/*')} if sroot.exists() else {}
        if not scene_dirs:
            self.notes.append('extracted decomp scenes not found: scene cutscene sequences not scanned')
        legacy = {4: ['NA_BGM_SHOP'], 3: ['NA_BGM_DUNGEON', 'NA_BGM_BOSS', 'NA_BGM_BOSS_CLEAR'],
                  2: ['NA_BGM_DUNGEON'], 1: ['NA_BGM_SARIA_THEME'], 10: ['NA_BGM_FIELD_LOGIC', 'NA_BGM_OWL']}
        actor_tokens = {}
        lvl, hdr, src = {}, {}, {}
        for e in self.scenes:
            cand = set(glob)
            if e['seq'] not in (0x7F, 0x01) and e['seq'] < len(names):
                cand.add(names[e['seq']])
            d = scene_dirs.get(e['name'].lower())
            if d:
                cand |= tokens(d.glob('*.c'))
            for a in self.ooc(e['index'])[1]:
                n = self.actor_dirs.get(a)
                if n == 'En_River_Sound':
                    # Only Saria's song / Great Fairy params start a sequence;
                    # GANON_TOWER params only scale the scene's own BGM volume.
                    for prm in self.params[e['index']].get(a, ()):
                        t = prm & 0xFF
                        cand |= {0x0C: {'NA_BGM_SARIA_THEME'}, 0x0D: {'NA_BGM_SARIA_THEME'},
                                 0x13: {'NA_BGM_GREAT_FAIRY'}}.get(t, set())
                    continue
                if a not in actor_tokens:
                    actor_tokens[a] = tokens((oot / 'src/overlays/actors' / ('ovl_' + n)).glob('*.c')) if n else set()
                cand |= actor_tokens[a]
            if e['save_scene'] < SAVE_SCENE_COUNT:
                cand |= set(legacy.get(e['save_scene'], ['NA_BGM_LINK_HOUSE' if e['image'] else 'NA_BGM_KOKIRI']))
                cand |= {'NA_BGM_OCA_FAIRY_GET', 'NA_BGM_SPIRITUAL_STONE', 'NA_BGM_DEKU_TREE_CS', 'NA_BGM_KOKIRI'}
            best = max(((lvl_of(n)[0], n) for n in cand), default=(0, ''))
            lvl[e['index']] = best[0]
            hdr[e['index']] = max((lvl_of(n)[1] for n in cand), default=0)
            src[e['index']] = '%s (%s)' % (best[1], lvl_of(best[1])[2]) if best[1] else 'silence'
        # keep_music only defers scene_music(): the previous table stays through
        # the load (modelled by the predecessor's steady state), then recomp's
        # per-frame scene_music() swaps to this scene's own theme.
        self.scene_lvl, self.scene_hdr, self.scene_lvl_src = lvl, hdr, src

    def load_cutscenes(self, path):
        text = path.read_text()
        self.cutscenes = [(f, int(n), s) for f, n, s in
                          re.findall(r'\{\s*"(CS\d+\.BIN)",\s*(\d+),\s*(CUTSCENE_SCENE_\w+)', text)]
        # cutscene.c bank_for_cutscene -> music_banks.c level files.
        bank_lvl = {'DEKU_TREE': 'CSDEKU.LVL', 'FAIRYGET': 'FAIRYGET.LVL', 'KOKIRI': 'FOREST.LVL',
                    'NAVI': 'CSNAVI.LVL', 'NIGHTMARE': 'CSGANON.LVL', 'STONE': 'STONE.LVL'}
        self.cs_music = {}
        for idx, body in re.findall(r'cutscene_music_t music_(\d+)\[\]\s*=\s*\{(.*?)\};', text, re.S):
            self.cs_music[int(idx)] = [self.sizes.get(bank_lvl[b], 0) for b in
                                       re.findall(r'CUTSCENE_BANK_(\w+)\s*,', body) if b in bank_lvl]


# --------------------------------------------------------------------------
# Allocation-site scripts (mirrors of the C call sites)
# --------------------------------------------------------------------------
class Model:
    def __init__(self, inp, fixed, notes):
        self.inp = inp
        self.fixed = fixed
        self.notes = notes
        self.zones = [('wram', inp.wram), ('cart1', 0x200000),
                      ('cart2', inp.bank2 - fixed), ('lowram', inp.low_heap)]
        self.warnings = set()
        self.mesh_cache = {}
        self.degraded = []
        self.guard_margin = 1 << 30

    def soft(self, label, fn, *args):
        """Non-fatal sites: a failed allocation degrades (silence, no save...)."""
        try:
            fn(*args)
        except OutOfMemory as exc:
            self.degraded.append('%s: %s' % (label, exc))

    # -- primitives ------------------------------------------------------
    def read_file(self, h, key, name, label=None):
        """jo_fs_read_file: (size + 1) REUSE_BLOCK."""
        s = self.inp.size(name)
        if s is None:
            return False
        h.malloc(key, s + 1, REUSE, label or name)
        return True

    def kfr1(self, name):
        if name not in self.mesh_cache:
            p = self.inp.cd / name
            if not p.exists():
                self.inp.missing.add(name.upper())
                self.mesh_cache[name] = None
            else:
                d = p.read_bytes()[:16]
                self.mesh_cache[name] = struct.unpack('>II', d[8:16]) if len(d) >= 16 else (0, 0)
        return self.mesh_cache[name]

    def load_actor(self, h, key, name, animated=False, struct_alloc=True):
        """cutscene_actor.c actor_mesh_load_static/_animated (and load_actor)."""
        vf = self.kfr1(name)
        if vf is None:
            return False
        v, f = vf
        if struct_alloc:
            h.malloc(key + '.0struct', MESH_STRUCT, FAST, name)
        self.read_file(h, key + '.1file', name)
        h.malloc(key + '.2points', v * POINT_BYTES, FAST, name + ' points')
        h.malloc(key + '.3polys', f * POLYGON_BYTES, FAST, name + ' polygons')
        h.malloc(key + '.4attrs', f * ATTR_BYTES, FAST, name + ' attrs')
        if animated:
            anm = name.rsplit('.', 1)[0] + '.ANM'
            q = self.cvq1(anm)
            if q:
                # cutscene_actor.c load_quantized: tick table, chunk pointers,
                # then one FAST block per chunk (sector reads, no file buffer).
                ticks, chunks = q
                h.malloc(key + '.5anim', 32 + ticks * 2, FAST, anm + ' ticks')
                h.malloc(key + '.6chunks', 4 * len(chunks), FAST, anm + ' chunk table')
                for i, n in enumerate(chunks):
                    h.malloc(key + '.7chunk%02d' % i, n, FAST, anm + ' chunk')
            else:
                self.read_file(h, key + '.5anim', anm)
        return True

    def cvq1(self, name):
        """(ticks, [chunk bytes]) of a CVQ1 track, else None."""
        if name not in self.mesh_cache:
            p = self.inp.cd / name
            d = p.read_bytes()[:32] if p.exists() else b''
            if d[:4] == b'CVQ1':
                v, poses, ticks, per, pose_bytes = struct.unpack('>5I', d[4:24])
                self.mesh_cache[name] = (ticks, [min(per, poses - c) * pose_bytes for c in range(0, poses, per)])
            else:
                self.mesh_cache[name] = None
        return self.mesh_cache[name]

    def sprite_memory(self, h, key, nbytes, label, guard=True):
        """oot_core_host.c host_sprite_memory: jo_malloc(bytes+15+4) + 85 % guard."""
        h.malloc(key, nbytes + 15 + 4, FAST, label)
        pct = h.percent()
        if guard:
            self.guard_margin = min(self.guard_margin, h.guard_limit() - h.live)
        if guard and pct > SPRITE_GUARD_PERCENT:
            h.free(key)
            raise OutOfMemory('%s: sprite guard %d%% > %d%%' % (label, pct, SPRITE_GUARD_PERCENT))

    # -- boot (main.c jo_main) -------------------------------------------
    def boot(self):
        h = Heap(self.zones[:2])            # jo_core_init: WRAM + cart bank 1
        for i, n in enumerate(SDK_SMALL[:4]):
            h.malloc('sdk.%d' % i, n, SAME, 'SDK list node')
        h.names += [z[0] for z in self.zones[2:]]          # ram_cart_claim_second_bank
        h.caps += [z[1] for z in self.zones[2:]]
        h.blocks += [[], []]
        h.high += [0, 0]
        h.total = sum(h.caps)
        h.reset_peak()
        self.guard_margin = 1 << 30
        h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open OOTCORE.BIN')
        h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open NESMSG.BIN')
        self.read_file(h, 'boot.playc', 'PLAYC.PFB')
        for f in ('DIALOG.TXT', 'CUTTEXT.TXT', 'MINIMAP.BIN'):
            self.read_file(h, '~tmp', f)
            h.free('~tmp')
        h.malloc('boot.musictrg', self.inp.musictrg, FAST, 'MUSICTRG table')
        for f in ('MUSICTRG.BIN', 'GOHMAPOS.BIN', 'TITLEPTH.BIN'):
            self.read_file(h, '~tmp', f)
            h.free('~tmp')
        self.read_file(h, 'boot.scenetab', 'SCENETAB.BIN')
        h.transient(SAVE_IO_BYTES, REUSE, 'backup prefs')
        h.malloc('boot.tiles', 12 * self.inp.tile_count, FAST, 'kokiri_tiles')
        h.malloc('boot.cluts', 32 * self.inp.tile_count, FAST, 'kokiri_cluts')
        self.link_model(h, 'child', backup=False)
        self.read_file(h, 'boot.start', 'START.RGB')
        h.malloc('sdk.4', SDK_SMALL[4], SAME, 'recomp vblank node')
        levels_alloc(h, self.inp.title_lvl, 'music levels (title)')
        h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open title levels')
        h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open title PCM')
        for i in range(5, len(SDK_SMALL)):
            h.malloc('sdk.%d' % i, SDK_SMALL[i], SAME, 'SDK list node')
        return h

    def link_model(self, h, age, backup):
        """kokiri_sgl.c link_model_load: three staged files (+ VRAM backup)."""
        files = ('LINKMESH.BIN', 'LINKTEX.BIN', 'LINK.TEX') if age == 'child' else \
                ('ADLTMESH.BIN', 'ADLTTEX.BIN', 'ADULT.TEX')
        for i, f in enumerate(files):
            self.read_file(h, '~link.%d' % i, f)
        if backup:
            c, a = self.inp.link, self.inp.adult
            bank = lambda t: ((t['PIXEL_BYTES'] + 31) & ~31) + t['TILE_COUNT'] * 32
            reserve = max(bank(c), bank(a))
            defs = max(c['TILE_COUNT'], a['TILE_COUNT']) * 8
            h.malloc('~link.backup', reserve + defs, FAST, 'Link VRAM backup')
            h.free('~link.backup')
        for i in range(3):
            if h.has('~link.%d' % i):
                h.free('~link.%d' % i)

    # -- scene sets ------------------------------------------------------
    def native_set(self, h, save_scene):
        """npc_draw_load + world_props_draw_load (legacy C scenes)."""
        inp = self.inp
        models = []
        for scene, model in inp.npcs:
            if scene == save_scene and model not in models:
                models.append(model)
        if save_scene == 4:
            models.append(15)
        for m in models:
            self.read_file(h, 'npc.spr%02d' % m, 'NPC%02d.SPR' % m)
        if save_scene == 4:
            self.read_file(h, 'npc.mask', 'S2R0.MSK')
            for f in ['SHELVES.BIN', 'COUNTER.BIN', 'ITEMSHLD.BIN', 'ITEMNUTS.BIN', 'ITEMSTCK.BIN',
                      'ITEMSEED.BIN', 'ITEMARR5.BIN', 'ITEMARRM.BIN', 'ITEMHART.BIN']:
                self.load_actor(h, 'npc.shop.' + f, f)
        props = []
        if save_scene == 0:
            props.append(('TREEMTH.BIN', False))
        rocks = any(s == save_scene and (i == 0x14E or (i == 0x14F and (p & 3) == 1)) for s, i, p in inp.props)
        pots = any(s == save_scene and i == 0x111 for s, i, p in inp.props)
        chests = save_scene in inp.chests
        if rocks:
            props.append(('ROCK.BIN', False))
        if pots:
            props.append(('POT.BIN', False))
        if chests:
            props.append(('CHEST.BIN', True))
        if save_scene == 0:
            props += [('BUSH.BIN', False), ('GOSSIP.BIN', False), ('SIGNALL.BIN', False)]
        if save_scene in (2, 3):
            props.append(('DTDOOR.BIN', False))
        props.append(('ENDOOR.BIN', False))       # assumption: any scene may own a handle door
        if save_scene == 2:
            props.append(('DTWEB.BIN', False))
            props += [('DTTORCH%d.BIN' % i, False) for i in range(3)]
            props += [('SKULL.BIN', True), ('GOLDSK.BIN', True), ('SKTOKEN.BIN', False), ('DHEAD.BIN', True),
                      ('HINTNUT.BIN', True), ('HINTFLOW.BIN', False), ('HINTBALL.BIN', False)]
            props += [('DTPZ%02d.BIN' % i, False) for i in range(14) if not 0 < i < 4]
            props += [('DTWALL%d.BIN' % i, False) for i in range(5)]   # assumption: walls_count max 5
        if save_scene in (2, 3):
            props += [('GOMALAR.BIN', True), ('GOMAEGG.BIN', False)]
        if save_scene == 3:
            props += [('GOHMA.BIN', True), ('BOSSHRT.BIN', False), ('BLUEWARP.BIN', False)]
        for f, anim in props:
            self.load_actor(h, 'npc.prop.' + f, f, animated=anim)

    def scene_sprites(self, h, scene, objs):
        """OotCore_SpritePreload: lengths[], then archives largest first."""
        rows = []
        for r, (obj, f) in enumerate(self.inp.sprite_rows):
            if obj == 0xFFF:
                name = 'I%02X.SP2' % (scene & 0xFF)
            elif obj in objs:
                name = 'G%03X%02X.SP2' % (obj, f)
            else:
                continue
            h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open ' + name)
            s = self.inp.size(name)
            if s is None or s < 16:
                self.warnings.add('scene %d: sprite archive %s missing (runtime preload fails)' % (scene, name))
                continue
            rows.append((s, r, name))
        self.sprite_memory(h, 'core.lengths', len(self.inp.sprite_rows) * 4, 'sprite lengths[]')
        for s, r, name in sorted(rows, key=lambda t: (-t[0], t[1])):
            self.sprite_memory(h, 'core.sprite.%03d' % r, s + 1, name)
            h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open ' + name)
        h.free('core.lengths')
        return sum(rnd(s + 20) for s, _, _ in rows)

    def player_groups(self, h, oot_scene, age):
        """oot_core_host.c player_groups_load (split_player_bank.py): scene
        groups, the scene cutscene pack, and the C items' groups. Worst case:
        the three largest item groups the age can equip."""
        g = self.inp.player_groups
        if not g:
            return
        names = g['groups']
        flags = g['scene_flags'][oot_scene] if oot_scene < len(g['scene_flags']) else 0
        want = [n for i, n in enumerate(names) if flags >> i & 1]
        if age == 'adult' and oot_scene in g['horse_scenes']:
            want.append('HORSE')
        if oot_scene in g['fish_scenes']:
            want.append('FISH')
        items = ['BOTTLE', 'MAGIC'] + (['HAMMER', 'HOOK'] if age == 'adult' else ['BOOM'])
        items.sort(key=lambda n: -(self.inp.size('PG%s.PFB' % n, required=False) or 0))
        for n in items[:3]:
            if n not in want:
                want.append(n)
        for n in names:
            if n in want:
                self.read_file(h, 'pgrp.' + n, 'PG%s.PFB' % n)
        if flags >> len(names) & 1:                    # CS_PACK, above the group bits
            self.read_file(h, 'pgrp.CS', 'PCS%02X.PFB' % oot_scene)

    def core_meshes(self, h, scene, objs, actors):
        """oot_core_host.c load_meshes (generic scenes, OotCore_MeshList)."""
        if self.inp.scenes[scene]['save_scene'] < SAVE_SCENE_COUNT:
            return 0
        n = 0
        for kind, obj, f, actor in self.inp.meshes:
            aid = self.inp.actor_ids.get(actor)
            if aid is not None and aid not in actors:
                continue
            if h.has('core.mesh.' + f + '.0struct'):
                continue
            if self.load_actor(h, 'core.mesh.' + f, f):
                n += 1
        if n > CORE_MESHES_MAX:
            self.warnings.add('scene %d: %d candidate core meshes > CORE_MESHES_MAX %d '
                              '(upper bound: all layers, objects not checked)' % (scene, n, CORE_MESHES_MAX))
        return n

    def tools(self, h, age):
        """tools_load: optional sheets, dropped above the 85 % guard."""
        dropped = []
        for f in TOOLS[age]:
            key = 'core.tool.' + f
            if h.has(key) or self.inp.size(f, required=False) is None:
                continue
            try:
                self.read_file(h, key, f)
            except OutOfMemory:
                dropped.append(f + '(oom)')
                continue
            if h.percent() > SPRITE_GUARD_PERCENT:
                h.free(key)
                dropped.append(f)
        return dropped

    def music_area(self, h, size):
        """music_area_play: new HDR blob, then free the old slot."""
        if not size:
            return
        h.malloc('music.hdr.new', size + 1, REUSE, 'area HDR')
        if h.has('music.hdr.old'):
            h.free('music.hdr.old')
        if h.has('music.hdr.cur'):
            z, b = h.keys.pop('music.hdr.cur')
            h.keys['music.hdr.old'] = (z, b)
        z, b = h.keys.pop('music.hdr.new')
        h.keys['music.hdr.cur'] = (z, b)

    def music_swap(self, h, size):
        """music.c swap: free levels, FAST pending levels, 8 KB staging."""
        levels_free(h)
        levels_alloc(h, size, 'music levels')
        h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open level stream')
        h.malloc('~music.staging', LOAD_CHUNK, FAST, 'music swap staging')
        h.free('~music.staging')

    # -- scene_flow_load -------------------------------------------------
    def scene_load(self, h, scene, room, age, from_age, layer=None):
        inp = self.inp
        e = inp.scenes[scene]
        h.free_prefix('story.')
        h.free_prefix('npc.')
        if age != from_age:
            self.link_model(h, age, backup=True)
            if age == 'adult':
                h.free_prefix('gear.')
                for i, f in enumerate(('LGEARSKN.BIN', 'LGEARMSH.BIN', 'LGEARTEX.BIN', 'LGEAR.TEX')):
                    self.read_file(h, 'gear.%d' % i, f)
            else:
                h.free_prefix('gear.')
        h.free_prefix('core.sprite.', order='sorted')     # sprites_reset
        h.free_prefix('core.tool.')                        # tools_free
        h.free_prefix('core.mesh.')                        # meshes_free
        h.free_prefix('pgrp.')                             # player_groups_release
        if not h.has('res.playres'):                       # oot_core_player_resident
            self.read_file(h, 'res.playres', 'PLAYRES.PFB')
        if h.has('music.hdr.old'):                         # music_area_trim
            h.free('music.hdr.old')
        h.free_prefix('field.')                            # room_load_bank / backdrop
        if scene == SCENE_SPOT00 and room == 0 and not e['image']:
            stm = 'SAR0.STM'
            p = inp.cd / stm
            if p.exists():
                hd = struct.unpack('>16I', p.read_bytes()[:64])
                tiles, buckets, slots, total, pool, groups = hd[3], hd[5], hd[6], hd[7], hd[12], hd[13]
                start = pool & ~2047
                h.malloc('field.pixels', total - start, REUSE, 'SAR0.STM pixels')
                h.malloc('field.geometry', pool, REUSE, 'SAR0.STM geometry')
                for k, n in (('slot', tiles * 2), ('ref', tiles), ('cur', groups * 2),
                             ('want', groups * 2), ('stack', slots * 2)):
                    h.malloc('field.' + k, n, FAST, 'field ' + k)
            else:
                inp.missing.add(stm)
        if e['save_scene'] < SAVE_SCENE_COUNT:
            self.native_set(h, e['save_scene'])
        else:
            self.load_actor(h, 'npc.prop.ENDOOR.BIN', 'ENDOOR.BIN')
        for f in ('OOC', 'OOB', 'OAP'):
            h.transient(SECTOR_BUFFER, REUSE, 'jo_fs_open scene ' + f)
        objs, actors = inp.ooc(scene)
        if layer is None:
            layer = 0 if age == 'child' else 2
        self.scene_sprites(h, scene, set(inp.layer_objects(scene, layer)))
        self.player_groups(h, e['oot_scene'], age)
        if e['save_scene'] == 1:
            for f in ('NPC19.SPR', 'NPC20.SPR', 'NPC21.SPR', 'NPC22.SPR'):
                self.read_file(h, 'story.' + f, f)
        if e['save_scene'] == SAVE_SCENE_COUNT - 1 and 'z_en_owl' not in inp.pack_actors.get(scene, ()):
            # story_route_load: C owl only when the scene pack lacks source EnOwl.
            for f in ('OWLPERCH.SPR', 'OWLFLY.SPR'):
                self.read_file(h, 'story.' + f, f)
        # enter_world: scene_music() reads the area HDR at once; the first
        # core frame loads meshes/tools; the level tables swap only after the
        # fade (music.c swap_stage 1), i.e. after those allocations.
        self.soft('scene music HDR', self.music_area, h, inp.scene_hdr[scene])
        self.core_meshes(h, scene, set(objs), actors)
        dropped = self.tools(h, age)
        self.soft('scene music levels', self.music_swap, h, inp.scene_lvl[scene])
        return dropped, objs, actors

    def in_play(self, h, scene, age, objs, actors):
        inp = self.inp
        self.soft('area music change HDR', self.music_area, h, inp.scene_hdr[scene])
        self.soft('fanfare/resume level swap', self.music_swap, h, inp.scene_lvl[scene])
        if inp.cutscenes:
            longest = max(inp.cutscenes, key=lambda c: c[1])

            def track():
                self.read_file(h, '~cs.file', longest[0])
                try:
                    h.malloc('~cs.track', longest[1] * 14, FAST, 'cutscene track')
                    h.free('~cs.track')
                finally:
                    h.free('~cs.file')
            self.soft('in-scene cutscene track', track)
        self.soft('save file I/O', h.transient, SAVE_IO_BYTES, REUSE, 'save file I/O')
        if inp.scenes[scene]['rooms'] > 1:       # room change: meshes_free + load_meshes
            h.free_prefix('core.mesh.')
            self.core_meshes(h, scene, objs, actors)
            self.tools(h, age)

    # -- C cutscene chains -------------------------------------------------
    def cutscene_track(self, h, idx):
        """cutscene.c load_track + the CS_START_SEQ banks it swaps to."""
        f, frames, _ = self.inp.cutscenes[idx]
        if h.has('cs.track'):
            h.free('cs.track')
        self.read_file(h, '~cs.file', f)
        h.malloc('cs.track', frames * 14, FAST, f + ' track')
        h.free('~cs.file')
        for size in self.inp.cs_music.get(idx, []):
            self.soft('%s music' % f, self.music_swap, h, size)

    def opening_chain(self, h):
        """New game: CS0 (house) -> CS1 (field riders) -> CS2 (Navi flight) -> CS3."""
        cs = self.inp.cutscenes
        levels_free(h)                      # music_silence for CUTSCENE_SLEEP
        self.cutscene_track(h, 0)
        riders = ['GANON.SPR', 'ZELDA.SPR', 'IMPA.SPR', 'HZELDA.SPR', 'HGANON.SPR']
        for f in riders:
            self.read_file(h, 'cs.actor.' + f, f)
        for f in ('BRIDGE.BIN', 'CHAINS.BIN', 'GATEFIRE.BIN'):
            self.load_actor(h, 'cs.actor.' + f, f, struct_alloc=False)
        self.cutscene_track(h, 1)
        h.free('cs.track')
        h.free_prefix('cs.actor.')
        self.read_file(h, 'cs.open.pool', 'NAVIPOOL.TEX')
        for i in range(10):
            self.read_file(h, 'cs.open.map%d' % i, 'C0R%d.MAP' % i)
        for m in dict.fromkeys(self.inp.navi_models):
            self.read_file(h, 'npc.spr%02d' % m, 'NPC%02d.SPR' % m)
        rooms = (cs[2][1] + 99) // 100
        for i in range(1, min(rooms, 10)):
            self.read_file(h, 'cs.open.mesh%d' % i, 'C0R%d.MSH' % i)
        self.cutscene_track(h, 2)
        h.free('cs.track')
        h.free_prefix('cs.open.')
        h.free_prefix('npc.')
        self.cutscene_track(h, 3)
        return h

    def emerald_chain(self, h):
        """CUTSCENE_EMERALD1..9 started over a loaded gameplay scene."""
        h.free_prefix('npc.')
        h.free_prefix('story.')
        for part in range(1, 10):
            h.free_prefix('em.')
            if part == 2:
                for f in ('GANON.SPR', 'HGANON.SPR'):
                    self.read_file(h, 'em.' + f, f)
            if 3 <= part <= 8:
                for f in ('GODBODY.BIN', 'GODAURA.BIN'):
                    self.load_actor(h, 'em.' + f, f)
            if part == 8:
                self.load_actor(h, 'em.TRIFORCE.BIN', 'TRIFORCE.BIN')
            if part == 9:
                self.load_actor(h, 'em.EMERALD.BIN', 'EMERALD.BIN')
            self.cutscene_track(h, 10 + part)
        return h


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def record(h, m, scene, age, room, pred, kind, err, dropped, layer=0):
    return {'scene': scene, 'age': age, 'room': room, 'layer': layer, 'pred': pred, 'kind': kind,
            'peak': h.peak, 'snapshot': h.peak_snapshot, 'at': h.peak_label,
            'zones': sorted(h.zones_used), 'largest': h.largest, 'error': err,
            'degraded': list(m.degraded), 'guard_margin': m.guard_margin, 'dropped': dropped}


def run(args):
    cd = Path(args.cd)
    if not (cd / 'SCENETAB.BIN').exists():
        print('heap_peak_model: %s has no staged disc (SCENETAB.BIN)' % cd, file=sys.stderr)
        return 2
    notes = []
    inp = Inputs(cd, notes)
    fixed = args.fixed_bytes if args.fixed_bytes is not None else inp.fixed_src
    m = Model(inp, fixed, notes)
    results, steady = [], {}

    def start(h):
        h.reset_peak()
        m.degraded = []
        m.guard_margin = 1 << 30

    # Title -> scene (Continue, Level Select, game over): boot state predecessor.
    for e in inp.scenes:
        for age in ('child', 'adult'):
            for layer in inp.age_layers(e['index'], age):
                for room in range(max(1, e['rooms'])):
                    h = m.boot()
                    start(h)
                    out, err = None, None
                    try:
                        out = m.scene_load(h, e['index'], room, age, 'child', layer)
                    except OutOfMemory as exc:
                        err = str(exc)
                    results.append(record(h, m, e['index'], age, room, 'title', 'title', err,
                                          out[0] if out else [], layer))
                    key = (e['index'], age)
                    if out and (key not in steady or h.live > steady[key][3]):
                        steady[key] = (h.clone(), out[1], out[2], h.live)

    heavy = sorted(steady, key=lambda k: -steady[k][3])
    for e in inp.scenes:
        for age in ('child', 'adult'):
            preds = {}
            for p in inp.preds[e['index']]:
                if (p, age) in steady:
                    preds[(p, age)] = 'door'
            for k in [k for k in heavy if k[1] == age][:args.heavy]:
                preds.setdefault(k, 'warp')
            if e['index'] in AGE_FLIP_SCENES:
                other = 'adult' if age == 'child' else 'child'
                for p in inp.preds[e['index']] | {e['index']}:
                    if (p, other) in steady:
                        preds.setdefault((p, other), 'age')
            for pred, kind in sorted(preds.items()):
                for variant in (('max', 'min') if not args.quick else ('max',)):
                    for layer in inp.age_layers(e['index'], age):
                        for room in range(max(1, e['rooms'])):
                            h = steady[pred][0].clone()
                            if variant == 'min' and h.has('music.levels.00'):
                                levels_free(h)
                                levels_alloc(h, inp.lvl_min, 'music levels (small)')
                            start(h)
                            out, err = None, None
                            try:
                                out = m.scene_load(h, e['index'], room, age, pred[1], layer)
                                m.in_play(h, e['index'], age, out[1], out[2])
                            except OutOfMemory as exc:
                                err = str(exc)
                            results.append(record(h, m, e['index'], age, room,
                                                  '%s/%s lvl-%s' % (inp.scenes[pred[0]]['name'], pred[1], variant),
                                                  kind, err, out[0] if out else [], layer))

    # C cutscene chains (cutscene.c), outside scene_flow_load.
    extra = []
    h = m.boot()
    start(h)
    err = None
    try:
        m.opening_chain(h)
    except OutOfMemory as exc:
        err = str(exc)
    extra.append(dict(record(h, m, -1, 'child', 0, 'title', 'cutscene', err, []),
                      name='opening CS0-CS3 (new game, child)'))
    for s in (1, 7, 9):
        if (s, 'child') in steady:
            h = steady[(s, 'child')][0].clone()
            start(h)
            err = None
            try:
                m.emerald_chain(h)
            except OutOfMemory as exc:
                err = str(exc)
            extra.append(dict(record(h, m, s, 'child', 0, inp.scenes[s]['name'], 'cutscene', err, []),
                              name='emerald CS11-CS19 over %s' % inp.scenes[s]['name']))
    return report(args, inp, m, fixed, results, extra, notes)


ASSUMPTIONS = [
    'build mode OOT_CORE=1, CORE_COLLISION=1, PLAYER_SOURCE=1: no C collision buffer/index/dyna heap; PLAYC.PFB from boot, PLAYRES.PFB from the first scene, '
    'Player demand groups per scene (worst three C-item groups)',
    'music: per scene, the largest LVL (and area HDR) among sequences named by the scene header, its decomp scene '
    'sources (cutscenes), the decomp overlays of every actor in its lists, Player/src/code, and the C scene_music() '
    'rules; the previous scene\'s table stays resident through the load; swap happens after meshes/tools',
    'every scene may be entered as child or adult; tools for a full inventory (optional, dropped by the 85 % guard)',
    'scene layers: child day/night (0, 1), adult day/night (2, 3) and every cutscene layer (4+) for both ages; '
    'sprites load only the destination layer objects (OotScene_LayerObjects)',
    'generic-scene core meshes: union of every room/layer actor list; object residency not checked (upper bound)',
    'legacy C scenes: every conditional native prop/NPC mesh loaded; Deku Tree walls = 5; ENDOOR in every scene',
    'Lost Woods Saria sheets always loaded (story flags ignored); Field C owl sheets unless the scene pack admits source EnOwl',
    'predecessors: title (boot), door-graph sources, the K heaviest steady states (warp/menu), age flip only '
    'into Temple of Time / Chamber of Sages; predecessor states are title->scene (one level of history)',
    'in play: area-music change (third HDR) + level swap, longest cutscene track, 8 KB save I/O, room-change mesh reload',
    'SDK list nodes 8 x 32 B; every jo_fs_open costs a transient 2 KB buffer',
    'fatal = scene load / preload / mesh / opening failure; degraded = music silence, cutscene or save I/O refused',
]


def scene_label(inp, r):
    if r.get('name'):
        return r['name']
    return '%s/%s/layer%d/room%d from %s' % (inp.scenes[r['scene']]['name'], r['age'], r.get('layer', 0),
                                             r['room'], r['pred'])


def report(args, inp, m, fixed, results, extra, notes):
    zones = m.zones
    total = sum(z[1] for z in zones)
    fatal = [r for r in results + extra if r['error']]
    degraded = [r for r in results + extra if r['degraded'] and not r['error']]
    print('Jo heap peak model  RAM_CART_FIXED_BYTES=0x%X (source 0x%X)' % (fixed, inp.fixed_src))
    print('zones: %s; total %d B; sprite guard 85%% => %d B live' % (
        ', '.join('%s %d' % z for z in zones), total, ((total // 64) * 86 + 99) // 100 * 64))
    print('%d scenes, %d scenarios (+%d cutscene chains)' % (len(inp.scenes), len(results), len(extra)))
    print()
    print('%-3s %-16s %-5s %-4s %8s %8s %-8s %-27s %-6s %s' % (
        '#', 'scene', 'age', 'L/rm', 'peak', 'largest', 'zones', 'free wram/cart1/cart2/low', 'status',
        'worst case (predecessor) / reason'))
    worst_ok = None
    for e in inp.scenes:
        rs = [r for r in results if r['scene'] == e['index']]
        bad = [r for r in rs if r['error']]
        deg = [r for r in rs if r['degraded'] and not r['error']]
        ok = [r for r in rs if not r['error']]
        pick = bad[0] if bad else max(ok, key=lambda r: r['peak'])
        status = 'FAIL' if bad else 'DEGR' if deg else 'ok'
        why = ''
        if bad:
            kinds = sorted({r['kind'] for r in bad})
            why = '%s [%d/%d scenarios; via %s]' % (pick['error'], len(bad), len(rs), ','.join(kinds))
        elif deg:
            why = '%s [%d/%d]' % (deg[0]['degraded'][0], len(deg), len(rs))
            pick = deg[0]
        free = '/'.join(str(z['free']) for z in pick['snapshot'])
        zl = ''.join(z[0] if z != 'lowram' else 'l' for z in pick['zones'])
        print('%-3d %-16s %-5s %-4s %8d %8d %-8s %-27s %-6s %s %s' % (
            e['index'], e['name'][:16], pick['age'], '%d/%d' % (pick.get('layer', 0), pick['room']), pick['peak'], pick['largest'][0],
            ','.join(z[:2] for z in pick['zones']), free, status, pick['pred'], why))
        for r in ok:
            if not worst_ok or r['peak'] > worst_ok['peak']:
                worst_ok = r
    print()
    for x in extra:
        print('%-40s peak %8d largest %8d free %s %s' % (
            x['name'], x['peak'], x['largest'][0], '/'.join(str(z['free']) for z in x['snapshot']),
            'FAIL ' + x['error'] if x['error'] else ('DEGR ' + x['degraded'][0] if x['degraded'] else 'ok')))
    ok_all = [r for r in results + extra if not r['error']]
    if ok_all:
        w = max(ok_all, key=lambda r: r['peak'])
        print()
        print('WORST FITTING PEAK: %s: %d B of %d (spare %d) at "%s"' % (
            scene_label(inp, w), w['peak'], total, total - w['peak'], w['at']))
        for z in w['snapshot']:
            print('   %-6s cap %8d live %8d free %8d largest hole %8d' % (
                z['zone'], z['capacity'], z['live'], z['free'], z['largest_hole']))
        big = max(results + extra, key=lambda r: r['largest'][0])
        print('LARGEST BLOCK: %d B (%s)' % (big['largest'][0], big['largest'][1]))
        c2 = min(ok_all, key=lambda r: r['snapshot'][2]['free'])
        print('MIN cart2 free at a fitting peak: %d B (%s)' % (c2['snapshot'][2]['free'], scene_label(inp, c2)))
        g = [r for r in ok_all if r['guard_margin'] < (1 << 30)]
        if g:
            gm = min(g, key=lambda r: r['guard_margin'])
            print('MIN sprite-guard margin: %d B (%s)' % (gm['guard_margin'], scene_label(inp, gm)))
    drops = sorted({'%s/%s' % (inp.scenes[r['scene']]['name'], r['age']) for r in results if r['dropped']})
    if drops:
        print('\nOptional tool sheets dropped (85%% guard): %d scene/age pairs: %s' % (len(drops), ', '.join(drops)))
    if m.warnings:
        print('\nWarnings:')
        for w in sorted(m.warnings):
            print('  ' + w)
    if inp.from_budget:
        print('\nSized from generic_sprites.budget.json (not staged in %s): %s' % (
            inp.cd, ', '.join(sorted(inp.from_budget))))
    if inp.missing:
        print('\nUnsized (not on disc, model skipped them): %s' % ', '.join(sorted(inp.missing)))
    print('\nAssumptions:')
    for a in ASSUMPTIONS + notes:
        print('  - ' + a)
    print()
    fatal_scenes = sorted({r['scene'] for r in fatal if r['scene'] >= 0})
    print('RESULT: %s  fatal %d scenarios (%d scenes%s), degraded %d scenarios' % (
        'FITS' if not fatal and not degraded else 'DOES NOT FIT', len(fatal), len(fatal_scenes),
        ' + cutscenes' if any(r['scene'] < 0 or r.get('name') for r in fatal) else '', len(degraded)))
    if args.json:
        Path(args.json).write_text(json.dumps({
            'fixed_bytes': fixed, 'zones': zones, 'results': results, 'extra': extra,
            'warnings': sorted(m.warnings), 'missing': sorted(inp.missing)}, indent=1, default=str))
    return 1 if fatal or degraded else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--cd', default=str(GAME / 'build' / 'cd'), help='staged disc directory')
    ap.add_argument('--fixed-bytes', type=lambda s: int(s, 0), default=None,
                    help='RAM_CART_FIXED_BYTES to model (default: src/ram_cart.h); e.g. 0x19A800 0x1AA800 0x1AF800')
    ap.add_argument('--heavy', type=int, default=3, help='heaviest steady states used as warp predecessors')
    ap.add_argument('--quick', action='store_true', help='skip the small-previous-music-table variant')
    ap.add_argument('--json', help='write a JSON report')
    return run(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
