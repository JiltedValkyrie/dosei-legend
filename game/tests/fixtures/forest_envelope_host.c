/* Host adapters around the actual scene_prepare implementation. */
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#define KOKIRI_STREAM_ROOMS 1
#define KOKIRI_VERTEX_COUNT 2047
#define KOKIRI_POLYGON_COUNT 510
#define KOKIRI_TILE_COUNT 64
#define KOKIRI_OBJECT_COUNT 4
#define FOREST_DRAW_POINTS 512
#define SCENE_SPOT04 85
#define SCENE_SPOT00 81
#define STORY_BANK_NAVI 128
#define FOREST_FACE_LANDMARK 8u
#define FIELD_LANDMARK_FAR 26000
#define RECOMP_LINK_EYE_HEIGHT 90
#define MESH_LOD_MAX 4
#define MESHon 1
#define SORT_MAX 2
#define SORT_MIN 0
#define SORT_CEN 3
#define ECdis 0
#define SPdis 0
#define CL16Look 0
#define C_RGB(r,g,b) (0x8000|(r)|((g)<<5)|((b)<<10))
#define VRAM_UNITS(x) ((x)/8)
#define JO_VDP1_VRAM ((uintptr_t)forest_palette)
#define FRAME_PHASE_DEPTH 0
#define FRAME_PHASE_PARTITION 1
#define FRAME_PHASE_FOG 2
typedef int32_t POINT[3];
typedef struct {int32_t normal[3];unsigned short Vertices[4];unsigned id;} POLYGON;
typedef struct {unsigned short texno,colno,atrb,gstb;unsigned char sort,dir;unsigned id;} ATTR;
typedef struct {POINT* pntbl;unsigned nbPoint;POLYGON* pltbl;unsigned nbPolygon;ATTR* attbl;} PDATA;
typedef struct {int minimum[3],maximum[3];} kokiri_object;
#include "mesh_lod.h"
#include "forest_vertex_pack.h"
#include "forest_envelope.h"
#include "trig.h"
static POINT source_points[KOKIRI_VERTEX_COUNT],forest_draw_spill[KOKIRI_VERTEX_COUNT];
static POLYGON polys[KOKIRI_POLYGON_COUNT];
static ATTR attrs[KOKIRI_POLYGON_COUNT];
static PDATA kokiri_pdata={source_points,KOKIRI_VERTEX_COUNT,polys,KOKIRI_POLYGON_COUNT,attrs};
static unsigned forest_vertex_count=KOKIRI_VERTEX_COUNT,forest_polygon_count=KOKIRI_POLYGON_COUNT;
static unsigned forest_tile_count=KOKIRI_TILE_COUNT,forest_object_count=KOKIRI_OBJECT_COUNT,forest_sprite_base=1;
static int forest_far_current=1310;
static unsigned short forest_scene=SCENE_SPOT04;
#define FOREST_FAR forest_far_current
#define FOREST_FOG_END (forest_scene==SCENE_SPOT00?4500:forest_scene==STORY_BANK_NAVI?1310:FOREST_FAR)
#define FOREST_FOG_START (forest_scene==SCENE_SPOT00?1800:FOREST_FOG_END/2)
#define FOREST_MESH_START (forest_scene==SCENE_SPOT00?4000:FOREST_FAR*7/8)
static short depth_store[2*KOKIRI_VERTEX_COUNT],tile_depth[KOKIRI_TILE_COUNT];
/* Deliberately small: random walks also exercise the full-scan overflow. */
#define TILE_LIST_MAX 24
static unsigned short tile_list[TILE_LIST_MAX];
static unsigned tile_list_n;
static bool tile_list_full=true;
#define forest_depth depth_store
#define forest_side (depth_store+KOKIRI_VERTEX_COUNT)
static unsigned char tile_fog[KOKIRI_TILE_COUNT],forest_mesh[KOKIRI_POLYGON_COUNT],kokiri_objects[KOKIRI_POLYGON_COUNT];
static unsigned char object_visible[KOKIRI_OBJECT_COUNT];
static kokiri_object kokiri_bounds[KOKIRI_OBJECT_COUNT];
static mesh_lod_t lod_rows[MESH_LOD_MAX],*forest_lods=lod_rows;
static unsigned forest_lod_count;
static unsigned char lod_state[MESH_LOD_MAX],lod_state_applied[MESH_LOD_MAX];
static unsigned short palette[KOKIRI_TILE_COUNT][16],kokiri_cluts[KOKIRI_TILE_COUNT][16];
static unsigned char *forest_palette=(unsigned char*)palette;
static unsigned char fog_channel[2][17][32];
static unsigned short forest_ground_colour=C_RGB(7,13,21);
static struct {int x,y,z;} recomp_camera,recomp_link;
static bool recomp_link_active=true;
static uint16_t recomp_yaw;
static int recomp_pitch,screen_distance=280,camera_roll;
static int recomp_screen_distance(void){return screen_distance;}
static int cutscene_camera_roll(void){return camera_roll;}
static void kokiri_camera_sincos(uint16_t angle,int32_t*s,int32_t*c){*s=linked_sin[angle];*c=linked_cos[angle];}
static int field_fade_offset(int sine,int cosine){(void)sine;(void)cosine;return 0;}
static void frame_timer_begin(int phase){(void)phase;}
static void frame_timer_end(int phase){(void)phase;}
static uint16_t frame_timer_frc(void){static uint16_t ticks;return ++ticks;}
static unsigned frame_timer_ticks_to_us(unsigned ticks){return ticks;}
static unsigned prep_progress;
#define PREP_PROGRESS prep_progress
#define PREP_PROGRESS_STEP() do{if(on_slave)++prep_progress;}while(0)
static int mesh_near_depth,mesh_near_far;
static short mesh_near_tile,mesh_near_polygon;
static unsigned short mesh_near_verts[4];
static bool mesh_near_authored;
static bool forest_prepared;
static unsigned prepared_points,prepared_pack;
static volatile unsigned forest_pack_enabled=2;
/* ACTUAL_CANDIDATE_STATE */
/* ACTUAL_FOREST_WORK */
static POINT *forest_draw_selected;
static unsigned forest_gathered_faces;
static bool forest_reused;
static int prepared_x,prepared_y,prepared_z,prepared_pitch,prepared_dist,prepared_roll;
static int prepared_link_x,prepared_link_z;
static uint16_t prepared_yaw;
static unsigned prepared_visible;
/* ACTUAL_LOD */
/* ACTUAL_PREP */

