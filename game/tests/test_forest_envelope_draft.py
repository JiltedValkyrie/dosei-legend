"""Production envelope proof: candidates contain every original visible face."""
import os
import re
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env
from test_graphics_backend import ROOT, function
from build_actor_packs import Elf32


def trig_memory():
    """Read current linked SH ELF/COFF; permit an objdump-only checkout too."""
    required = {'_sin_index_tbl', '_cos_index_tbl', '_sin_tbl'}
    supplied = os.environ.get('DOSEI_FOREST_TRIG_ELF')
    elfs = [Path(supplied)] if supplied else sorted(
        (ROOT / 'build').glob('*.elf'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in elfs:
        if not path.exists():
            continue
        data = path.read_bytes()
        sections = []
        if data.startswith(b'\x7fELF'):
            elf = Elf32(path)
            symbols = {row['name']: row['value'] for row in elf.symbols
                       if row['section'] and row['name'] in required}
            sections = [(row[3], elf.section_data(index))
                        for index, row in enumerate(elf.sections) if row[1] != 8]
        elif data.startswith(b'\x05\x00'):  # Jo names its SH COFF executable .elf.
            _, count, _, sym_at, sym_count, optional, _ = struct.unpack_from('>HHIIIHH', data)
            strings = sym_at + sym_count * 18
            symbols = {}
            index = 0
            while index < sym_count:
                at = sym_at + index * 18
                name = data[at:at + 8]
                if name[:4] == b'\0' * 4:
                    offset = strings + int.from_bytes(name[4:], 'big')
                    name = data[offset:data.index(0, offset)]
                else:
                    name = name.split(b'\0', 1)[0]
                value, section, _, _, aux = struct.unpack_from('>IhHBB', data, at + 8)
                name = name.decode()
                if section > 0 and name in required:
                    symbols[name] = value
                index += aux + 1
            for index in range(count):
                at = 20 + optional + index * 40
                _, _, address, size, offset, _, _, _, _, _ = struct.unpack_from('>8sIIIIIIHHI', data, at)
                if offset:
                    sections.append((address, data[offset:offset + size]))
        else:
            continue
        if symbols.keys() != required:
            continue
        base = min(symbols.values())
        end = symbols['_sin_tbl'] + 0x4004
        memory = bytearray(end - base)
        for address, contents in sections:
            start, stop = max(base, address), min(end, address + len(contents))
            if start < stop:
                memory[start - base:stop - base] = contents[start - address:stop - address]
        return symbols, base, memory
    for path in sorted((ROOT / 'build').glob('*.dis'),
                       key=lambda p: p.stat().st_mtime, reverse=True):
        text = path.read_text()
        symbols = {name: int(address, 16) for address, name in
                   re.findall(r'^([0-9a-f]+) <(_(?:sin|cos)_index_tbl|_sin_tbl)>:', text, re.M)}
        if symbols.keys() != required:
            continue
        base = min(symbols.values())
        memory = bytearray(symbols['_sin_tbl'] + 0x4004 - base)
        for address, a, b in re.findall(r'^\s*([0-9a-f]+):\s*([0-9a-f]{2}) ([0-9a-f]{2})\s', text, re.M):
            at = int(address, 16) - base
            if 0 <= at < len(memory) - 1:
                memory[at:at + 2] = bytes((int(a, 16), int(b, 16)))
        return symbols, base, memory
    raise unittest.SkipTest('SGL trig proof needs a linked Saturn host ELF/dis in game/build; '
                            'build Debug or set DOSEI_FOREST_TRIG_ELF to its ELF')


def linked_trig():
    """Decode the actual slSin/slCos table records from the target disassembly.

    The linked SH-2 routines xor a signed byte into the angle, mask 0x3ffe,
    load a table word, then xor/add signed bytes from their octant record.
    Missing objdump bytes (the '...' compression) are zero initialized.
    """
    symbols, base, memory = trig_memory()

    def signed(n):
        return n if n < 128 else n - 256

    def value(name, angle):
        record = symbols[name] - base + (angle >> 13) * 8
        pointer = int.from_bytes(memory[record:record + 4], 'big')
        index = (angle ^ signed(memory[record + 6])) & 0x3ffe
        offset = pointer - base + index
        if not 0 <= offset < len(memory) - 1:
            raise ValueError('SGL trig record outside expected table')
        word = int.from_bytes(memory[offset:offset + 2], 'big')
        return (word ^ signed(memory[record + 4])) + signed(memory[record + 5])

    return ([value('_sin_index_tbl', angle) for angle in range(65536)],
            [value('_cos_index_tbl', angle) for angle in range(65536)])


PROGRAM = r'''
#include <stdio.h>
#include <limits.h>
#include <stdlib.h>
#include "forest_envelope.h"
#include "trig.h"
#define CHECK(c) do {if(!(c)){printf("line %d: %s\n",__LINE__,#c);return 1;}}while(0)
static unsigned random_state=0x7319b265;
static unsigned random_word(void){random_state=random_state*1664525u+1013904223u;return random_state;}
static int random_range(int n){return (int)(random_word()%(unsigned)(2*n+1))-n;}
static int clamp_coord(int x){return x<-32768?-32768:(x>32767?32767:x);}
static int side_cull_dist,side_sin_q8,side_cos_q8;
ACTUAL_SIDE_MASK

typedef struct {int x,y,z;} point;
static fe_camera begin(point c,uint16_t yaw,uint16_t pitch,int dist,int roll){
    return fe_begin(c.x,c.y,c.z,yaw,pitch,dist,roll,
                    linked_sin[yaw],linked_cos[yaw],linked_sin[pitch],linked_cos[pitch]);
}
static int original_face(const point p[4],point camera,uint16_t yaw,uint16_t pitch,int dist,int roll,int far){
    int i,nearest=32767,farthest=-32768,ps=linked_sin[pitch],pc=linked_cos[pitch];
    unsigned side=3;
    int pitch_signed=fe_angle_delta(pitch,0);
    side_sin_q8=(fe_abs(ps)+255)>>8;side_cos_q8=pc>>8;
    side_cull_dist=(!roll && pitch_signed>-8192 && pitch_signed<8192 && pc>0 && dist>0 && dist<=1024)?dist:0;
    for(i=0;i<4;++i){
        int x=p[i].x-camera.x,z=p[i].z-camera.z;
        /* Wide arithmetic is the host oracle for the original native
         * product sum, including its existing signed-short conversion. */
        int depth=(int16_t)(((int64_t)x*linked_sin[yaw]+(int64_t)z*linked_cos[yaw])>>16);
        int across=(int16_t)(((int64_t)x*linked_cos[yaw]-(int64_t)z*linked_sin[yaw])>>16);
        if(depth<nearest)nearest=depth;if(depth>farthest)farthest=depth;
        side&=side_cull_dist?side_mask(depth,p[i].y-camera.y,across):0;
    }
    return farthest>=0 && nearest<=far && !side;
}
static int original_object(point camera,const int box[4],int far){
    int dx=camera.x<box[0]?box[0]-camera.x:(camera.x>box[2]?camera.x-box[2]:0);
    int dz=camera.z<box[1]?box[1]-camera.z:(camera.z>box[3]?camera.z-box[3]:0);
    return (int64_t)dx*dx+(int64_t)dz*dz<=(int64_t)far*far;
}

static int trig_proof(void){
    int angle,delta,maximum=0;
    CHECK(linked_sin[0]==0 && linked_cos[0]==65536);
    CHECK(linked_sin[16384]==65536 && linked_sin[32768]==0 && linked_sin[49152]==-65536);
    for(angle=0;angle<65536;++angle){
        CHECK(linked_sin[angle]>=-65536 && linked_sin[angle]<=65536);
        CHECK(linked_cos[angle]>=-65536 && linked_cos[angle]<=65536);
        for(delta=-FE_ANGLE;delta<=FE_ANGLE;++delta){
            int other=(uint16_t)(angle+delta),bound=7*fe_abs(delta)+16;
            int sd=fe_abs(linked_sin[angle]-linked_sin[other]);
            int cd=fe_abs(linked_cos[angle]-linked_cos[other]);
            CHECK(sd<=bound && cd<=bound);
            if(sd>maximum)maximum=sd;if(cd>maximum)maximum=cd;
        }
    }
    printf("SGL trig: exhaustive 33,619,968 angle pairs, max delta %d <= %d\n",maximum,FE_TRIG);
    return 0;
}

static int visibility_proof(void){
    int sample,j,k,comparisons=0,rejected_faces=0,rejected_objects=0;
    const int pitch_edges[]={-32768,-8193,-8192,-8191,-7936,-7935,0,7935,7936,8191,8192,8193,32767};
    const int distances[]={0,1,160,280,1024,1025,-1};
    for(sample=0;sample<120000;++sample){
        point camera={random_range(sample%8?4096:32767),random_range(2000),random_range(sample%8?4096:32767)};
        uint16_t yaw=(uint16_t)random_word(),pitch=(uint16_t)(sample%3?random_range(10000):pitch_edges[sample%13]);
        int dist=sample%11?280:distances[sample%7],roll=sample%61==0,far=sample%5?1310:4500;
        fe_camera env=begin(camera,yaw,pitch,dist,roll);
        point points[4];fe_vertex bounds[4];
        int bx=random_range(7000),bz=random_range(7000),box[4]={32767,32767,-32768,-32768};
        for(j=0;j<4;++j){
            int spread=sample%3?160:32767;
            points[j]=(point){clamp_coord(camera.x+bx+random_range(spread)),
                clamp_coord(camera.y+random_range(spread)),clamp_coord(camera.z+bz+random_range(spread))};
            bounds[j]=fe_bound_vertex(&env,points[j].x,points[j].y,points[j].z);
            if(points[j].x<box[0])box[0]=points[j].x;if(points[j].x>box[2])box[2]=points[j].x;
            if(points[j].z<box[1])box[1]=points[j].z;if(points[j].z>box[3])box[3]=points[j].z;
        }
        int candidate=fe_face_candidate(bounds,far);
        int object=fe_object_candidate(&env,box[0],box[1],box[2],box[3],far);
        rejected_faces+=!candidate;rejected_objects+=!object;
        for(k=0;k<16;++k){
            point moved=camera;
            if(k<6){int displacement=k&1?64:-64;if(k/2==0)moved.x+=displacement;else if(k/2==1)moved.y+=displacement;else moved.z+=displacement;}
            else {moved.x+=random_range(21);moved.y+=random_range(21);moved.z+=random_range(21);}
            uint16_t myaw=(uint16_t)(yaw+(k<8?(k&1?256:-256):random_range(256)));
            uint16_t mpitch=(uint16_t)(pitch+(k<8?(k&2?256:-256):random_range(256)));
            if(!fe_coord(moved.x)||!fe_coord(moved.y)||!fe_coord(moved.z))continue;
            CHECK(fe_contains(&env,moved.x,moved.y,moved.z,myaw,mpitch,dist,roll));
            CHECK(candidate || !original_face(points,moved,myaw,mpitch,dist,roll,far));
            CHECK(object || !original_object(moved,box,far));
            ++comparisons;
        }
    }
    CHECK(rejected_faces>10000 && rejected_objects>10000);
    printf("candidate proof: %d views, %d face + %d object rejects; zero lost faces\n",
           comparisons,rejected_faces,rejected_objects);
    return 0;
}

static int edge_proof(void){
    point camera={0,0,0};fe_camera env=begin(camera,0,0,280,0);fe_vertex bounds[4];int i;
    CHECK(fe_contains(&env,64,0,0,256,256,280,0));
    CHECK(!fe_contains(&env,64,1,0,0,0,280,0));
    CHECK(!fe_contains(&env,0,0,0,257,0,280,0));
    CHECK(!fe_contains(&env,0,0,0,0,257,280,0));
    CHECK(!fe_contains(&env,0,0,0,0,0,281,0));
    CHECK(!fe_contains(&env,0,0,0,0,0,280,1));
    /* Long polygon centre lies far outside FAR, but one end remains visible. */
    point long_face[4]={{-30,0,100},{30,0,100},{30000,100,20000},{-30000,100,20000}};
    for(i=0;i<4;++i)bounds[i]=fe_bound_vertex(&env,long_face[i].x,long_face[i].y,long_face[i].z);
    CHECK(fe_face_candidate(bounds,1310));CHECK(original_face(long_face,camera,0,0,280,0,1310));
    /* Rear/far boundary can enter the view anywhere inside the envelope. */
    for(i=0;i<4;++i)bounds[i]=fe_bound_vertex(&env,0,0,-63);
    CHECK(fe_face_candidate(bounds,1310));
    for(i=0;i<4;++i)bounds[i]=fe_bound_vertex(&env,0,0,1374);
    CHECK(fe_face_candidate(bounds,1310));
    CHECK(fe_object_candidate(&env,1374,-1,1375,1,1310));
    /* Any member view with side culling off makes the entire side envelope off. */
    env=begin(camera,0,7936,280,0);CHECK(env.side_dist==0);
    env=begin(camera,0,(uint16_t)-7936,280,0);CHECK(env.side_dist==0);
    env=begin(camera,0,0,1025,0);CHECK(env.side_dist==0);
    env=begin(camera,0,0,280,1);CHECK(env.side_dist==0);
    /* Unsupported/range-overflow cases include everything, never overflow. */
    env=fe_begin(INT_MIN,0,0,0,0,280,0,0,65536,0,65536);CHECK(!env.valid);
    CHECK(!fe_contains(&env,0,0,0,0,0,280,0));
    env=fe_begin(0,0,0,0,0,280,0,INT_MIN,65536,0,65536);CHECK(!env.valid);
    env=begin(camera,0,0,280,0);
    bounds[0]=fe_bound_vertex(&env,INT_MAX,INT_MIN,0);
    CHECK(bounds[0].near_depth==-32768 && bounds[0].far_depth==32767 && !bounds[0].side);
    CHECK(fe_object_candidate(&env,0,0,1,1,INT_MAX));
    camera=(point){-32768,-32768,-32768};env=begin(camera,8192,0,1024,0);
    bounds[0]=fe_bound_vertex(&env,32767,32767,32767);
    CHECK(bounds[0].near_depth==-32768 && bounds[0].far_depth==32767 && !bounds[0].side);
    printf("edges: far/rear entry, long crossing faces, invalidation, s16 and s32 limits pass\n");
    return 0;
}
/* Widened, led envelopes (moving-prepare A/B): the centre is anywhere within
 * the position radius of the camera that built it, and every member view
 * (including exact L1 and angle extremes) keeps every original visible face. */
static int sized_proof(void){
    const int sizes[][2]={{64,256},{128,256},{128,512},{256,1024}};
    int sample,j,k,comparisons=0,maximum=0,rejected=0;
    for(sample=0;sample<2000000;++sample){
        int angle=(int)(random_word()&65535u),delta=random_range(FE_ANGLE_MAX);
        int other=(uint16_t)(angle+delta),bound=7*fe_abs(delta)+16;
        int sd=fe_abs(linked_sin[angle]-linked_sin[other]),cd=fe_abs(linked_cos[angle]-linked_cos[other]);
        CHECK(sd<=bound && cd<=bound);if(sd>maximum)maximum=sd;if(cd>maximum)maximum=cd;
    }
    for(sample=0;sample<160000;++sample){
        int size=sample&3,position=sizes[size][0],angle=sizes[size][1];
        point centre={random_range(4096),random_range(2000),random_range(4096)};
        uint16_t yaw=(uint16_t)random_word(),pitch=(uint16_t)random_range(9000);
        int dist=sample%11?280:1024,far=sample%5?1310:4500;
        fe_camera env=fe_begin_sized(centre.x,centre.y,centre.z,yaw,pitch,dist,0,
            linked_sin[yaw],linked_cos[yaw],linked_sin[pitch],linked_cos[pitch],position,angle);
        point points[4];fe_vertex bounds[4];
        int bx=random_range(7000),bz=random_range(7000),box[4]={32767,32767,-32768,-32768};
        CHECK(env.valid);
        for(j=0;j<4;++j){
            int spread=sample%3?160:3000;
            points[j]=(point){clamp_coord(centre.x+bx+random_range(spread)),
                clamp_coord(centre.y+random_range(spread)),clamp_coord(centre.z+bz+random_range(spread))};
            bounds[j]=fe_bound_vertex(&env,points[j].x,points[j].y,points[j].z);
            if(points[j].x<box[0])box[0]=points[j].x;if(points[j].x>box[2])box[2]=points[j].x;
            if(points[j].z<box[1])box[1]=points[j].z;if(points[j].z>box[3])box[3]=points[j].z;
        }
        int candidate=fe_face_candidate(bounds,far),object=fe_object_candidate(&env,box[0],box[1],box[2],box[3],far);
        rejected+=!candidate;
        for(k=0;k<12;++k){
            int ax=random_range(position),ay=random_range(position-fe_abs(ax)),az;
            point moved;
            az=position-fe_abs(ax)-fe_abs(ay);if(k&1)az=random_range(az);else if(k&2)az=-az;
            moved=(point){centre.x+ax,centre.y+ay,centre.z+az};
            uint16_t myaw=(uint16_t)(yaw+(k<4?(k&1?angle:-angle):random_range(angle)));
            uint16_t mpitch=(uint16_t)(pitch+(k<4?(k&2?angle:-angle):random_range(angle)));
            CHECK(fe_contains(&env,moved.x,moved.y,moved.z,myaw,mpitch,dist,0));
            CHECK(candidate || !original_face(points,moved,myaw,mpitch,dist,0,far));
            CHECK(object || !original_object(moved,box,far));
            ++comparisons;
        }
        CHECK(!fe_contains(&env,centre.x+position+1,centre.y,centre.z,yaw,pitch,dist,0));
        CHECK(!fe_contains(&env,centre.x,centre.y,centre.z,(uint16_t)(yaw+angle+1),pitch,dist,0));
    }
    CHECK(rejected>20000);
    CHECK(!fe_begin_sized(0,0,0,0,0,280,0,0,65536,0,65536,FE_POSITION_MAX+1,256).valid);
    CHECK(!fe_begin_sized(0,0,0,0,0,280,0,0,65536,0,65536,64,FE_ANGLE_MAX+1).valid);
    printf("sized envelopes: %d led views up to %d units/%d binang, %d face rejects; trig delta %d\n",
           comparisons,FE_POSITION_MAX,FE_ANGLE_MAX,rejected,maximum);
    return 0;
}
int main(int argc,char** argv){
    if(argc<2)return 1;
    if(argv[1][0]=='s')return sized_proof();
    return argv[1][0]=='t'?trig_proof():(argv[1][0]=='v'?visibility_proof():edge_proof());
}
'''


class ForestEnvelopeDraft(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        sine, cosine = linked_trig()
        (folder / 'trig.h').write_text(
            'static const int linked_sin[65536]={' + ','.join(map(str, sine)) + '};\n' +
            'static const int linked_cos[65536]={' + ','.join(map(str, cosine)) + '};\n')
        actual = function(ROOT / 'src/kokiri_sgl.c', 'static short side_mask(')
        source = folder / 'envelope.c'
        source.write_text(PROGRAM.replace('ACTUAL_SIDE_MASK', actual))
        compiler, cls.env = compiler_env()
        cls.exe = folder / 'envelope'
        result = subprocess.run(
            [compiler, '-x', 'c', '-std=c99', '-O2', '-fsanitize=undefined',
             '-fno-sanitize-recover=undefined', '-I', str(ROOT / 'src'),
             str(source), '-o', str(cls.exe)], env=cls.env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def probe(self, mode):
        result = subprocess.run([str(self.exe), mode], env=self.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_linked_sgl_trig_bound_exhaustive(self):
        self.probe('trig')

    def test_camera_envelope_keeps_all_original_visible_faces(self):
        self.probe('visibility')

    def test_boundaries_long_faces_and_overflow_fallbacks(self):
        self.probe('edges')

    def test_widened_led_envelopes_keep_all_original_visible_faces(self):
        self.probe('sized')
