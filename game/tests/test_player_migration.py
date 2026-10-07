"""Execute the imported Player rumble fix with the real Fx32 implementation."""
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_fx32 import ROOT, host_flags, compiler_env, importer


class PlayerMigration(unittest.TestCase):
    def test_rumble_preserves_source_pulse_timing_without_saturation(self):
        rel = 'src/overlays/actors/ovl_player_actor/z_player.c'
        raw = (importer.OOT_DEFAULT / rel).read_text(encoding='utf-8')
        stats = dict(macros=0, fxl=0, anon=0, mtxf=0, problems=[])
        changed = importer.fixup(rel, raw, stats)
        start = changed.index('void Player_DetectRumbleSecrets(')
        body = changed[start:changed.index('\nstatic s8 sCueToCsActionMap', start)]
        program = r'''
#include "ultra64.h"
#include "z_math.h"
extern "C" int printf(const char*, ...);
struct Player { FxSq closestSecretDistSq; Fx unk_6A0; };
static int owned = 1, pulses;
#define CHECK_QUEST_ITEM(x) owned
static void Player_RequestRumble(Player*, int, int, int, int) { pulses++; }
''' + body + r'''
int main() {
    for (int distance = 0; distance <= 30000; distance++) {
        if (distance > 201 && distance != 1000 && distance != 30000) continue;
        Player p = {}; p.closestSecretDistSq = OOT_SQ(Fx(distance));
        int original = 0, expected = 0; pulses = 0;
        for (int tick = 0; tick < 500; tick++) {
            int increment = distance < 200 ? 200000 - distance * distance * 5 : 0;
            original += increment;
            if (original > 4000000) { original = 0; expected++; }
            Player_DetectRumbleSecrets(&p);
            if (pulses != expected || p.unk_6A0.v < 0 || p.unk_6A0.v >= FX_MAX) {
                printf("distance=%d tick=%d pulses=%d expected=%d\n",
                       distance, tick, pulses, expected); return 1;
            }
        }
    }
    Player p = {}; p.closestSecretDistSq = OOT_SQ(Fx(0));
    owned = 0; pulses = 0;
    for (int i = 0; i < 500; i++) Player_DetectRumbleSecrets(&p);
    return pulses != 0 || p.unk_6A0.v != 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / 'player.cpp'
            exe = Path(directory) / 'player.exe'
            src.write_text(program, encoding='utf-8')
            result = subprocess.run([compiler, *host_flags(), str(src),
                                     str(ROOT / 'oot-core/src/oot_math.cpp'),
                                     str(ROOT / 'oot-core/src/oot_rand.cpp'), '-o', str(exe)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], env=env, capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def run_program(self, program):
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / 'player.cpp'
            exe = Path(directory) / 'player.exe'
            src.write_text(program, encoding='utf-8')
            result = subprocess.run([compiler, *host_flags(), str(src),
                                     str(ROOT / 'oot-core/src/oot_math.cpp'),
                                     str(ROOT / 'oot-core/src/oot_rand.cpp'), '-o', str(exe)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], env=env, capture_output=True,
                                    text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def imported(self, rel, start, end):
        raw = (importer.OOT_DEFAULT / rel).read_text(encoding='utf-8')
        stats = dict(macros=0, fxl=0, anon=0, mtxf=0, problems=[])
        changed = importer.fixup(rel, raw, stats)
        first = changed.index(start)
        return changed[first:changed.index(end, first)]

    def test_turn_ratio_is_exact_for_every_yaw_difference(self):
        body = self.imported('src/overlays/actors/ovl_player_actor/z_player.c',
                             's32 func_8083FC68(', '\ns32 func_8083FD78(')
        self.assertNotIn('32768', body)
        program = r'''
