#include "push_block.h"
#include "kokiri_camera.h"

/* ObjOshihiki_Push updates distance directly (no Actor_UpdatePos multiplier).
 * Convert 20 Hz speed and acceleration to 30 Hz separately. */
#define PUSH_ACCEL_Q8 57
#define PUSH_MAX_Q8 341
#define PUSH_DISTANCE_Q8 (20 * 256)
#define PUSH_COOLDOWN 15
#define PUSH_ID 0x00FF /* local profile identity; source spawn decoding is separate */
enum { SLOT, HOME_X, HOME_Z, DISTANCE, SPEED, DIRECTION, FALL_SPEED, TIMER };
static bg_mesh_t block_mesh;
static bool mesh_ready;
static void (*draw_block)(const actor_t *, int32_t);
static const int32_t scales[] = {6554,10923,13107,21845};

static int32_t scale(const actor_t *a) { return scales[a->params & 3]; }
static int32_t half(const actor_t *a) { return (300 * scale(a) + 32768) / 65536; }
unsigned push_block_bg(const actor_t *a) { return (unsigned)a->data[SLOT]; }
bool push_block_moving(const actor_t *a) { return a && a->data[DIRECTION] != 0; }
void push_block_lock(actor_t *a) {if(a && a->profile && a->profile->id==PUSH_ID)a->data[TIMER]=-1;}

static void place(actor_t *a)
{
    bg_vec_t pos = {a->x,a->y,a->z};
    bg_dyna_set(push_block_bg(a), &pos, a->yaw, scale(a));
}

/* Own mesh excluded, as source queries exclude the actor. Four face-corner
 * rays cover the complete next 20-unit grid step before it can start. */
static bool blocked(actor_t *a, uint16_t yaw, int direction)
{
    int32_t sn,cs,h=half(a), i;
    bool hit = false;
    kokiri_camera_sincos(yaw,&sn,&cs);
    bg_dyna_enable(push_block_bg(a),false);
    for (i=0;i<4;i++) {
        int32_t side = (i&1) ? h-1 : 1-h;
        bg_vec_t from = {a->x + side*cs/65536,
            a->y + ((i&2) ? 2*h-1 : 1), a->z-side*sn/65536};
        /* ObjOshihiki_CheckWall maxDist = half + 20 - 0.5: the ray stops
         * short of the next face plane. Reaching exactly half + 20 ended ON
         * the back of room 3's ledge wall (x=-395), refusing the last push. */
        bg_vec_t to = {from.x+direction*(h+19)*sn/65536,from.y,
                      from.z+direction*(h+19)*cs/65536}, result;
        bg_hit_t wall;
        if (bg_line(&from,&to,&result,BG_CHECK_WALL|BG_CHECK_ONE_FACE,
                     BG_IGNORE_ENTITY,&wall)) { hit=true; break; }
    }
    bg_dyna_enable(push_block_bg(a),true);
    return hit;
}

static int32_t floor_below(actor_t *a, int32_t ceiling)
{
    int i,h=half(a)-1;
    int32_t best=BG_Y_MIN;
    bg_dyna_enable(push_block_bg(a),false);
    for (i=0;i<5;i++) {
        bg_vec_t p={a->x+(i==4?0:(i&1?h:-h)),ceiling,
                    a->z+(i==4?0:(i&2?h:-h))};
        bg_hit_t hit;
        int32_t y=bg_floor(&p,BG_IGNORE_ENTITY,&hit);
        if (y>best) best=y;
    }
    bg_dyna_enable(push_block_bg(a),true);
    return best;
}