static POINT original_faces[KOKIRI_POLYGON_COUNT][4];
static unsigned rng;
static unsigned next_word(void){rng=rng*1664525u+1013904223u;return rng;}
void load_bank(unsigned seed,int dense){
    unsigned i,j,k; rng=seed;forest_prepared=false;forest_gathered_faces=0;
    forest_scene=SCENE_SPOT04;forest_far_current=1310;
    for(i=0;i<KOKIRI_POLYGON_COUNT;++i){
        int x=dense?(int)(next_word()%401)-200:(int)(next_word()%10001)-5000;
        int z=dense?200+(int)(next_word()%801):(int)(next_word()%10001)-5000;
        int y=(int)(next_word()%161)-80;
        polys[i]=(POLYGON){{0,-65536,0},{0,0,0,0},i};
        attrs[i]=(ATTR){(unsigned short)(1+i%KOKIRI_TILE_COUNT),0,(unsigned short)(i&1),0,0x67,2,i};
        forest_mesh[i]=(i&1)|((i%3==0)?2:0);kokiri_objects[i]=i%4;
        for(j=0;j<4;++j){
            unsigned v=i*4+j;polys[i].Vertices[j]=v;
            source_points[v][0]=(x+(j&1?20:-20))*65536;
            source_points[v][1]=-y*65536;
            source_points[v][2]=(z+(j&2?20:-20))*65536;
            for(k=0;k<3;++k)original_faces[i][j][k]=source_points[v][k];
        }
    }
    for(i=0;i<KOKIRI_OBJECT_COUNT;++i)kokiri_bounds[i]=(kokiri_object){{-16000,-16000,-16000},{16000,16000,16000}};
    forest_lod_count=1;lod_rows[0]=(mesh_lod_t){{0,0,500},30,350,3000,1,2,{0,0}};
    memset(lod_state_applied,255,sizeof(lod_state_applied));
    memset(tile_depth,0x55,sizeof(tile_depth));tile_list_full=true;  /* Low RAM is not zeroed */
    for(i=0;i<KOKIRI_TILE_COUNT;++i){tile_fog[i]=255;for(j=0;j<16;++j)kokiri_cluts[i][j]=j?C_RGB((i+j)%32,(i*3+j)%32,(i+j*7)%32):0;}
    memset(palette,0,sizeof(palette));
    for(i=0;i<17;++i)for(j=0;j<32;++j){fog_channel[0][i][j]=(j*(16-i)+7*i)>>4;fog_channel[1][i][j]=(j*(16-i)+13*i)>>4;}
}
void set_view(int x,int y,int z,int yaw,int pitch,int dist,int roll,int linkz){
    recomp_camera.x=x;recomp_camera.y=y;recomp_camera.z=z;recomp_yaw=(uint16_t)yaw;recomp_pitch=(int16_t)pitch;
    screen_distance=dist;camera_roll=roll;recomp_link.x=x;recomp_link.y=y+90;recomp_link.z=linkz;
}
void set_mode(int enabled,int pack){forest_envelope_enabled=enabled;forest_pack_enabled=pack;}
void set_scene(int scene){if(forest_scene!=scene){forest_scene=scene;forest_prepared=false;}}
static int full_scan;
/* Reference library: clear and scan every tile each frame (the original). */
void set_full_scan(int on){full_scan=on;}
unsigned run_frame(void){
    unsigned visible;
    if(full_scan)tile_list_full=true;
    visible=scene_prepare(false);
    for(unsigned i=0;i<KOKIRI_TILE_COUNT;++i)if(tile_depth[i]!=32767&&i<forest_tile_count)return 0xFFFFFFFFu;
    return visible;
}
int verify_geometry(void){
    for(unsigned i=0;i<KOKIRI_POLYGON_COUNT;++i){
        unsigned id=polys[i].id;if(attrs[i].id!=id||kokiri_objects[i]!=id%4||forest_mesh[i]!=((id&1)|((id%3==0)?2:0)))return 1;
        POINT* p=i<forest_gathered_faces?forest_draw_selected:kokiri_pdata.pntbl;
        for(unsigned j=0;j<4;++j){unsigned v=polys[i].Vertices[j];if(v>=KOKIRI_VERTEX_COUNT)return 2;
            if(memcmp(p[v],original_faces[id][j],sizeof(POINT)))return 3;}
    }
    return 0;
}
#define SNAP_WORDS (KOKIRI_POLYGON_COUNT*18+KOKIRI_TILE_COUNT*17)
unsigned snapshot(uint32_t* out){
    memset(out,0,SNAP_WORDS*sizeof(*out));POINT* points=forest_gathered_faces?forest_draw_selected:kokiri_pdata.pntbl;
    for(unsigned i=0;i<prepared_visible;++i){unsigned at=polys[i].id*18;out[at++]=1;out[at++]=attrs[i].sort;
        out[at++]=attrs[i].atrb;out[at++]=attrs[i].texno;out[at++]=attrs[i].colno;out[at++]=attrs[i].dir;
        for(unsigned j=0;j<4;++j)for(unsigned k=0;k<3;++k)out[at++]=(uint32_t)points[polys[i].Vertices[j]][k];}
    unsigned at=KOKIRI_POLYGON_COUNT*18;
    for(unsigned i=0;i<KOKIRI_TILE_COUNT;++i){out[at++]=tile_fog[i];for(unsigned j=0;j<16;++j)out[at++]=palette[i][j];}
    return SNAP_WORDS;
}
unsigned state(unsigned which){switch(which){case 0:return forest_candidate_reused;case 1:return forest_candidates;
    case 2:return forest_reused;case 3:return prepared_points;case 4:return forest_draw_selected==forest_draw_spill;
    case 6:return forest_env_builds;case 7:return tile_list_full;case 8:return tile_list_n;
    default:return forest_candidate_valid;}}