#include "ultra64.h"
#include "z_math.h"
extern "C" int printf(const char*, ...);
struct Shape { struct { s16 y; } rot; };
struct ActorT { Shape shape; };
struct Player { ActorT actor; void* focusActor; };
static void func_8083DB98(Player*, int) {}
static int func_8002DD78(Player*) { return 0; }
static int func_808334B4(Player*) { return 0; }
''' + body + r'''
int main() {
    Player p = {};
    for (int d = -32768; d <= 32767; d++) {
        double t = (d < 0 ? -(double)d : (double)d) / 32768.0;
        double fast = t * t * 50.0 + 6.0, side = (1.0 - t) * 10.0 + 6.8;
        for (int q = 0; q <= 240; q++) {
            double speed = q * 0.25;
            /* Fx rounds 6.8 and t*t: skip speeds within 0.01 of a threshold. */
            if ((speed - fast) * (speed - fast) < 1e-4 || (speed - side) * (speed - side) < 1e-4)
                continue;
            int want = speed > fast ? 1 : speed > side ? -1 : 0;
            int got = func_8083FC68(&p, Fx::raw(q << 14), (s16)d);
            if (got != want) { printf("d=%d q=%d got=%d want=%d\n", d, q, got, want); return 1; }
        }
    }
    return 0;
}
'''
        self.run_program(program)

    def test_hookshot_reticle_reach_stays_in_range(self):
        body = self.imported('src/code/z_player_lib.c',
                             '    D_801260C8.z = FXL(1000.0f);', '\n\n')
        self.assertIn('? FXL(38.6f) : FXL(77.6f)', self.imported(
            'src/code/z_player_lib.c', 'Player_DrawHookshotReticle(play, this,', ';'))
        program = r'''
