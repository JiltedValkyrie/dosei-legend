"""Drive the real save_file.c: round trip, version, checksum, refusal.

Compiled and called through ctypes rather than reimplemented. save_file.c is
platform free, so no Saturn and no backup cartridge is involved -- which is the
point: the failure modes a real BUP device produces (a block reading back all
zeroes or all 0xFF, one flipped byte, a save written by an older layout) can be
produced here deliberately instead of waited for.

The rule these tests exist to protect: a save that cannot be read must be
REFUSED, and refusing it must not disturb the live quest state.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

SAVE_FILE_PAYLOAD_BYTES = 210
SAVE_FILE_BYTES = 8 + SAVE_FILE_PAYLOAD_BYTES + 2
SAVE_FILE_VERSION = 1

SAVE_FILE_OK = 0
SAVE_FILE_EMPTY = 1
SAVE_FILE_BAD_MAGIC = 2
SAVE_FILE_BAD_VERSION = 3
SAVE_FILE_BAD_CHECKSUM = 4
SAVE_FILE_BAD_SIZE = 5

QUEST_KOKIRI_EMERALD = 18
EVENTCHKINF_DEKU_TREE_CLEARED = 0x09
EQUIP_TYPE_SWORD = 0
EQUIP_TYPE_SHIELD = 1
EQUIP_VALUE_SWORD_KOKIRI = 1
EQUIP_VALUE_SHIELD_DEKU = 1
SAVE_SCENE_KOKIRI_FOREST = 0
SAVE_SCENE_DEKU_TREE = 2
HEART_UNIT = 0x10


class Summary(ctypes.Structure):
    _fields_ = [('present', ctypes.c_bool),
                ('hearts', ctypes.c_uint8),
                ('hearts_full', ctypes.c_uint8),
                ('rupees', ctypes.c_uint16),
                ('has_emerald', ctypes.c_bool),
                ('deku_tree_cleared', ctypes.c_bool),
                ('scene_id', ctypes.c_uint8)]


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class SaveFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'save_file.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/save_file.c'),
                        str(ROOT / 'src/save_state.c'),
                        str(ROOT / 'tests/fixtures/save_file_host.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.save_file_checksum.restype = ctypes.c_uint16
        cls.lib.save_file_status_text.restype = ctypes.c_char_p
        cls.lib.sf_summary.restype = ctypes.c_int
        cls.lib.sf_summary.argtypes = [ctypes.POINTER(Summary),
                                       ctypes.c_char_p, ctypes.c_uint]
        cls.lib.sf_pack.argtypes = [ctypes.c_char_p]
        cls.lib.sf_unpack.restype = ctypes.c_int
        cls.lib.sf_unpack.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        cls.lib.sf_fingerprint.restype = ctypes.c_uint
        cls.lib.sf_quest_items.restype = ctypes.c_uint
        # These return C `bool`. Without an explicit restype ctypes reads the
        # full 32-bit return register, and GCC leaves the masked flag value in
        # its upper bits -- so a cleared flag can read back as a large nonzero
        # int and assertFalse fails on a save that is perfectly correct.
        for name in ('save_get_event_chk_inf', 'save_get_inf_table',
                     'save_get_item_get_inf', 'save_check_quest_item',
                     'save_get_treasure', 'save_get_switch', 'save_get_clear',
                     'save_get_collectible', 'save_mido_demands_met',
                     'save_is_dead'):
            getattr(cls.lib, name).restype = ctypes.c_bool

    def setUp(self):
        self.lib.save_new_game()

    # ---- helpers -------------------------------------------------------

    def pack(self):
        """Serialise the current live save."""
        buf = ctypes.create_string_buffer(SAVE_FILE_BYTES)
        self.lib.sf_pack(buf)
        return bytearray(buf.raw[:SAVE_FILE_BYTES])

    def unpack(self, block):
        raw = bytes(block)
        return self.lib.sf_unpack(raw, len(raw))

    def summary(self, block):
        out = Summary()
        raw = bytes(block)
        status = self.lib.sf_summary(ctypes.byref(out), raw, len(raw))
        return status, out

    def furnish(self):
        """Put recognisable progress into the live save."""
        self.lib.save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_CLEARED)
        self.lib.save_set_inf_table(0x0C)
        self.lib.save_give_quest_item(QUEST_KOKIRI_EMERALD)
        self.lib.save_set_treasure(SAVE_SCENE_KOKIRI_FOREST, 0)
        self.lib.save_set_treasure(SAVE_SCENE_DEKU_TREE, 1)
        self.lib.save_set_switch(SAVE_SCENE_DEKU_TREE, 4)
        self.lib.save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.lib.save_set_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_set_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.lib.save_damage(HEART_UNIT)
        self.lib.sf_set_rupees(42)
        self.lib.sf_set_scene(SAVE_SCENE_DEKU_TREE, 3)

    # ---- layout --------------------------------------------------------

    def test_packed_block_is_exactly_the_declared_size(self):
        self.assertEqual(SAVE_FILE_BYTES, len(self.pack()))

    def test_header_carries_magic_and_version(self):
        block = self.pack()
        self.assertEqual(b'DLSV', bytes(block[:4]))
        self.assertEqual(SAVE_FILE_VERSION, (block[4] << 8) | block[5])

    # ---- round trip ----------------------------------------------------

    def test_round_trip_restores_every_field(self):
        self.furnish()
        block = self.pack()
        before = self.lib.sf_fingerprint()
        self.lib.save_new_game()
        self.assertNotEqual(before, self.lib.sf_fingerprint())
        self.assertEqual(SAVE_FILE_OK, self.unpack(block))
        self.assertEqual(before, self.lib.sf_fingerprint())

    def test_round_trip_preserves_the_gates_the_quest_depends_on(self):
        self.furnish()
        block = self.pack()
        self.lib.save_new_game()
        self.assertEqual(SAVE_FILE_OK, self.unpack(block))
        self.assertTrue(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_DEKU_TREE_CLEARED))
        self.assertTrue(self.lib.save_get_inf_table(0x0C))
        self.assertTrue(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))
        self.assertTrue(self.lib.save_get_treasure(SAVE_SCENE_DEKU_TREE, 1))
        self.assertTrue(self.lib.save_get_switch(SAVE_SCENE_DEKU_TREE, 4))
        self.assertFalse(self.lib.save_get_treasure(SAVE_SCENE_DEKU_TREE, 0))
        # And the equipment state Mido's gate reads.
        self.assertTrue(self.lib.save_mido_demands_met())

    def test_a_fresh_file_round_trips_too(self):
        block = self.pack()
        self.assertEqual(SAVE_FILE_OK, self.unpack(block))
        self.assertFalse(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))
        self.assertFalse(self.lib.save_is_dead())

    # ---- refusal -------------------------------------------------------

    def test_blank_device_reads_as_an_empty_slot_not_corruption(self):
        # A never-written backup block reads back uniform. Both spellings must
        # look like "no save yet", because that is not an error.
        for fill in (0x00, 0xFF):
            block = bytearray([fill]) * SAVE_FILE_BYTES
            self.assertEqual(SAVE_FILE_EMPTY, self.unpack(block),
                             'fill 0x%02X' % fill)

    def test_another_games_block_is_refused_as_foreign(self):
        block = bytearray(b'ZZZZ') + bytearray(SAVE_FILE_BYTES - 4)
        self.assertEqual(SAVE_FILE_BAD_MAGIC, self.unpack(block))

    def test_an_older_layout_is_refused_not_guessed_at(self):
        block = self.pack()
        block[4] = 0
        block[5] = SAVE_FILE_VERSION - 1 if SAVE_FILE_VERSION else 0
        self.assertEqual(SAVE_FILE_BAD_VERSION, self.unpack(block))

    def test_a_future_layout_is_also_refused(self):
        block = self.pack()
        block[5] = SAVE_FILE_VERSION + 1
        self.assertEqual(SAVE_FILE_BAD_VERSION, self.unpack(block))

    def test_a_short_block_is_refused(self):
        block = self.pack()[:SAVE_FILE_BYTES - 1]
        self.assertEqual(SAVE_FILE_BAD_SIZE, self.unpack(block))

    def test_every_single_flipped_payload_byte_is_caught(self):
        """One bad byte anywhere in the payload must fail the checksum."""
        clean = self.pack()
        for offset in range(8, 8 + SAVE_FILE_PAYLOAD_BYTES):
            block = bytearray(clean)
            block[offset] ^= 0xFF
            self.assertEqual(SAVE_FILE_BAD_CHECKSUM, self.unpack(block),
                             'offset %d survived corruption' % offset)

    def test_a_refused_load_does_not_disturb_the_live_save(self):
        self.furnish()
        expected = self.lib.sf_fingerprint()
        for block in (bytearray([0xFF]) * SAVE_FILE_BYTES,
                      bytearray(b'ZZZZ') + bytearray(SAVE_FILE_BYTES - 4)):
            self.unpack(block)
            self.assertEqual(expected, self.lib.sf_fingerprint())
        damaged = self.pack()
        damaged[20] ^= 0x01
        self.assertEqual(SAVE_FILE_BAD_CHECKSUM, self.unpack(damaged))
        self.assertEqual(expected, self.lib.sf_fingerprint())

    def test_checksum_rejects_an_all_zero_payload(self):
        # A plain additive sum would give zero for a zeroed payload and so
        # accept a dead block. The rotate is what prevents that.
        self.assertNotEqual(0, self.lib.save_file_checksum(
            bytes(SAVE_FILE_PAYLOAD_BYTES), SAVE_FILE_PAYLOAD_BYTES))

    def test_checksum_notices_byte_order(self):
        a = bytes([1, 2]) + bytes(SAVE_FILE_PAYLOAD_BYTES - 2)
        b = bytes([2, 1]) + bytes(SAVE_FILE_PAYLOAD_BYTES - 2)
        self.assertNotEqual(
            self.lib.save_file_checksum(a, SAVE_FILE_PAYLOAD_BYTES),
            self.lib.save_file_checksum(b, SAVE_FILE_PAYLOAD_BYTES))

    # ---- summaries -----------------------------------------------------

    def test_summary_describes_a_slot_without_loading_it(self):
        self.furnish()
        block = self.pack()
        self.lib.save_new_game()
        fresh = self.lib.sf_fingerprint()
        status, out = self.summary(block)
        self.assertEqual(SAVE_FILE_OK, status)
        self.assertTrue(out.present)
        self.assertEqual(3, out.hearts)
        self.assertEqual(2, out.hearts_full)       # one heart of damage
        self.assertEqual(42, out.rupees)
        self.assertTrue(out.has_emerald)
        self.assertTrue(out.deku_tree_cleared)
        self.assertEqual(SAVE_SCENE_DEKU_TREE, out.scene_id)
        # Reading a summary must not load the file.
        self.assertEqual(fresh, self.lib.sf_fingerprint())

    def test_summary_of_an_empty_slot_reports_absent(self):
        status, out = self.summary(bytearray([0x00]) * SAVE_FILE_BYTES)
        self.assertEqual(SAVE_FILE_EMPTY, status)
        self.assertFalse(out.present)

    def test_summary_of_a_damaged_slot_reports_absent_and_says_why(self):
        block = self.pack()
        block[30] ^= 0x80
        status, out = self.summary(block)
        self.assertEqual(SAVE_FILE_BAD_CHECKSUM, status)
        self.assertFalse(out.present)
        self.assertIn(b'DAMAGED', self.lib.save_file_status_text(status))

    def test_every_status_has_text(self):
        for status in range(SAVE_FILE_BAD_SIZE + 1):
            self.assertTrue(self.lib.save_file_status_text(status))


if __name__ == '__main__':
    unittest.main()
