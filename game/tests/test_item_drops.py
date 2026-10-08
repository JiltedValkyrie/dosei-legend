"""Original drop-table parity plus conditional child inventory branches."""
import ctypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path(shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe')
OOT=Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))
class Drop(ctypes.Structure):
    _fields_=[('item',ctypes.c_uint8),('count',ctypes.c_uint8)]
class Drops(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path=Path(cls.tmp.name)
        (path/'adapter.c').write_text('#include "save_state.h"\nvoid state(int h,int max,int sling,int seeds){save_new_game();save_state.health=h;save_state.health_capacity=max;save_state.slingshot=sling;save_state.ammo_seeds=seeds;}\nint hp(void){return save_state.health;}\nint nuts(void){return save_state.nut_ammo;}\nint seeds(void){return save_state.ammo_seeds;}\n')
        env=dict(os.environ);env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-fPIC','-O2','-I'+str(ROOT/'src'),str(path/'adapter.c'),
                        str(ROOT/'src/item_drop.c'),str(ROOT/'src/save_state.c'),'-o',str(path/'drop.dll')],check=True,env=env)
        cls.lib=ctypes.CDLL(str(path/'drop.dll'));cls.lib.item_drop_random.restype=Drop
        cls.lib.item_drop_give.restype=ctypes.c_bool
    def test_tables_match_original_ids_and_quantities(self):
        source=(OOT/'src/code/z_en_item00.c').read_text()
        ids={n:int(v,16) for v,n in re.findall(r'/\* 0x([0-9A-F]+) \*/ (ITEM00_\w+)',(OOT/'include/z_en_item00.h').read_text())}
        names=re.findall(r'\bITEM00_\w+',source.split('static u8 sItemDropIds[] = {')[1].split('};')[0])
        quantities=source.split('static u8 sDropQuantities[] = {')[1].split('};')[0]
        quantities=re.sub(r'//[^\n]*|/\*.*?\*/','',quantities,flags=re.S)
        actual=(ROOT/'src/item_drop_tables.h').read_text()
        table=actual.split('item_drop_ids[15][16] = {')[1].split('};')[0]
        self.assertEqual([ids[n] for n in names],[int(n,16) for n in re.findall(r'0x([0-9A-F]+)',table)])
        counts=actual.split('item_drop_quantities[15][16] = {')[1].split('};')[0]
        self.assertEqual(re.findall(r'\d+',quantities),re.findall(r'\d+',counts))
    def test_health_and_missing_inventory_filters(self):
        self.lib.state(48,48,0,0)
        self.assertEqual(0,self.lib.item_drop_filter(3))
        for item in (4,8,9,10,11,14,15,16,25):self.assertEqual(255,self.lib.item_drop_filter(item))
        self.lib.state(32,48,1,0)
        self.assertEqual(3,self.lib.item_drop_filter(3))
        self.assertEqual(16,self.lib.item_drop_filter(8))
    def test_enemy_tables_13_and_14_are_not_clamped_to_grass(self):
        self.lib.state(32,48,1,0)
        for table, roll, expected, count in ((13,0,16,1),(13,2,12,1),(13,4,13,1),(14,0,3,3),(14,2,16,1),(14,4,3,1)):
            drop=self.lib.item_drop_random(table,roll)
            self.assertEqual((drop.item,drop.count),(expected,count))
        a=self.lib.item_drop_random(15,0)
        b=self.lib.item_drop_random(0,0)
        self.assertEqual((a.item,a.count),(b.item,b.count))
    def test_flexible_fairy_and_health_quantities(self):
        self.lib.state(16,48,0,0)
        drop=self.lib.item_drop_random(0,11)
        self.assertEqual((254,1),(drop.item,drop.count))
        self.assertTrue(self.lib.item_drop_give(254));self.assertEqual(48,self.lib.hp())
        self.lib.state(32,48,0,0)
        drop=self.lib.item_drop_random(0,11)
        self.assertEqual((3,3),(drop.item,drop.count))
        self.lib.state(48,48,0,0)
        drop=self.lib.item_drop_random(0,11)
        self.assertEqual((0,3),(drop.item,drop.count))
    def test_nut_seed_quantities_and_no_seed_grant_without_slingshot(self):
        self.lib.state(48,48,0,0)
        self.assertFalse(self.lib.item_drop_give(16))
        self.assertTrue(self.lib.item_drop_give(12));self.assertEqual(5,self.lib.nuts())
        self.lib.state(48,48,1,29)
        self.assertTrue(self.lib.item_drop_give(16));self.assertEqual(30,self.lib.seeds())
if __name__=='__main__':unittest.main()
