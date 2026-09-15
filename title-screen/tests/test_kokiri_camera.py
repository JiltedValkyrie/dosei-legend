"""Run the actual portable collision and frustum C code against the shipped ROM data."""
import ctypes as C
import math
import os
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / 'src/scene'
DLL = ROOT / 'build/kokiri_camera_test.dll'
DLL.parent.mkdir(exist_ok=True)
os.environ["PATH"] = "C:/msys64/mingw64/bin;" + os.environ["PATH"]
adapter = ROOT/'build/camera_test_adapter.c'
adapter.write_text("""
#include <math.h>
#include <stdint.h>
#include "kokiri_collision.h"
int movement_calls, trig_calls;
void test_collision_move(camera_position_t *p, int32_t x, int32_t y, int32_t z);
void kokiri_collision_move(camera_position_t *p, int32_t x, int32_t y, int32_t z) {
    movement_calls++;
    test_collision_move(p,x,y,z);
}
void kokiri_camera_sincos(uint16_t yaw, int32_t *s, int32_t *c) {
    trig_calls++;
    double angle=yaw*6.283185307179586/65536.0;
    *s=(int32_t)round(sin(angle)*65536); *c=(int32_t)round(cos(angle)*65536);
}
""")
collision_object=ROOT/'build/camera_test_collision.o'
subprocess.run(['C:/msys64/mingw64/bin/gcc.exe', '-c', '-O2', '-Wall', '-Wextra', '-Werror',
                '-Dkokiri_collision_move=test_collision_move', str(SCENE/'kokiri_collision.c'),
                '-o', str(collision_object)], check=True)
subprocess.run(['C:/msys64/mingw64/bin/gcc.exe', '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I'+str(SCENE), str(collision_object), str(SCENE/'kokiri_clip.c'),
                str(SCENE/'kokiri_camera.c'), str(adapter), '-o', str(DLL)], check=True)
LIB = C.CDLL(str(DLL))

class Position(C.Structure):
    _fields_ = [('x',C.c_int32),('y',C.c_int32),('z',C.c_int32)]
class Triangle(C.Structure):
    _fields_ = [('values',C.c_int16*18)]
class ClipVertex(C.Structure):
    _fields_ = [(k,C.c_int32) for k in ('x','y','z','b','c')]

LIB.kokiri_collision_init.argtypes = [C.POINTER(Triangle),C.c_uint32]
LIB.kokiri_collision_clear.argtypes = [Position]
LIB.kokiri_collision_clear.restype = C.c_bool
LIB.kokiri_collision_spawn.argtypes = [C.POINTER(Position)]
LIB.kokiri_collision_spawn.restype = C.c_bool
LIB.kokiri_collision_move.argtypes = [C.POINTER(Position),C.c_int32,C.c_int32,C.c_int32]
LIB.kokiri_clip_frustum.argtypes = [C.POINTER(ClipVertex),C.POINTER(ClipVertex),C.POINTER(C.c_bool)]
LIB.kokiri_clip_frustum.restype = C.c_int
LIB.kokiri_clip_texture.argtypes = [C.POINTER(C.c_uint8), C.c_uint,
    C.POINTER(ClipVertex), C.POINTER(C.c_uint8)]
LIB.kokiri_project_offset.argtypes = [C.c_int32, C.c_int32]
LIB.kokiri_project_offset.restype = C.c_int32
LIB.kokiri_camera_update.argtypes = [C.POINTER(Position), C.POINTER(C.c_uint16),
                                    C.POINTER(C.c_int32), C.c_uint16, C.c_bool]
DATA = (ROOT/'cd/FOREST.BIN').read_bytes()
H = struct.unpack_from('>9I3i4I',DATA)
COLLISION = (Triangle*H[15])(*[Triangle((C.c_int16*18)(*struct.unpack_from('>18h',DATA,H[14]+i*36))) for i in range(H[15])])
VERTS = [struct.unpack_from('>3h',DATA,H[4]+i*6) for i in range(H[2])]
FACES = [struct.unpack_from('>4HIIHH',DATA,H[5]+i*20) for i in range(H[3])]