#include "ultra64.h"
#include "z_math.h"
extern "C" int printf(const char*, ...);
static Vec3f D_801260C8, step;
static void Matrix_MultVec3f(Vec3f*, Vec3f* out) { *out = step; }
int main() {
    /* Link matrix scale 0.01: the 1000-unit local step is 10 world units. */
    double reach[2] = { 386.0, 776.0 };
    f32 args[2] = { FXL(38.6f), FXL(77.6f) };
    for (int i = 0; i < 2; i++) {
        Vec3f sp8C = { FXL(100.0f), FXL(50.0f), FXL(-20.0f) }, sp80;
        f32 arg2 = args[i];
        step.x = FXL(106.0f); step.y = FXL(50.0f); step.z = FXL(-12.0f);
''' + body + r'''
        double ex = 100.0 + 0.6 * reach[i], ez = -20.0 + 0.8 * reach[i];
        double gx = sp80.x.v / 65536.0, gy = sp80.y.v / 65536.0, gz = sp80.z.v / 65536.0;
        if (gx - ex > 1 || ex - gx > 1 || gz - ez > 1 || ez - gz > 1 || gy != 50.0) {
            printf("reach=%d x=%d z=%d\n", (int)reach[i], (int)gx, (int)gz); return 1;
        }
    }
    return 0;
}
'''
        self.run_program(program)

    def test_symbol_audit_classifies_link_dependencies(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import player_migration_symbols as audit
        for helper in ('___ashiftrt_r4_10', '___movmemSI12', '___ashrsi3'):
            self.assertTrue(audit.LIBGCC.match(helper))
        for wide in ('___divdi3', '___muldi3', '___addsf3'):
            self.assertFalse(audit.LIBGCC.match(wide))
        def bucket(sym):
            return next((n for n, pat in audit.BUCKETS if pat.match(sym)), 'engine_functions')
        self.assertEqual(bucket('_gPlayerAnim_link_normal_wait'), 'player_animations')
        self.assertEqual(bucket('_gLinkChildSkel'), 'link_draw_assets')
        self.assertEqual(bucket('_gEntranceTable'), 'tables')
        self.assertEqual(bucket('__Z14Camera_SetViewP6CameraP5Vec3f'), 'engine_functions')

    def test_pose_split_keeps_anchor_walk_and_drops_presentation(self):
        rel = 'src/overlays/actors/ovl_player_actor/z_player.c'
        draw = self.imported(rel, '\nvoid Player_Draw(', '\n}\n')
        gameplay = self.imported(rel, '\nvoid Player_DrawGameplay(', '\n}\n')
        impl = self.imported('src/code/z_player_lib.c', '\nvoid Player_DrawImpl(', '\n}\n')
        # Anchors: source lod/override choice, one walk through post-limb draw.
        for need in ('Player_OverrideLimbDrawGameplayFirstPerson',
                     'Player_OverrideLimbDrawGameplayCrawling', 'damageFlickerAnimCounter',
                     'Player_DrawGameplay(play, this, lod, NULL'):
            self.assertIn(need, draw)
        self.assertEqual(draw.count('Player_DrawGameplay('), 1)
        self.assertIn('Player_PostLimbDrawGameplay', gameplay)
        self.assertIn('SkelAnime_DrawFlexLod(', impl)
        self.assertIn('sDListsLodOffset', impl)
        for gone in ('Player_DrawGetItem', 'gEffIceFragment3DL', 'Gfx_SetFog2', 'POLY_'):
            self.assertNotIn(gone, draw)
        for gone in ('sMaskDlists', 'gHoverBootsCircleDL', 'POLY_'):
            self.assertNotIn(gone, gameplay)
        for gone in ('sEyeTextures', 'Gauntlet', 'POLY_'):
            self.assertNotIn(gone, impl)
        for rel, entries in importer.PLAYER_POSE_SPLIT.items():
            for name, _, _ in entries:
                raw = f'\nvoid {name}(PlayState* play) {{\n}}\n'
                with self.assertRaises(ValueError):
                    importer.fix_player_pose_split(rel, raw, {})

    def test_hook_sizer_names_and_owner_classes(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import size_player_hooks as hooks
        self.assertEqual(hooks.plain_name('__Z21Camera_RequestSettingP6Cameras'),
                         'Camera_RequestSetting')
        self.assertEqual(hooks.plain_name('_gEntranceTable'), 'gEntranceTable')
        expect = {'Audio_StopSfxById': 'host_audio', 'func_800F4010': 'host_audio',
                  'Camera_SetViewParam': 'host_camera', 'Play_TriggerVoidOut': 'host_scene_flow',
                  'gEntranceTable': 'host_scene_flow', 'Interface_SetNaviCall': 'host_ui',
                  'Inventory_ConsumeFairy': 'real_gameplay_state', 'Health_IsCritical': 'real_gameplay_state',
                  'gObjectTable': 'saturn_resident_dispatch', 'KaleidoScopeCall_LoadPlayer':
                  'saturn_resident_dispatch', 'Something_Else': 'unclassified'}
        for name, cls in expect.items():
            self.assertEqual(hooks.owner(name), cls, name)

    def test_frame_sizer_reads_source_headers_and_age_blocks(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import size_player_frames as frames
        self.assertEqual(frames.FRAME_BYTES, 134)
        heads = frames.headers(importer.OOT_DEFAULT)
        counts = frames.frame_counts(importer.OOT_DEFAULT)
        self.assertGreaterEqual(len(heads), 521)
        self.assertTrue(all(d in counts for d in heads.values()))
        source = (importer.OOT_DEFAULT /
                  'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
        (adult, child), rest = frames.age_blocks(source)
        self.assertIn('gPlayerAnim_link_normal', adult + child)
        self.assertNotIn('static PlayerAgeProperties sAgeProperties', rest)

    def test_packed_clip_bytes_round_trip(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import player_frame_pack as fp
        src = [[i * 7 - 300, 3000 + i, -i]
               + [((i * 997 + c * 131) % 65536) - 32768 if c % 5 else 1234 for c in range(63)]
               + [0x21 + i % 3] for i in range(11)]
        src[4][10] = 32767; src[5][10] = -32768          # wrap seam inside a channel
        for shift in (0, 2, 4, 6, 8):
            for stride in (1, 2, 3):
                block = fp.pack_clip(src, shift, stride)
                ref = fp.reference(src, shift, stride)
                self.assertEqual(len(block) % 4, 0)
                self.assertGreater(struct.unpack_from('>H', block, 8)[0], 0)  # delta blocks
                self.assertEqual([fp.unpack_frame(block, i) for i in range(11)], ref)
                for a, b in zip(src, ref):
                    self.assertEqual(a[0:3], b[0:3])     # root motion exact
                    self.assertEqual(a[66], b[66])       # face word exact
        self.assertEqual(fp.reference(src, 0, 1), src)
        # Constant channels cost no stream bits.
        block = fp.pack_clip(src, 0, 1)
        widths = block[fp.WIDTHS:fp.WIDTHS + 67]
        self.assertTrue(all(widths[c] == 0 for c in range(3, 66) if (c - 3) % 5 == 0))
        mixed = [8 if c % 2 == 0 else 2 for c in range(63)]
        block = fp.pack_clip(src, mixed, 2)
        self.assertEqual(list(block[fp.SHIFTS:fp.SHIFTS + 63]), mixed)
        self.assertEqual([fp.unpack_frame(block, i) for i in range(11)], fp.reference(src, mixed, 2))
        # Shortest arc across the seam, C truncating division.
        seam = [[0, 0, 0] + [32000] * 63 + [0], [0, 0, 0] + [32000] * 63 + [0],
                [0, 0, 0] + [-32000] * 63 + [0]]
        self.assertEqual(fp.reference(seam, 0, 2)[1][3], fp.wrap(32000 + 768))

    def test_bank_precision_raises_only_blamed_channels(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import build_player_frame_bank as bank
        bank._init_worker(importer.OOT_DEFAULT)
        limbs, points, layout = bank._W['adult']
        self.assertEqual(len(layout), len(bank.anchors(limbs, points, [0] * 67)[0]))
        # Only the left-hand limb (15) moves, by a little each frame.
        src = [[0, 3000, 0] + [0] * 63 + [0] for _ in range(6)]
        for i, f in enumerate(src):
            f[3 + 15 * 3 + 1] = 1000 + i * 37
        choice = bank.choose([bank._W['adult']], src, bank.ALWAYS_TIGHT | {'weapon'}, 0.5, 2.0)
        raised = [c for c, s in enumerate(choice['shifts']) if s < 8]
        self.assertTrue(all(c // 3 == 15 for c in raised), raised)
        self.assertLessEqual(choice['error'], 1.0)

    def test_bank_context_marks_attack_clips_weapon_tight(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import build_player_frame_bank as bank
        text = (importer.OOT_DEFAULT /
                'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
        table = text[text.index('D_80854190[PLAYER_MWA_MAX] = {'):]
        attack = re.search(r'&(gPlayerAnim_\w+)', table).group(1)
        idle = 'gPlayerAnim_link_normal_wait'
        cs_only = 'gPlayerAnim_link_demo_goma_furimuki'
        ctx = bank.clip_context(importer.OOT_DEFAULT, {attack, idle, cs_only})
        self.assertIn('weapon', ctx[attack][1])
        # Uncertain stays strict: ordinary clips without an attack marker too.
        self.assertEqual(ctx[idle][1], {'weapon', 'held'})
        self.assertEqual(ctx[cs_only][1], frozenset())

    def test_core_region_loader_validates_before_writing(self):
        spans = [(0x02770000, 589824), (0x0021D800, 40960), (0x002FA000, 24576),
                 (0x026EC800, 20480), (0x02683800, 4096)]
        def payload(regions, bss=(0x02770100, 0x02770140), magic=b'ORG1'):
            head = magic + struct.pack('>HHII', 1, len(regions), *bss)
            offset = 16 + 12 * len(regions)
            table, body = b'', b''
            for address, data in regions:
                table += struct.pack('>III', address, len(data), offset + len(body))
                body += data
            return head + table + body
        good = payload([(0x02770000, b'\x11' * 0x100), (0x0021D800, b'\x22' * 64),
                        (0x02683800 + 4096 - 8, b'\x33' * 8)])
        cases = {
            'good': good,
            'magic': payload([(0x02770000, b'\x11' * 4)], magic=b'ORG0'),
            'outside': payload([(0x0021D800 + 40960 - 4, b'\x22' * 8)]),
            'overlap': payload([(0x02770000, b'\x11' * 16), (0x02770008, b'\x22' * 16)]),
            'bss_cover': payload([(0x02770100, b'\x11' * 16)]),
            'unaligned': payload([(0x0021D802, b'\x22' * 4)]),
        }
        program = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "oot_core_regions.h"
static uint8_t mem[5][589824];
static uint8_t *map(uint32_t a) {
    for (int i = 0; i < 5; i++)
        if (a >= oot_region_spans[i].address && a < oot_region_spans[i].address + oot_region_spans[i].bytes)
            return mem[i] + (a - oot_region_spans[i].address);
    abort();
}
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb"); static uint8_t buf[1 << 16];
    int n = (int)fread(buf, 1, sizeof buf, f); fclose(f);
    memset(mem, 0xEE, sizeof mem);
    int r = oot_core_regions_load(buf, n, oot_region_spans, 5, map);
    int touched = 0;
    for (int i = 0; i < 5; i++) for (int j = 0; j < 589824; j++) touched += mem[i][j] != 0xEE;
    printf("%d %d %02x %02x %02x %02x\n", r, touched, mem[0][0], mem[0][0x100], mem[1][0],
           mem[4][4088]);
    return 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            (d / 'main.c').write_text(program, encoding='utf-8')
            exe = d / 'loader.exe'
            result = subprocess.run([compiler, '-x', 'c', '-O1', '-I', str(ROOT / 'src'),
                                     str(d / 'main.c'), str(ROOT / 'src/oot_core_regions.c'),
                                     '-o', str(exe)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            got = {}
            for name, data in cases.items():
                (d / name).write_bytes(data)
                got[name] = subprocess.run([str(exe), str(d / name)], env=env, capture_output=True,
                                           text=True).stdout.split()
        self.assertEqual(got['good'][0], '3')
        self.assertEqual(got['good'][2:], ['11', '00', '22', '33'])   # images copied, BSS zeroed
        expect = {'magic': '-1', 'outside': '-3', 'overlap': '-4', 'bss_cover': '-4', 'unaligned': '-2'}
        for name, code in expect.items():
            self.assertEqual(got[name][:2], [code, '0'], name)       # nothing written

    def test_frame_bank_placement_respects_each_allocation(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import place_frame_bank as place
        resident = [(i, 4000) for i in range(130)]           # 520,000 B of clips
        result = place.place(resident, {'a': 20000, 'b': 10000})
        self.assertIsNotNone(result)
        for chunk in result['chunks'].values():
            self.assertLessEqual(chunk['file_bytes'], chunk['capacity'])
        self.assertTrue(result['fits_worst_scene'])
        self.assertFalse(result['fits_transition_with_rollback'])   # 30 KB both packs
        self.assertIsNone(place.place([(0, 500000)], {}))           # no single hole is big enough

    def test_bank_adapter_and_demand_cache_host_harnesses(self):
        bank = ROOT / 'build/player-migration/bank_strict'
        if not (bank / 'ALL.PFB').exists():
            self.skipTest('run tools/build_player_frame_bank.py first')
        compiler, env = compiler_env()
        packs = sorted(str(p) for p in bank.glob('S_*.PFB'))
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            dec = d / 'dec.o'
            r = subprocess.run([compiler, '-x', 'c', '-O2', '-c',
                                str(ROOT / 'oot-core/tests/player_frame_decode.c'), '-o', str(dec)],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name, sources, args in (
                    ('bank', ['oot-core/src/player_frame_bank.cpp',
                              'oot-core/tests/player_frame_bank_test.cpp'], [str(bank)] + packs),
                    ('cache', ['oot-core/src/player_anim_cache.cpp', 'oot-core/src/player_frame_bank.cpp',
                               'oot-core/tests/player_anim_cache_test.cpp'], [str(bank)])):
                exe = d / (name + '.exe')
                r = subprocess.run([compiler, '-x', 'c++', '-O2', *[str(ROOT / s) for s in sources],
                                    '-x', 'none', str(dec), '-o', str(exe)],
                                   env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                r = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True,
                                   timeout=300)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn('PASS', r.stdout)

    def test_collision_port_probes(self):
        """C library vs core parity, dyna contract and bg_* shim scenario.
        Linux only (host core build). The one tracked Fx corner case is the
        only shim row allowed to differ until it is fixed."""
        if os.name == 'nt' or not (ROOT / 'build/cd/S1.COL').exists():
            self.skipTest('Linux host build with build/cd/S1.COL required')
        r = subprocess.run(['bash', str(ROOT / 'oot-core/tests/run_bg_port_probe.sh')],
                           capture_output=True, text=True, timeout=1800)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        self.assertIn('dyna contract PASS', r.stdout)
        self.assertRegex(r.stdout, r'rows, [01] differ beyond')
        self.assertIn('known Fx case plat 520,520', r.stdout)

    def test_changed_source_anchor_fails_closed(self):
        for rel in ('src/overlays/actors/ovl_player_actor/z_player.c',
                    'src/code/z_player_lib.c'):
            with self.assertRaises(ValueError):
                importer.fix_player_migration(rel, '', {})


if __name__ == '__main__':
    unittest.main()
