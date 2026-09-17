#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#define KOKIRI_POLYGON_COUNT 8
#define KOKIRI_VERTEX_COUNT 32
#define KOKIRI_TILE_COUNT 8
#define FOREST_FAR 1310
#define FOREST_FOG_START 655
#define FRAME_PHASE_PREP 0
#define FRAME_PHASE_DEPTH 1
#define FRAME_PHASE_PARTITION 2
#define FRAME_PHASE_FOG 3
#define MESHon 1
typedef struct { unsigned short Vertices[4]; int id; } POLYGON;
typedef struct { unsigned short texno, atrb; int id; } ATTR;
typedef struct {
    int32_t pntbl[32][3]; POLYGON pltbl[8]; ATTR attbl[8]; unsigned nbPolygon;
} PDATA;
PDATA kokiri_pdata;
static short forest_depth[32], tile_depth[8];
static unsigned char tile_fog[8], forest_mesh[8], palette_bytes[256];
static unsigned char *forest_palette = palette_bytes;
static unsigned short kokiri_cluts[8][16];
static struct { int x, y, z; } demo_camera;
static unsigned short demo_yaw;
static int demo_pitch;
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
    demo_camera.x=demo_camera.y=demo_camera.z=demo_pitch=demo_yaw=0;
    for (unsigned i=0; i<8; ++i) {
        kokiri_pdata.pltbl[i].id=i;
        kokiri_pdata.attbl[i].id=i;
        kokiri_pdata.attbl[i].texno=i+1;
        kokiri_pdata.attbl[i].atrb=i&1;
        forest_mesh[i]=i&1; tile_fog[i]=255;
        for (unsigned j=0;j<4;++j) kokiri_pdata.pltbl[i].Vertices[j]=i*4+j;
    }
}
void set_depth(int id, int depth) {
    forest_prepared = false;
    for (int j=0;j<4;++j) kokiri_pdata.pntbl[id*4+j][2]=depth*65536;
}
unsigned visible_count(void) { return captured; }
int fog_level(int id) { return tile_fog[id]; }
void set_camera_z(int z) { demo_camera.z=z; }
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
