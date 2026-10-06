#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#define KOKIRI_POLYGON_COUNT 8
#define KOKIRI_VERTEX_COUNT 32
#define KOKIRI_TILE_COUNT 8
#define forest_polygon_count KOKIRI_POLYGON_COUNT
#define forest_vertex_count KOKIRI_VERTEX_COUNT
#define forest_tile_count KOKIRI_TILE_COUNT
#define forest_sprite_base 1
#define FOREST_FAR 1310
#define FOREST_FOG_START 655
#define FRAME_PHASE_PREP 0
#define FRAME_PHASE_DEPTH 1
#define FRAME_PHASE_PARTITION 2
#define FRAME_PHASE_FOG 3
#define MESHon 1
#define SORT_MAX 2
#define SORT_CEN 3
#define RECOMP_LINK_EYE_HEIGHT 90
typedef int32_t FIXED;
typedef struct { int32_t norm[3]; unsigned short Vertices[4]; int id; } POLYGON;
typedef struct { unsigned short texno, atrb, gstb; unsigned char sort; int id; } ATTR;
typedef struct {
    int32_t pntbl[32][3]; POLYGON pltbl[8]; ATTR attbl[8]; unsigned nbPolygon;
} PDATA;
PDATA kokiri_pdata;
static short forest_depth[32], tile_depth[8];
static unsigned char tile_fog[8], forest_mesh[8], palette_bytes[256];
static unsigned char *forest_palette = palette_bytes;
static unsigned short kokiri_cluts[8][16];
static struct { int x, y, z; } recomp_camera;
static struct { int x, y, z; } recomp_link;
static bool recomp_link_active, prepared_link_active;
static int prepared_link_x, prepared_link_y, prepared_link_z;
static unsigned short recomp_yaw;
static int recomp_pitch;
static bool forest_prepared;
static int prepared_x, prepared_y, prepared_z, prepared_pitch;
static unsigned short prepared_yaw;
static unsigned int prepared_visible;
static unsigned char fog_channel[2][17][32];
static void forest_fog_init(void);
int fog_color(int target, int amount, int channel) { return fog_channel[target][amount][channel]; }
static unsigned kokiri_rejected, kokiri_accepted_mask, submitted, captured;
static void frame_timer_begin(int phase) { (void)phase; }
static void frame_timer_end(int phase) { (void)phase; }
static void kokiri_camera_sincos(unsigned short yaw, int32_t *s, int32_t *c)
{ (void)yaw; *s=0; *c=65536; }
static void submit(PDATA *p, unsigned bit) { (void)bit; captured=p->nbPolygon; }
void reset_scene(void) {
    forest_fog_init();
    forest_prepared = false;
    recomp_camera.x=recomp_camera.y=recomp_camera.z=recomp_pitch=recomp_yaw=0;
    recomp_link.x=0; recomp_link.y=90; recomp_link.z=100; recomp_link_active=true;
    for (unsigned i=0; i<8; ++i) {
        kokiri_pdata.pltbl[i].id=i;
        kokiri_pdata.attbl[i].id=i;
        kokiri_pdata.attbl[i].texno=i+1;
        kokiri_pdata.attbl[i].atrb=i&1;
        kokiri_pdata.attbl[i].sort=0x67;
        kokiri_pdata.pltbl[i].norm[1]=-65536;
        forest_mesh[i]=i&1; tile_fog[i]=255;
        for (unsigned j=0;j<4;++j) {
            kokiri_pdata.pltbl[i].Vertices[j]=i*4+j;
            kokiri_pdata.pntbl[i*4+j][1]=0;
        }
    }
}
void set_depth(int id, int depth) {
    forest_prepared = false;
    for (int j=0;j<4;++j) {
        kokiri_pdata.pntbl[id*4+j][0]=(j==0 || j==3 ? -10 : 10)*65536;
        kokiri_pdata.pntbl[id*4+j][2]=depth*65536;
    }
}
void set_floor_footprint(int id) {
    forest_prepared=false;
    kokiri_pdata.pntbl[id*4][2]=90*65536;
    kokiri_pdata.pntbl[id*4+1][2]=90*65536;
    kokiri_pdata.pntbl[id*4+2][2]=110*65536;
    kokiri_pdata.pntbl[id*4+3][2]=110*65536;
}
void set_link_x(int x) { recomp_link.x=x; }
unsigned visible_count(void) { return captured; }
int fog_level(int id) { return tile_fog[id]; }
void set_camera_z(int z) { recomp_camera.z=z; }
void set_link_feet(int y) { recomp_link.y=y+90; }
void set_link_active(int active) { recomp_link_active=active; }
void set_surface(int id, int y, int normal_y) {
    forest_prepared=false;
    kokiri_pdata.pltbl[id].norm[1]=normal_y;
    for (int j=0;j<4;++j) kokiri_pdata.pntbl[id*4+j][1]=-y*65536;
}
int sort_for_id(int id) {
    for (int i=0;i<8;++i) if (kokiri_pdata.pltbl[i].id==id)
        return kokiri_pdata.attbl[i].sort;
    return -1;
}
void set_corner_height(int vertex, int y) {
    forest_prepared=false;
    kokiri_pdata.pntbl[vertex][1]=-y*65536;
}
int polygon_id(int index) { return kokiri_pdata.pltbl[index].id; }
int paired(int index) {
    int id=kokiri_pdata.pltbl[index].id;
    return kokiri_pdata.attbl[index].id==id &&
        kokiri_pdata.attbl[index].texno==id+1 && forest_mesh[index]==(id&1);
}

/* The partition loop records the closest still-stippled polygon, so the host
** build needs the same statics the game file declares above the body. */
static int mesh_near_depth = 32767;
static int mesh_near_far = 32767;
static short mesh_near_tile = -1;
static short mesh_near_polygon = -1;
static unsigned short mesh_near_verts[4];
static bool mesh_near_authored;
static bool forest_reused;

/* Expose the reuse flag so tests can tell a rebuilt list from a cached one --
** the distinction that makes a timing figure meaningful. */
int scene_reused(void) { return forest_reused ? 1 : 0; }