static void update(actor_t *a)
{
    int32_t old_y=a->y, floor;
    if (a->data[TIMER]>0) a->data[TIMER]--;
    if (a->data[DIRECTION]) {
        int32_t sn,cs,dist;
        a->data[SPEED]+=PUSH_ACCEL_Q8;
        if (a->data[SPEED]>PUSH_MAX_Q8) a->data[SPEED]=PUSH_MAX_Q8;
        a->data[DISTANCE]+=a->data[SPEED];
        if (a->data[DISTANCE]>PUSH_DISTANCE_Q8) a->data[DISTANCE]=PUSH_DISTANCE_Q8;
        dist=a->data[DISTANCE]*(a->data[DIRECTION]&0x20000 ? -1 : 1);
        kokiri_camera_sincos((uint16_t)a->data[DIRECTION],&sn,&cs);
        a->x=a->data[HOME_X]+(int32_t)((int64_t)dist*sn/(256*65536));
        a->z=a->data[HOME_Z]+(int32_t)((int64_t)dist*cs/(256*65536));
        if (a->data[DISTANCE]==PUSH_DISTANCE_Q8) {
            a->data[DIRECTION]=0;
            a->data[TIMER]=PUSH_COOLDOWN;
        }
    }
    floor=floor_below(a,old_y+1);
    if (floor==old_y) a->data[FALL_SPEED]=0;
    else {
        if (!a->data[FALL_SPEED]) a->data[SPEED]=0;
        a->data[DIRECTION]=0;
        a->data[FALL_SPEED]-=171;
        if (a->data[FALL_SPEED]<-5120) a->data[FALL_SPEED]=-5120;
        a->data[SPEED]+=a->data[FALL_SPEED];
        a->y+=a->data[SPEED]/256;
        a->data[SPEED]%=256;
        if (floor!=BG_Y_MIN && a->y<=floor) {
            a->y=floor;
            a->data[FALL_SPEED]=0;
        }
        if (a->y<BG_Y_MIN) { actor_kill(a); return; }
    }
    place(a);
}

static void destroy(actor_t *a) { bg_dyna_remove(push_block_bg(a)); }
static void draw(const actor_t *a) { if (draw_block) draw_block(a,half(a)); }
static const actor_profile_t profile={PUSH_ID,ACTORCAT_PROP,0,0,update,draw,destroy};

bool push_block_set_mesh(const bg_mesh_t *mesh)
{
    if (actor_sys_find(PUSH_ID,0)) return false;
    mesh_ready=mesh && mesh->triangle_count && mesh->triangles;
    if (mesh_ready) block_mesh=*mesh;
    return mesh_ready;
}

actor_t *push_block_spawn(unsigned scene,int room,bg_vec_t p,uint16_t yaw,uint16_t params)
{
    actor_t *a;
    unsigned slot;
    if (!mesh_ready) return 0;
    slot=bg_dyna_register(&block_mesh,BG_DYNA_POS);
    if (slot>=BG_DYNA_MAX) return 0;
    a=actor_spawn(&profile,scene,room,p.x,p.y,p.z,yaw,params);
    if (!a) { bg_dyna_remove(slot); return 0; }
    a->data[SLOT]=(int32_t)slot;
    place(a);
    return a;
}

actor_t *push_block_from_bg(unsigned bg_id)
{
    actor_t *a=0;
    while ((a=actor_sys_find(PUSH_ID,a)))
        if (push_block_bg(a)==bg_id) return a;
    return 0;
}

bool push_block_request(actor_t *a,uint16_t facing,int direction,unsigned strength)
{
    unsigned size;
    if (!a || a->profile!=&profile || !direction || a->data[DIRECTION] ||
        a->data[TIMER] || a->data[FALL_SPEED]) return false;
    size=a->params&3;
    if ((size==2 && strength<1) || (size==3 && strength<2)) return false;
    direction=direction>0?1:-1;
    if (blocked(a,facing,direction)) return false;
    a->data[HOME_X]=a->x; a->data[HOME_Z]=a->z;
    a->data[DISTANCE]=a->data[SPEED]=0;
    a->data[DIRECTION]=(int32_t)facing | (direction>0 ? 0x10000 : 0x20000);
    return true;
}

void push_block_set_draw(void (*callback)(const actor_t *,int32_t)) { draw_block=callback; }
