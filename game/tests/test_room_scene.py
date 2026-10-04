import json
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_hybrid_scene as hybrid
import build_room_scene as rooms
import build_sgl_scene as scene
import asset_names


class RoomFormatTests(unittest.TestCase):
    def test_binary_layout_keeps_geometry_material_and_object_bindings(self):
        vertices = [(0,0,0),(8,0,0),(8,0,8),(0,0,8)]
        faces = [dict(idx=(0,1,2,3),tex_off=0,cull=True,mesh=True)]
        tiles = {0:dict(index=0,width=8,height=2,pixels=bytes(range(8)),clut=(0,)*16)}
        records = [dict(object=7,indices=[0,1,2,3])]
        blob,pixels,bounds = rooms.pack_room(vertices,faces,tiles,records,scene.face_normal)
        self.assertEqual(struct.unpack_from('>8I',blob),(0x4b524d31,4,1,1,8,1,0,0))
        self.assertEqual(struct.unpack_from('>3i',blob,32+12),(8*65536,0,0))
        self.assertEqual(struct.unpack_from('>BB5H',blob,32+48+20),(0,0x67,0,0x188,0,0,2))
        self.assertEqual(struct.unpack_from('>HHII',blob,112),(8,2,0,8))
        self.assertEqual(bounds,[(0,0,0,8,0,8)])
        self.assertEqual(len(blob),32+48+32+44+4+24)
        self.assertEqual(pixels,bytes(range(8)))

    def test_streamed_floor_sort_tag_matches_resident_rule(self):
        cases = [
            ([(0,0,0),(0,0,128),(128,0,128),(128,0,0)], 0x66),
            ([(0,0,0),(32,0,0),(32,0,32),(0,0,32)], 0x67),
            ([(0,0,0),(128,0,0),(128,128,0),(0,128,0)], 0x67),
            ([(0,0,0),(128,0,0),(128,0,128),(0,0,128)], 0x67),
        ]
        for vertices, expected in cases:
            for flat in (False, True):
                face=dict(idx=(0,1,2,3),tex_off=0,cull=True,mesh=False)
                if flat: face['colour']=0x8123
                tiles={0:dict(index=0,width=8,height=2,pixels=bytes(8),clut=(0,)*16)}
                blob,_,_=rooms.pack_room(vertices,[face],tiles,
                    [dict(object=0,indices=[0,1,2,3])],scene.face_normal)
                self.assertEqual(blob[32+48+20+1],expected,(vertices,flat))

    def test_triangle_to_quads_preserves_area_winding_and_source_mapping(self):
        points = [(0,0,0,0,0,127,0,0,255),(180,0,0,36,0,127,0,0,255),
                  (0,0,240,0,48,127,0,0,255)]
        group = dict(points=points,source=[497],tri=dict(vertices=points),size=300)
        parts = hybrid.triangle_quads(group)
        self.assertEqual(len(parts),3)
        area = 0
        for part in parts:
            p = part['points']
            self.assertEqual(len(set(v[:3] for v in p)),4)
            signed = sum(p[i][0]*p[(i+1)%4][2]-p[(i+1)%4][0]*p[i][2] for i in range(4))
            self.assertGreater(signed,0)
            area += signed/2
            self.assertEqual(part['source'],[497])
            for v in p:
                self.assertAlmostEqual(v[3],v[0]/5)
                self.assertAlmostEqual(v[4],v[2]/5)
        self.assertAlmostEqual(area,180*240/2)


@unittest.skipUnless((ROOT/'build/generated/rooms_manifest.json').is_file(),'room banks not generated')
class GeneratedRoomsTests(unittest.TestCase):
    def test_room_banks_cover_all_source_faces_and_fit_independently(self):
        gen = ROOT/'build/generated'
        meta = json.loads((gen/'rooms_manifest.json').read_text())
        coverage = []
        for room in meta['rooms']:
            if room.get('streamed'):
                self.assertTrue((gen/asset_names.room_asset(room['scene'],room['id'],'STM')).is_file())
                self.assertTrue((gen/'field_stream_report.json').is_file())
                continue  # Field pieces/capacity have their own stream regression.
            stem = 'S%dR%d' % (room['scene'], room['id'])
            detail_path = gen/(stem.lower()+'/texture_manifest.json')
            if not room['budget']:  # generic banks are copied from the all-scenes bake
                detail_path = ROOT/'build/all-scenes'/('%s_room_%d'%(room['prefix'],room['id']))/'texture_manifest.json'
            detail = json.loads(detail_path.read_text())
            if room['prefix'] == 'spot04':
                coverage.append({s for f in detail['faces'] for s in f['source']})
            blob = (gen/asset_names.room_asset(room['scene'],room['id'],'MSH')).read_bytes()
            magic,nv,np,nt,nb,no,_,_ = struct.unpack_from('>8I',blob)
            self.assertEqual(magic,0x4b524d31)
            self.assertEqual(len(blob),32+nv*12+np*32+nt*44+((np+3)&~3)+no*24)
            self.assertEqual(nb,(gen/asset_names.room_asset(room['scene'],room['id'],'TEX')).stat().st_size)
            self.assertLessEqual(np+517,2600)
            self.assertLessEqual(nv+309,2500)
            self.assertLessEqual(sum(p['bytes'] for p in detail['budget'])+512,detail['vram_limit'])
            for i in range(np):
                indices = struct.unpack_from('>4H',blob,32+nv*12+i*20+12)
                self.assertLess(max(indices),nv)
                attr = struct.unpack_from('>BB5H',blob,32+nv*12+np*20+i*12)
                self.assertLess(attr[2],nt)
                baked = [tuple(v//65536 for v in struct.unpack_from('>3i',blob,32+j*12))
                         for j in indices]
                normal = struct.unpack_from('>3i',blob,32+nv*12+i*20)
                expected = 0x66 if scene.floor_uses_far_sort(baked,range(4),normal) else 0x67
                self.assertEqual(attr[1],expected)
                self.assertEqual(bool(attr[3]&0x100),detail['faces'][i]['mesh'])
        self.assertEqual(set.union(*coverage),set(range(2128)))
        self.assertEqual(sum(map(len,coverage)),2128)
