"""Validate ROM exporters in temporary directories, never the mounted disc."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
OOT=Path('D:/Workspace-Claude/game-decomps/n64/oot')

@unittest.skipUnless((OOT/'assets/xml/objects/object_box.xml').exists(),'OoT assets required')
class WorldPropAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.out=Path(cls.tmp.name)/'cd'
        subprocess.run([sys.executable,str(ROOT/'tools/build_world_props.py'),'--out',str(cls.out)],
                       check=True,capture_output=True)
        sys.path.insert(0,str(ROOT/'tools'))
        from build_shop_props import static_mesh
        for obj,symbol,name in [('object_gi_nuts','gGiNutDL','NUT'),
                                ('object_gi_heart','gGiRecoveryHeartDL','HEART')]:
            static_mesh(OOT,None,obj,symbol,cls.out/(name+'.BIN'),.25)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_models_have_valid_indices_and_texture_extents(self):
        for file in self.out.glob('*.BIN'):
            data=file.read_bytes()
            magic,version,vertices,faces,vo,ro,to,tb=struct.unpack_from('>4s7I',data)
            self.assertEqual(magic,b'KFR1',file.name)
            self.assertEqual(len(data),to+tb,file.name)
            self.assertGreater(vertices,0)
            for i in range(faces):
                at=ro+i*20
                self.assertLess(max(struct.unpack_from('>4H',data,at)),vertices)
                pixel,clut,size=struct.unpack_from('>IIH',data,at+8)
                self.assertLessEqual(pixel+(size>>8)*8*(size&255)//2,tb)
                self.assertLessEqual(clut+32,tb)

    def test_counter_preserves_backdrop_material_variation(self):
        from build_interior_masks import build_shop_counter
        backdrop=ROOT/'build/cd/S2R0.RGB'
        if not backdrop.exists(): self.skipTest('shop backdrop required')
        dest=self.out/'COUNTER.BIN'
        build_shop_counter(OOT,None,backdrop.read_bytes(),dest)
        data=dest.read_bytes()
        faces,records=struct.unpack_from('>I',data,12)[0],struct.unpack_from('>I',data,20)[0]
        tiles={struct.unpack_from('>I',data,records+20*i+8)[0] for i in range(faces)}
        self.assertGreater(len(tiles),8)  # catches UVs clamped to a single pixel

    def test_flat_shop_items_use_only_solid_colour_tiles(self):
        from build_shop_props import static_mesh, ITEMS
        for name,obj,symbol in ITEMS:
            dest=self.out/('FLAT'+name)
            static_mesh(OOT,None,obj,symbol,dest,.25,flat=True)
            data=dest.read_bytes()
            count,records=struct.unpack_from('>I',data,12)[0],struct.unpack_from('>I',data,20)[0]
            for face in range(count):
                self.assertEqual(struct.unpack_from('>H',data,records+20*face+16)[0],0x0102)
            self.assertFalse(dest.with_suffix('.SCR').exists())

    def test_chest_has_distinct_closed_and_open_source_poses(self):
        data=(self.out/'CHEST.ANM').read_bytes()
        magic,vertices,poses,ticks=struct.unpack_from('>4s3I',data)
        self.assertEqual(magic,b'CVA1')
        self.assertEqual(len(data),16+ticks*2+poses*vertices*6)
        indices=struct.unpack_from('>%dH'%ticks,data,16)
        self.assertNotEqual(indices[0],indices[-1])
        self.assertLess(max(indices),poses)
        self.assertGreater(poses,20)

    def test_scroll_frames_match_runtime_layout_and_actually_change(self):
        for name in ('NUT','HEART'):
            data=(self.out/(name+'.SCR')).read_bytes()
            mesh=(self.out/(name+'.BIN')).read_bytes()
            magic,frames,faces=struct.unpack_from('>4sII',data)
            self.assertEqual((magic,frames),(b'KTS1',32))
            count,records=struct.unpack_from('>I',mesh,12)[0],struct.unpack_from('>I',mesh,20)[0]
            indices=struct.unpack_from('>%dI'%faces,data,12)
            self.assertEqual(len(set(indices)),faces)
            self.assertLess(max(indices),count)
            for face in indices:
                self.assertEqual(struct.unpack_from('>H',mesh,records+20*face+16)[0],0x0210)
            start=12+faces*4;stride=faces*160
            self.assertEqual(len(data),start+frames*stride)
            self.assertGreater(len({data[start+i*stride:start+(i+1)*stride] for i in range(frames)}),8)
            if name=='NUT': self.assertLess(faces,count)  # body stays still; cap scrolls

if __name__=='__main__': unittest.main()