def synthetic(vertices,normal):
    return Triangle((C.c_int16*18)(*[n for v in vertices for n in v],*normal,
                    *[min(v[i] for v in vertices) for i in range(3)],
                    *[max(v[i] for v in vertices) for i in range(3)]))


def clip(points):
    guarded = (ClipVertex*14)()
    for i in (0,13):
        guarded[i] = ClipVertex(*([0x13579BDF]*5))
    out = C.cast(C.byref(guarded,C.sizeof(ClipVertex)),C.POINTER(ClipVertex))
    changed = C.c_bool()
    n = LIB.kokiri_clip_frustum((ClipVertex*3)(*[ClipVertex(*p,0,0) for p in points]),out,C.byref(changed))
    assert 0 <= n <= 12, f'Invalid clip count: {n}'
    for i in (0,13):
        assert all(getattr(guarded[i],k)==0x13579BDF for k in ('x','y','z','b','c')), 'Clip output overrun'
    # Copy values: the cast pointer does not own the guarded allocation.
    return [ClipVertex.from_buffer_copy(out[i]) for i in range(n)],changed.value


class CameraTests(unittest.TestCase):
    def setUp(self):
        LIB.kokiri_collision_init(COLLISION,len(COLLISION))

    def test_hidden_title_idle_and_start_hold_do_no_movement_work(self):
        p=Position(-300,91,0); yaw=C.c_uint16(900); pitch=C.c_int32(0)
        moves=C.c_int.in_dll(LIB,'movement_calls'); trig=C.c_int.in_dll(LIB,'trig_calls')
        moves.value=trig.value=0
        for _ in range(10000):
            for buttons in (0,0x0800):
                LIB.kokiri_camera_update(C.byref(p),C.byref(yaw),C.byref(pitch),buttons,False)
        self.assertEqual(moves.value,0)
        self.assertEqual(trig.value,0)
        self.assertEqual((p.x,p.y,p.z,yaw.value,pitch.value),(-300,91,0,900,0))

    def test_manual_controls_and_title_mode(self):
        p=Position(-300,91,0); yaw=C.c_uint16(0); pitch=C.c_int32(0)
        def update(buttons,title=False):
            LIB.kokiri_camera_update(C.byref(p),C.byref(yaw),C.byref(pitch),buttons,title)
        update(0x1000)
        self.assertEqual((p.x,p.z),(-300,16))
        update(0x8000)
        self.assertEqual((p.x,p.z),(-284,16))
        update(0x80); self.assertEqual(yaw.value,360)
        update(0x08); self.assertEqual(yaw.value,0)
        update(0x40); self.assertEqual(p.y,107)
        update(0x10); self.assertEqual(p.y,91)
        update(0x1020); self.assertEqual(pitch.value,240)
        self.assertEqual((p.x,p.z),(-284,16))
        update(0x0200); self.assertEqual(pitch.value,0)
        update(0x1040,True)
        self.assertEqual((p.x,p.y,p.z,yaw.value),(-284,91,16,90))

    def test_shoulders_turn_oppositely_through_wraparound(self):
        for start in (0,100,32768,65400):
            for buttons,delta in ((0x08,-360),(0x80,360),(0x88,0)):
                p=Position(-300,91,0); yaw=C.c_uint16(start); pitch=C.c_int32(0)
                for _ in range(200):
                    LIB.kokiri_camera_update(C.byref(p),C.byref(yaw),C.byref(pitch),buttons,False)
                self.assertEqual(yaw.value,(start+200*delta)&65535)

    def test_all_pad_combinations_are_bounded(self):
        for buttons in range(0,65536,8):
            p=Position(-300,91,0); yaw=C.c_uint16(900); pitch=C.c_int32(0)
            LIB.kokiri_camera_update(C.byref(p),C.byref(yaw),C.byref(pitch),buttons,False)
            self.assertLessEqual(abs(p.x+300),17)
            self.assertLessEqual(abs(p.z),17)
            self.assertLessEqual(abs(p.y-91),16)
            self.assertTrue(LIB.kokiri_collision_clear(p))

    def test_verified_scene_collision_and_spawn(self):
        self.assertEqual(H[1],2)
        self.assertEqual(len(COLLISION),1692)
        p = Position()
        self.assertTrue(LIB.kokiri_collision_spawn(C.byref(p)))
        self.assertTrue(LIB.kokiri_collision_clear(p))
        self.assertEqual((p.x,p.y,p.z),(-300,91,0))
        LIB.kokiri_collision_move(C.byref(p),0,-1000,0)
        self.assertEqual(p.y,91)
        print('Collision-validated spawn:',p.x,p.y,p.z)

    def test_swept_wall_and_edge_collision(self):
        wall = synthetic([(0,-1000,-1000),(0,1000,-1000),(0,0,1000)],(16384,0,0))
        LIB.kokiri_collision_init(C.byref(wall),1)
        p = Position(-100,0,0)
        LIB.kokiri_collision_move(C.byref(p),1000,0,0)
        self.assertLessEqual(p.x,-24)
        self.assertTrue(LIB.kokiri_collision_clear(p))
        LIB.kokiri_collision_move(C.byref(p),50,0,40)
        self.assertEqual(p.z,40)
        self.assertFalse(LIB.kokiri_collision_clear(Position(0,0,1005)))

    def test_ceiling_blocks_vertical_flight(self):
        ceiling = synthetic([(-1000,200,-1000),(0,200,1000),(1000,200,-1000)],(0,-16384,0))
        LIB.kokiri_collision_init(C.byref(ceiling),1)
        p = Position(0,90,0)
        LIB.kokiri_collision_move(C.byref(p),0,1000,0)
        self.assertLessEqual(p.y,176)
        self.assertTrue(LIB.kokiri_collision_clear(p))

    def test_scene_movement_stays_clear(self):
        for dx,dz in ((8,0),(-8,0),(0,8),(0,-8),(6,6)):
            p = Position(-300,90,0)
            for _ in range(120):
                LIB.kokiri_collision_move(C.byref(p),dx,0,dz)
                self.assertTrue(LIB.kokiri_collision_clear(p))

    def test_frustum_extremes(self):
        cases = [[(-10000,-100,1),(10000,-100,1),(0,10000,200)],
                 [(-100,-100,-1),(100,-100,-1),(0,100,-1)],
                 [(-80,-80,200),(80,-80,200),(0,80,200)]]
        for points in cases:
            out,changed = clip(points)
            self.assertLessEqual(len(out),8)
            for p in out:
                self.assertGreaterEqual(p.z,20)
                self.assertLessEqual(abs(p.b)+abs(p.c),65538)
                self.assertTrue(-20 <= 160+p.x*240/p.z <= 340)
                self.assertTrue(-20 <= 120-p.y*240/p.z <= 260)
        self.assertEqual(len(clip(cases[1])[0]),0)
        self.assertFalse(clip(cases[2])[1])

    def test_projection_signed_coordinates(self):
        for coordinate in (-25000,-1000,-1,0,1,1000,25000):
            for z in (20,31,240,20000):
                self.assertEqual(LIB.kokiri_project_offset(coordinate,z),int(coordinate*240/z))

    def test_idle_rotation_clipping_buffers(self):
        # The new user crash occurred without input after clipping returned.
        # Exercise a full revolution in the same 90-unit yaw steps as title mode.
        # This checks native buffer bounds, not SH-2 interrupts or VDP1 behavior.
        for yaw in range(0,65536,90):
            ys,yc=math.sin(yaw*math.tau/65536),math.cos(yaw*math.tau/65536)
            points=[(int((x+300)*yc-z*ys),y-91,int(z*yc+(x+300)*ys)) for x,y,z in VERTS]
            for face in FACES:
                poly,_=clip([points[i] for i in face[:3]])
                self.assertLessEqual(len(poly),8)
                for p in poly:
                    self.assertGreaterEqual(p.z,20)

    def test_clipped_texture_matches_barycentric_reference(self):
        points=[(-180,-100,180),(100,-100,180),(0,200,10)]
        poly,changed=clip(points)
        self.assertTrue(changed)
        for size in (16,32):
            indices=[(x+3*y)%16 for y in range(size) for x in range(size)]
            source=(C.c_uint8*(size*size//2))(*[(indices[i]<<4)|indices[i+1] for i in range(0,len(indices),2)])
            for first in range(1,len(poly)-1,2):
                quad=[poly[0],poly[first],poly[first+1],poly[min(first+2,len(poly)-1)]]
                tile=(C.c_uint8*130)(*[0xAB]*130)
                LIB.kokiri_clip_texture(source,size,(ClipVertex*4)(*quad),tile)
                self.assertEqual(list(tile)[128:],[0xAB,0xAB])
                for y in range(16):
                    for x in range(16):
                        u,v=x/15,y/15
                        b=sum(p.b*w for p,w in zip(quad,((1-u)*(1-v),u*(1-v),u*v,(1-u)*v)))
                        c=sum(p.c*w for p,w in zip(quad,((1-u)*(1-v),u*(1-v),u*v,(1-u)*v)))
                        sx=0 if c>=65536 else min(size-1,max(0,round(b*(size-1)/(65536-c))))
                        sy=min(size-1,max(0,round(c*(size-1)/65536)))
                        # Integer interpolation can move a sample across a half-texel boundary.
                        actual=(tile[y*8+x//2] >> (0 if x&1 else 4))&15
                        neighbors={indices[yy*size+xx] for yy in range(max(0,sy-1),min(size,sy+2))
                                   for xx in range(max(0,sx-1),min(size,sx+2))}
                        self.assertIn(actual,neighbors)

    def test_full_camera_sweep_command_and_texture_budgets(self):
        max_commands = max_clipped = 0
        total_fast = total_clipped = total_rejected = 0
        for camera in ((-300,90,0),(-600,150,-300),(0,300,0)):
            for pitch in (-65,0,65):
                ps,pc = math.sin(math.radians(pitch)),math.cos(math.radians(pitch))
                for yaw in range(0,360,15):
                    ys,yc = math.sin(math.radians(yaw)),math.cos(math.radians(yaw))
                    points = []
                    for v in VERTS:
                        x,y,z = [v[i]-camera[i] for i in range(3)]
                        rx,rz = x*yc-z*ys,z*yc+x*ys
                        points.append((round(rx),round(y*pc-rz*ps),round(rz*pc+y*ps)))
                    projections=[(160+int(x*240/z),120-int(y*240/z)) if z>=20 else None for x,y,z in points]
                    commands = clipped = 0
                    for face in FACES:
                        triangle=[points[i] for i in face[:3]]
                        distances=lambda p:(p[2]-20,p[0]*240+p[2]*160,p[2]*159-p[0]*240,
                                             p[2]*120-p[1]*240,p[2]*119+p[1]*240)
                        if any(all(distances(p)[plane]<0 for p in triangle) for plane in range(5)):
                            total_rejected+=1
                            continue
                        safe=all(projections[i] is not None and -160<=projections[i][0]<=479 and
                                 -120<=projections[i][1]<=359 for i in face[:3])
                        if safe:
                            poly=[ClipVertex(*p,0,0) for p in triangle]; changed=False
                        else:
                            poly,changed = clip(triangle)
                        for first in range(1,len(poly)-1,2):
                            quad = [poly[0],poly[first],poly[first+1],poly[min(first+2,len(poly)-1)]]
                            p = [(160+int(v.x*240/v.z),120-int(v.y*240/v.z)) for v in quad]
                            area = sum(p[i][0]*p[(i+1)%4][1]-p[i][1]*p[(i+1)%4][0] for i in range(4))
                            if area == 0 or (face[7]&2 and area <= 0):continue
                            commands += 1
                            clipped += changed
                            total_fast += not changed
                            total_clipped += changed
                    max_commands = max(max_commands,commands)
                    max_clipped = max(max_clipped,clipped)
        self.assertLess(max_commands+3,3072)
        self.assertLessEqual(max_clipped,256)
        self.assertLess(3072*32+256*128+H[7]+32,512*1024)
        print('Sweep peak commands / clipped tiles:',max_commands,max_clipped)
        print('Sweep original tiles / resampled tiles / rejected faces:',total_fast,total_clipped,total_rejected)


if __name__ == '__main__':
    unittest.main()
