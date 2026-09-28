"""Navi cutscene owns its source layer, not gameplay's differently placed cast."""
import pathlib
import re
import struct
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_actors as actors

class NaviCast(unittest.TestCase):
    def test_cutscene_header_actor_reader_uses_absolute_segment_pointers(self):
        blob=bytearray(128)
        struct.pack_into('>BBHI',blob,32,1,1,0,0x03000050)
        blob[40]=0x14
        struct.pack_into('>HhhhhhhH',blob,80,0x163,-641,120,454,0,29855,0,0xFF02)
        cast=actors.read_actors(blob,32)
        self.assertEqual(len(cast),1)
        self.assertEqual((cast[0]['x'],cast[0]['z'],cast[0]['var']),(-641,454,0xFF02))

    def test_exported_layer_seven_cast_and_cutscene_specific_placements(self):
        text=(ROOT/'build/generated/navi_npcs.h').read_text()
        rows=[tuple(map(int,r)) for r in re.findall(r'\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(\d+),\s*(\d+)\s*\}',text)]
        self.assertEqual(len(rows),8)
        self.assertEqual([r[4] for r in rows],[2,3,4,5,6,7,8,0])
        self.assertIn((-641,120,454,29855,4),rows)
        self.assertIn((-638,1,-165,25304,8),rows)
        for row in rows:
            b=(ROOT/'build/generated/npcs'/('NPC%02d.ANM'%row[4])).read_bytes()
            _,vertices,poses,ticks=struct.unpack_from('>4I',b)
            for x,y,z in struct.iter_unpack('>3h',b[16+2*ticks:]):
                self.assertLess(x*x+(y-40*64)**2+z*z,(80*64)**2,
                    'source pose must leave 20 units of culling sphere for tracking')
