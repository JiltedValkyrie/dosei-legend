"""Verify baked drawbridge cutouts and source-based torch animation banks."""
import pathlib
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class CutsceneProps(unittest.TestCase):
    def bank(self,name):
        blob=(ROOT/'build/generated'/name).read_bytes()
        header=struct.unpack_from('>9I3i4I',blob)
        self.assertEqual(header[8],len(blob))
        result=[]
        for i in range(header[3]):
            r=struct.unpack_from('>4HIIHH',blob,header[5]+20*i)
            size=(r[6]>>8)*8*(r[6]&255)//2
            pixels=blob[header[6]+r[4]:header[6]+r[4]+size]
            self.assertEqual(len(pixels),size)
            indices=[n for v in pixels for n in (v>>4,v&15)]
            self.assertTrue(r[7]&1,'VDP1 must skip transparent pixel zero')
            self.assertIn(0,indices)
            self.assertTrue(any(indices))
            result.append(pixels)
        return header,result

    def test_chain_holes_remain_transparent_and_metal_remains_visible(self):
        h,tiles=self.bank('CHAINS.BIN')
        self.assertEqual(h[3],6)

    def test_fire_has_32_distinct_scroll_phases_and_source_scale(self):
        h,tiles=self.bank('GATEFIRE.BIN')
        self.assertEqual((h[2],h[3]),(4,32))
        self.assertEqual(len(set(tiles)),32)
        blob=(ROOT/'build/generated/GATEFIRE.BIN').read_bytes()
        points=list(struct.iter_unpack('>3h',blob[h[4]:h[4]+24]))
        self.assertEqual(max(p[0] for p in points)-min(p[0] for p in points),64)
        self.assertEqual(max(p[1] for p in points)-min(p[1] for p in points),128)
