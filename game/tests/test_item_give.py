"""Drive the real save_state.c grant path (M3a): Item_Give and EnGirlA_CanBuy.

Rules come from z_parameter.c Item_Give, z_inventory.c gUpgradeCapacities and
z_en_girla.c CanBuy_* / ItemGive_*. One refusal must change nothing; a
purchase gives and charges exactly once.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

(RUPEE_GREEN, RUPEE_BLUE, RUPEE_RED, RECOVERY_HEART, STICK, STICKS_5, STICKS_10,
 NUT, NUTS_5, NUTS_10, SWORD, SHIELD) = range(12)
SUCCESS, SUCCESS_FANFARE, NEED_RUPEES, CANT_GET_NOW = range(4)

HOST = r'''
#include "save_state.h"
int t_rupees(void) { return save_state.rupees; }
void t_set_rupees(int r) { save_state.rupees = (unsigned short)r; }
int t_sticks(void) { return save_state.stick_owned * 1000 + save_state.stick_ammo * 10 + save_state.stick_upgrade; }
int t_nuts(void) { return save_state.nut_owned * 1000 + save_state.nut_ammo * 10 + save_state.nut_upgrade; }
void t_set_health(int h, int cap) { save_state.health = h; save_state.health_capacity = cap; }
int t_health(void) { return save_state.health; }
'''


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class ItemGive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        host = pathlib.Path(cls.tmp.name) / 'host.c'
        host.write_text(HOST)
        out = pathlib.Path(cls.tmp.name) / 'item_give.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(out), '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/save_state.c'), str(host)], check=True, env=env)
        cls.lib = ctypes.CDLL(str(out))
        cls.lib.save_item_give.restype = ctypes.c_bool
        cls.lib.save_item_first_get.restype = ctypes.c_bool

    def setUp(self):
        self.lib.save_new_game()

    def test_rupees_clamp_at_the_child_wallet(self):
        self.lib.t_set_rupees(90)
        self.lib.save_item_give(RUPEE_BLUE)
        self.assertEqual(self.lib.t_rupees(), 95)
        self.lib.save_item_give(RUPEE_RED)
        self.assertEqual(self.lib.t_rupees(), 99)

    def test_first_stick_sets_one_then_clamps_at_ten(self):
        self.lib.save_item_give(STICK)
        self.assertEqual(self.lib.t_sticks(), 1011)
        for _ in range(20):
            self.lib.save_item_give(STICK)
        self.assertEqual(self.lib.t_sticks(), 1101)

    def test_first_sticks_5_sets_five(self):
        self.lib.save_item_give(STICKS_5)
        self.assertEqual(self.lib.t_sticks(), 1051)

    def test_nuts_capacity_is_twenty(self):
        self.lib.save_item_give(NUTS_10)
        self.assertEqual(self.lib.t_nuts(), 1101)
        self.lib.save_item_give(NUTS_10)
        self.lib.save_item_give(NUTS_5)
        self.assertEqual(self.lib.t_nuts(), 1201)

    def test_recovery_heart_heals_one_heart_up_to_capacity(self):
        self.lib.t_set_health(0x10, 0x30)
        self.lib.save_item_give(RECOVERY_HEART)
        self.assertEqual(self.lib.t_health(), 0x20)
        self.lib.t_set_health(0x28, 0x30)
        self.lib.save_item_give(RECOVERY_HEART)
        self.assertEqual(self.lib.t_health(), 0x30)

    def test_shield_needs_forty_and_charges_once(self):
        self.lib.t_set_rupees(39)
        self.assertEqual(self.lib.save_item_buy(SHIELD, 40), NEED_RUPEES)
        self.assertEqual(self.lib.t_rupees(), 39)
        self.lib.t_set_rupees(40)
        self.assertEqual(self.lib.save_item_buy(SHIELD, 40), SUCCESS_FANFARE)
        self.assertEqual(self.lib.t_rupees(), 0)
        self.lib.t_set_rupees(99)
        self.assertEqual(self.lib.save_item_buy(SHIELD, 40), CANT_GET_NOW)
        self.assertEqual(self.lib.t_rupees(), 99)

    def test_owned_check_precedes_money_like_source(self):
        self.lib.save_item_give(SHIELD)
        self.lib.t_set_rupees(0)
        self.assertEqual(self.lib.save_item_can_buy(SHIELD, 40), CANT_GET_NOW)

    def test_full_nuts_refused_and_money_kept(self):
        for _ in range(3):
            self.lib.save_item_give(NUTS_10)
        self.lib.t_set_rupees(50)
        self.assertEqual(self.lib.save_item_buy(NUTS_5, 15), CANT_GET_NOW)
        self.assertEqual(self.lib.t_rupees(), 50)

    def test_first_nuts_purchase_has_fanfare_then_plain(self):
        self.lib.t_set_rupees(99)
        self.assertEqual(self.lib.save_item_buy(NUTS_5, 15), SUCCESS_FANFARE)
        self.assertEqual(self.lib.save_item_buy(NUTS_5, 15), SUCCESS)
        self.assertEqual(self.lib.t_rupees(), 69)
        self.assertEqual(self.lib.t_nuts(), 1101)

    def test_heart_refused_at_full_health(self):
        self.lib.t_set_rupees(99)
        self.assertEqual(self.lib.save_item_buy(RECOVERY_HEART, 10), CANT_GET_NOW)
        self.lib.t_set_health(0x10, 0x30)
        self.assertEqual(self.lib.save_item_buy(RECOVERY_HEART, 10), SUCCESS)
        self.assertEqual(self.lib.t_rupees(), 89)


if __name__ == '__main__':
    unittest.main()
