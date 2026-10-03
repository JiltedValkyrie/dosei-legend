"""Resident sprites must fit alongside every shipped scene bank."""
import pathlib
import re
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import vdp1_budget as budget
import check_forest_budget


class ResidentBudgetTests(unittest.TestCase):
    def test_actor_reservation_rejects_pre_fix_room(self):
        b = budget.Budget()
        b.parts = [dict(bytes=378368 + 8824 + 143 * 32,
                        tiles=1400 + 143, polygons=0, vertices=0)]
        self.assertFalse(b.failures())
        b.reserve_forest_actors()
        self.assertTrue(any('VDP1 textures' in f for f in b.failures()))

    @unittest.skipUnless((ROOT / 'build/cd/NPC01.BIN').exists(), 'actors not built')
    def test_staged_forest_includes_props_and_nearby_npcs(self):
        check_forest_budget.check(ROOT)

    def test_rejects_forest_bank_that_failed_after_attention_glows(self):
        # Captured failing S1R0: 369024 pixels, 1400 CLUTs; Link 8824/143.
        b = budget.Budget()
        b.parts = [dict(bytes=369024 + 1400 * 32 + 8824 + 143 * 32,
                        tiles=1543, polygons=0, vertices=0)]
        # Later resident HUD/reticle additions can only worsen this old failure.
        self.assertGreaterEqual(b.vram_bytes, 447384)
        self.assertGreaterEqual(b.vram_bytes - b.vram_limit, 1952)
        self.assertTrue(any('VDP1 textures' in failure for failure in b.failures()))
        self.assertLess(b.sprite_slots, budget.MAX_SPRITE_SLOTS)

    def test_hardware_clut_padding_counts_in_budget(self):
        self.assertEqual(budget.tile_bytes(136, 57), 3936)
        self.assertEqual(budget.tile_bytes(56, 63), 1824)
        self.assertEqual(budget.bank_bytes(8912, 154), 8928 + 154 * 32)
        self.assertEqual(budget.bank_bytes(131072, 128), 131072 + 128 * 32)

    def test_sprite_limit_includes_resident_slots_and_jo_slot(self):
        b = budget.Budget()
        b.add('small tiles', [(8, 1)] *
              (budget.MAX_SPRITE_SLOTS - budget.RUNTIME_SPRITE_SLOTS - 1), 0, 0)
        self.assertFalse(b.failures())
        b.add('one too many', [(8, 1)], 0, 0)
        self.assertTrue(any('sprite slots' in failure for failure in b.failures()))

    @unittest.skipUnless((ROOT / 'build/cd/S1R0.MSH').exists(), 'banks not built')
    def test_staged_banks_fit_with_all_resident_sprites(self):
        header = (ROOT / 'build/generated/link_scene.h').read_text()
        value = lambda name: int(re.search(r'#\s*define\s+' + name + r'\s+(\d+)', header)[1])
        link_tiles = value('LINK_TILE_COUNT')
        resident = budget.bank_bytes(value('LINK_PIXEL_BYTES'), link_tiles) + budget.RUNTIME_SPRITE_BYTES
        for path in (ROOT / 'build/cd').glob('*.MSH'):
            with self.subTest(bank=path.name):
                _, _, _, tiles, pixels, _, _, _ = struct.unpack('>8I', path.read_bytes()[:32])
                # Field uses the larger cutscene command reservation.
                base = ((3750 * 32 + 8192 + 255) & ~255) if path.name.startswith('S3R') else budget.TEXTURE_BASE
                self.assertLessEqual(resident + budget.bank_bytes(pixels, tiles), budget.VDP1_END - base)
                if path.name.startswith('S1R'):
                    self.assertLessEqual(resident + budget.bank_bytes(pixels, tiles),
                                         budget.VDP1_END - base - budget.FOREST_VRAM_MARGIN)
                self.assertLessEqual(1 + link_tiles + budget.RUNTIME_SPRITE_SLOTS + tiles,
                                     budget.MAX_SPRITE_SLOTS)


if __name__ == '__main__':
    unittest.main()
