"""Drive the real file_select.c against an in-memory backup device.

file_select.c is platform free and reaches storage only through
save_device.h, so the fake device in tests/fixtures/save_device_fake.c lets the
real screen logic be driven through states a physical cartridge makes awkward to
arrange: an empty slot, a damaged slot, a save from an older layout, and a
device that refuses to write or erase.

The rules worth protecting: an unreadable file is never silently overwritten,
cancelling never loses data, and a refused device operation is reported rather
than passing for success.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

SAVE_FILE_SLOTS = 3
ROW_ERASE = SAVE_FILE_SLOTS
ROWS = SAVE_FILE_SLOTS + 1

CHOOSING, ERASE_PICK, ERASE_CONFIRM = 0, 1, 2
NONE, START_NEW, START_LOAD, BACK = 0, 1, 2, 3

SAVE_FILE_OK = 0
SAVE_FILE_EMPTY = 1
SAVE_FILE_BAD_VERSION = 3
SAVE_FILE_BAD_CHECKSUM = 4

QUEST_KOKIRI_EMERALD = 18
EVENTCHKINF_DEKU_TREE_CLEARED = 0x09
HEART_UNIT = 0x10


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class FileSelect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'file_select.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/file_select.c'),
                        str(ROOT / 'src/save_file.c'),
                        str(ROOT / 'src/save_state.c'),
                        str(ROOT / 'tests/fixtures/save_device_fake.c'),
                        str(ROOT / 'tests/fixtures/file_select_host.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        for name in ('file_select_row_label', 'file_select_row_detail'):
            getattr(cls.lib, name).restype = ctypes.c_char_p
        cls.lib.file_select_copy_supported.restype = ctypes.c_bool
        cls.lib.save_check_quest_item.restype = ctypes.c_bool
        cls.lib.save_get_event_chk_inf.restype = ctypes.c_bool
        cls.lib.fs_device_failed.restype = ctypes.c_bool
        for name in ('fs_mode', 'fs_cursor', 'fs_result', 'fs_slot',
                     'fs_status', 'fake_is_stored', 'fs_step'):
            getattr(cls.lib, name).restype = ctypes.c_int

    def setUp(self):
        self.lib.fake_reset()
        self.lib.save_new_game()
        self.lib.file_select_open()

    # ---- helpers -------------------------------------------------------

    def step(self, up=0, down=0, confirm=0, cancel=0):
        return self.lib.fs_step(up, down, confirm, cancel)

    def populate(self, slot, rupees=10, emerald=False, damage=0):
        """Put a recognisable save into a slot via the fake device."""
        self.lib.save_new_game()
        self.lib.fs_set_rupees(rupees)
        if emerald:
            self.lib.save_give_quest_item(QUEST_KOKIRI_EMERALD)
            self.lib.save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_CLEARED)
        if damage:
            self.lib.save_damage(damage)
        self.lib.fake_store_current(slot)
        self.lib.save_new_game()
        self.lib.file_select_refresh()

    # ---- opening -------------------------------------------------------

    def test_opens_on_the_first_file_with_all_slots_empty(self):
        self.assertEqual(CHOOSING, self.lib.fs_mode())
        self.assertEqual(0, self.lib.fs_cursor())
        self.assertEqual(NONE, self.lib.fs_result())
        for slot in range(SAVE_FILE_SLOTS):
            self.assertEqual(SAVE_FILE_EMPTY, self.lib.fs_status(slot))
            self.assertIn(b'NEW FILE', self.lib.file_select_row_detail(slot))

    def test_every_row_has_a_label(self):
        for row in range(ROWS):
            self.assertTrue(self.lib.file_select_row_label(row))
        self.assertIn(b'ERASE', self.lib.file_select_row_label(ROW_ERASE))

    def test_copy_is_not_advertised(self):
        self.assertFalse(self.lib.file_select_copy_supported())

    # ---- cursor --------------------------------------------------------

    def test_cursor_wraps_across_files_and_the_erase_row(self):
        for expected in (1, 2, ROW_ERASE, 0):
            self.step(down=1)
            self.assertEqual(expected, self.lib.fs_cursor())
        self.step(up=1)
        self.assertEqual(ROW_ERASE, self.lib.fs_cursor())

    def test_erase_pick_cursor_cannot_land_on_the_erase_row(self):
        self.populate(0)
        self.step(down=1)
        self.step(down=1)
        self.step(down=1)               # on the erase row
        self.step(confirm=1)
        self.assertEqual(ERASE_PICK, self.lib.fs_mode())
        for _ in range(ROWS * 2):
            self.step(down=1)
            self.assertLess(self.lib.fs_cursor(), SAVE_FILE_SLOTS)

    # ---- starting a game -----------------------------------------------

    def test_an_empty_slot_starts_a_new_game(self):
        self.assertEqual(START_NEW, self.step(confirm=1))
        self.assertEqual(0, self.lib.fs_slot())
        self.assertFalse(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))

    def test_a_new_game_starts_from_a_clean_save_even_over_stale_state(self):
        self.lib.save_give_quest_item(QUEST_KOKIRI_EMERALD)
        self.step(confirm=1)
        self.assertFalse(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))

    def test_a_stored_slot_loads_and_brings_its_progress_back(self):
        self.populate(1, rupees=42, emerald=True)
        self.step(down=1)
        self.assertEqual(START_LOAD, self.step(confirm=1))
        self.assertEqual(1, self.lib.fs_slot())
        self.assertTrue(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))
        self.assertTrue(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_DEKU_TREE_CLEARED))
        self.assertEqual(42, self.lib.fs_rupees())

    def test_a_loaded_slot_is_summarised_before_it_is_loaded(self):
        self.populate(2, rupees=7, emerald=True, damage=HEART_UNIT)
        detail = self.lib.file_select_row_detail(2)
        self.assertIn(b'2/3 HEARTS', detail)
        self.assertIn(b'7 RUPEES', detail)
        self.assertIn(b'EMERALD', detail)
        # Summarising must not have loaded it.
        self.assertFalse(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))

    def test_result_latches_so_a_held_button_cannot_choose_twice(self):
        self.assertEqual(START_NEW, self.step(confirm=1))
        self.assertEqual(START_NEW, self.step(confirm=1, down=1))
        self.assertEqual(0, self.lib.fs_slot())

    # ---- refusing what cannot be read ----------------------------------

    def test_a_damaged_slot_is_reported_and_not_offered(self):
        self.populate(0)
        self.lib.fake_corrupt(0, 40)
        self.lib.file_select_refresh()
        self.assertEqual(SAVE_FILE_BAD_CHECKSUM, self.lib.fs_status(0))
        self.assertIn(b'DAMAGED', self.lib.file_select_row_detail(0))
        # Confirming it must neither load nor overwrite it.
        self.assertEqual(NONE, self.step(confirm=1))
        self.assertTrue(self.lib.fs_device_failed())
        self.assertTrue(self.lib.fake_is_stored(0))

    def test_an_older_save_is_reported_and_not_overwritten(self):
        self.populate(0)
        self.lib.fake_set_version(0, 0)
        self.lib.file_select_refresh()
        self.assertEqual(SAVE_FILE_BAD_VERSION, self.lib.fs_status(0))
        self.assertEqual(NONE, self.step(confirm=1))
        self.assertTrue(self.lib.fake_is_stored(0))

    def test_a_damaged_slot_can_still_be_erased_deliberately(self):
        self.populate(0)
        self.lib.fake_corrupt(0, 40)
        self.lib.file_select_refresh()
        for _ in range(ROW_ERASE):
            self.step(down=1)
        self.step(confirm=1)                    # enter erase mode
        self.step(confirm=1)                    # pick slot 0
        self.assertEqual(ERASE_CONFIRM, self.lib.fs_mode())
        self.step(confirm=1)                    # confirm
        self.assertFalse(self.lib.fake_is_stored(0))
        self.assertEqual(SAVE_FILE_EMPTY, self.lib.fs_status(0))

    # ---- erasing -------------------------------------------------------

    def enter_erase(self):
        while self.lib.fs_cursor() != ROW_ERASE:
            self.step(down=1)
        self.step(confirm=1)
        self.assertEqual(ERASE_PICK, self.lib.fs_mode())

    def test_erase_needs_a_confirmation_step(self):
        self.populate(0)
        self.enter_erase()
        self.step(confirm=1)
        self.assertEqual(ERASE_CONFIRM, self.lib.fs_mode())
        self.assertTrue(self.lib.fake_is_stored(0))     # not yet gone
        self.step(confirm=1)
        self.assertFalse(self.lib.fake_is_stored(0))

    def test_cancelling_the_confirmation_keeps_the_file(self):
        self.populate(0)
        self.enter_erase()
        self.step(confirm=1)
        self.step(cancel=1)
        self.assertEqual(ERASE_PICK, self.lib.fs_mode())
        self.assertTrue(self.lib.fake_is_stored(0))
        self.assertEqual(SAVE_FILE_OK, self.lib.fs_status(0))

    def test_erasing_only_touches_the_chosen_slot(self):
        for slot in range(SAVE_FILE_SLOTS):
            self.populate(slot, rupees=slot + 1)
        self.enter_erase()
        self.step(down=1)               # slot 1
        self.step(confirm=1)
        self.step(confirm=1)
        self.assertTrue(self.lib.fake_is_stored(0))
        self.assertFalse(self.lib.fake_is_stored(1))
        self.assertTrue(self.lib.fake_is_stored(2))

    def test_erasing_an_empty_slot_does_nothing_and_is_not_an_error(self):
        self.enter_erase()
        self.step(confirm=1)
        self.assertEqual(ERASE_PICK, self.lib.fs_mode())
        self.assertFalse(self.lib.fs_device_failed())

    def test_a_device_that_refuses_to_erase_says_so(self):
        self.populate(0)
        self.lib.fs_set_erase_fails(1)
        self.enter_erase()
        self.step(confirm=1)
        self.step(confirm=1)
        self.assertTrue(self.lib.fs_device_failed())
        self.assertTrue(self.lib.fake_is_stored(0))

    # ---- leaving -------------------------------------------------------

    def test_cancel_from_the_file_list_returns_to_the_title(self):
        self.assertEqual(BACK, self.step(cancel=1))

    def test_cancel_backs_out_of_erase_mode_instead_of_leaving(self):
        self.enter_erase()
        self.assertEqual(NONE, self.step(cancel=1))
        self.assertEqual(CHOOSING, self.lib.fs_mode())
        self.assertEqual(ROW_ERASE, self.lib.fs_cursor())
        # A second cancel, now on the file list, does leave.
        self.assertEqual(BACK, self.step(cancel=1))

    def test_reopening_resets_the_screen(self):
        self.step(down=1)
        self.step(cancel=1)
        self.lib.file_select_open()
        self.assertEqual(CHOOSING, self.lib.fs_mode())
        self.assertEqual(0, self.lib.fs_cursor())
        self.assertEqual(NONE, self.lib.fs_result())


if __name__ == '__main__':
    unittest.main()
