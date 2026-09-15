"""Validate the shipped CD scene; generate a host preview of its baked tiles."""
import math
import struct
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from PIL import Image
from build_kokiri_scene import coordinate, rgba16

ROOT = Path(__file__).resolve().parents[1]
DATA = (ROOT / 'cd/FOREST.BIN').read_bytes()
H = struct.unpack_from('>9I3i4I', DATA)
VERTS = [struct.unpack_from('>3h', DATA, H[4]+6*i) for i in range(H[2])]
FACES = [struct.unpack_from('>4HIIHH', DATA, H[5]+20*i) for i in range(H[3])]


CAMERA = (-300, 91, 0)
NEAR = 20


def camera_vertices(angle):
    result = []
    for p in VERTS:
        x,y,z = [p[i]-CAMERA[i] for i in range(3)]
        result.append((x*math.cos(angle)-z*math.sin(angle), y,
                       z*math.cos(angle)+x*math.sin(angle)))
    return result


def project_point(p):
    return (max(-1024,min(1023,160+p[0]*240/p[2])),
            max(-1024,min(1023,120-p[1]*240/p[2])), *p[2:])


def clip_polygon(points):
    planes = [lambda p:p[2]-NEAR, lambda p:p[0]*240+p[2]*160,
              lambda p:p[2]*159-p[0]*240, lambda p:p[2]*120-p[1]*240,
              lambda p:p[2]*119+p[1]*240]
    for distance in planes:
        out = []
        for i,b in enumerate(points):
            a = points[i-1]
            da,db = distance(a),distance(b)
            if (da >= 0) != (db >= 0):
                t = da/(da-db)
                out.append(tuple(a[j]+t*(b[j]-a[j]) for j in range(len(a))))
            if db >= 0:
                out.append(b)
        points = out
    return points


def preview(angle):
    image = Image.new('RGB', (320,240), (44,65,75))
    pixels = image.load()
    points = camera_vertices(angle)
    for face in sorted(FACES, key=lambda f:sum(points[i][2] for i in f[:3]), reverse=True):
        polygon = clip_polygon([(*points[index],int(i==1),int(i==2)) for i,index in enumerate(face[:3])])
        polygon = [project_point(p) for p in polygon]
        for j in range(1,len(polygon)-1):
            a,b,c = polygon[0],polygon[j],polygon[j+1]
            area = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            if abs(area) < .01 or (face[7]&2 and area <= 0):
                continue
            size = face[6]&255
            clut = struct.unpack_from('>16H', DATA, H[6]+face[5])
            for y in range(max(0,math.floor(min(a[1],b[1],c[1]))), min(240,math.ceil(max(a[1],b[1],c[1])))):
                for x in range(max(0,math.floor(min(a[0],b[0],c[0]))), min(320,math.ceil(max(a[0],b[0],c[0])))):
                    wb = ((x+.5-a[0])*(c[1]-a[1])-(y+.5-a[1])*(c[0]-a[0]))/area
                    wc = ((b[0]-a[0])*(y+.5-a[1])-(b[1]-a[1])*(x+.5-a[0]))/area
                    if wb < 0 or wc < 0 or wb+wc > 1 or (face[7]&1 and (x+y)&1):
                        continue
                    original_b = (1-wb-wc)*a[3]+wb*b[3]+wc*c[3]
                    original_c = (1-wb-wc)*a[4]+wb*b[4]+wc*c[4]
                    u = original_b / max(1e-9,1-original_c)
                    pos = min(size-1,round(original_c*(size-1)))*size + min(size-1,round(u*(size-1)))
                    packed = DATA[H[6]+face[4]+pos//2]
                    index = (packed >> (0 if pos&1 else 4)) & 15
                    if index:
                        color = clut[index]
                        pixels[x,y] = tuple(((color >> shift)&31)*255//31 for shift in (0,5,10))
    return image


class SceneTests(unittest.TestCase):
    def test_binary_layout_and_memory(self):
        self.assertEqual(H[:2], (0x4B465231,2))
        self.assertEqual(H[3],2060)
        self.assertEqual(len(DATA),H[8])
        self.assertEqual(H[6]+H[7],len(DATA))
        self.assertEqual(H[15],1692)
        self.assertLessEqual(H[14]+H[15]*36,H[6])
        self.assertLess(H[7]+3072*32+32+256*128,512*1024)
        self.assertLess((len(DATA)+2047)&~2047,1024*1024)
        for f in FACES:
            self.assertTrue(all(i < len(VERTS) for i in f[:4]))
            self.assertEqual(f[2],f[3])
            self.assertIn(f[6],(0x0210,0x0420))
            self.assertEqual(f[4]%8,0)
            self.assertEqual(f[5]%8,0)
            self.assertLessEqual(f[4]+(f[6]&255)**2//2,H[7])
            self.assertLessEqual(f[5]+32,H[7])

    def test_texture_addressing(self):
        self.assertEqual(coordinate(-1,1,0,0,0,3,8),7)
        self.assertEqual(coordinate(8,1,0,0,1,3,8),7)
        self.assertEqual(coordinate(15,1,0,0,1,3,8),0)
        self.assertEqual(coordinate(99,1,0,0,2,3,8),7)
        self.assertEqual(coordinate(8,1,1,4,0,3,8),3)
        self.assertEqual(rgba16(0xF801),(255,0,0,255))


if __name__ == '__main__':
    output = ROOT / 'build/kokiri-preview.png'
    output.parent.mkdir(exist_ok=True)
    sheet = Image.new('RGB',(640,480))
    for i in range(4):
        sheet.paste(preview(i*math.pi/2),((i%2)*320,(i//2)*240))
    sheet.save(output)
    unittest.main()
