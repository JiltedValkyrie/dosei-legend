#include "player_camera.h"
#include "kokiri_camera.h"
#pragma GCC optimize("Os")

static unsigned char experiment;
static uint16_t orbit_yaw = 32768, orbit_start;
static signed char orbit_pending, orbit_direction;
static unsigned char orbit_frame;
bool player_camera_orbit_active(void) { return experiment==1; }
void player_camera_orbit_turn(int direction)
{
    if (experiment != 1 || !direction) return;
    /* Bounded queue: rapid taps retain complete cardinal turns. */
    if (direction > 0 && orbit_pending < 4) ++orbit_pending;
    if (direction < 0 && orbit_pending > -4) --orbit_pending;
}
static void orbit_step(void)
{
    int32_t t, curve;
    if (!orbit_direction) {
        if (!orbit_pending) return;
        orbit_direction = orbit_pending > 0 ? 1 : -1;
        orbit_pending -= orbit_direction;
        orbit_start = orbit_yaw;
        orbit_frame = 0;
    }
    /* Cubic Hermite smoothstep, Q8: zero slope at both ends, 16 fixed
     * camera steps (~0.53 s at 30 Hz). Largest product is 16,777,216. */
    t = ++orbit_frame * 16;
    curve = t*t*(768-2*t)/1024; /* 16384 * (3u^2 - 2u^3). */
    orbit_yaw = (uint16_t)(orbit_start + orbit_direction*curve);
    if (orbit_frame == 16) orbit_direction = 0;
}
unsigned player_camera_experiment_cycle(void)
{
    /* Leave a cardinal heading when switching away mid-turn. */
    if (orbit_direction) orbit_yaw=(uint16_t)(orbit_start+orbit_direction*16384);
    orbit_direction=orbit_pending=orbit_frame=0;
    experiment^=1;
    return experiment;
}
void player_camera_experiment_reset(void)
{
    experiment=0; orbit_yaw=32768;
    orbit_direction=orbit_pending=orbit_frame=0;
}

void player_camera_scene_default(bool overhead)
{
    player_camera_experiment_reset();
    experiment=overhead ? 1 : 0;
}

static void experiment_eye(const camera_position_t *player, camera_position_t *eye,
                           uint16_t *yaw, int32_t *pitch)
{
    /* Human 2026-10-08: 40% closer than 600/360, same pitch. */
    const int back=360, rise=216;
    *eye=*player;
    eye->y+=oot_follow_scale.height-OOT_CAM_PLAYER_ORIGIN+rise;
    eye->z+=back;
    *yaw=32768; /* Fixed north; movement still uses the actual camera yaw. */
    if (experiment==1) {
        int32_t s,c;
        orbit_step();
        *yaw=orbit_yaw;
        kokiri_camera_sincos(*yaw,&s,&c);
        eye->x-=s*back/65536;
        eye->z=player->z-c*back/65536;
    }
    *pitch=-(int16_t)kokiri_camera_facing(rise,back);
}

static int32_t ease(int32_t from, int32_t to)
{
    int32_t step = (to - from) / 6;
    if (!step && from != to) step = from < to ? 1 : -1;
    return from + step;
}

void player_camera_reset(player_camera_t *camera)
{
    *camera = (player_camera_t){0};
}

bool player_camera_crawl_line(const bg_mesh_t *mesh, unsigned index,
                             bg_vec_t *point, int32_t direction[3])
{
    const bg_camera_t *cam;
    const int16_t *front, *back;
    if (!mesh || !mesh->cameras || !mesh->camera_vectors || index >= mesh->camera_count)
        return false;
    cam = &mesh->cameras[index];
    if (cam->setting != 0x1E || cam->count < 4 ||
        cam->first > mesh->camera_vector_count ||
        (uint32_t)cam->count > mesh->camera_vector_count - cam->first) return false;
    front = &mesh->camera_vectors[(cam->first+1)*3];
    back = &mesh->camera_vectors[(cam->first+cam->count-2)*3];
    if (front[0] == back[0] && front[2] == back[2]) return false;
    point->x=front[0]; point->y=front[1]; point->z=front[2];
    direction[0]=back[0]-front[0];
    direction[1]=back[1]-front[1];
    direction[2]=back[2]-front[2];
    return true;
}

static bool near_climb_end(const camera_position_t *player, uint16_t facing)
{
    bg_vec_t ray = {player->x, player->y-OOT_CAM_PLAYER_ORIGIN+1, player->z};
    bg_hit_t hit;
    int32_t feet = ray.y-1, floor, sine, cosine;
    floor = bg_floor(&ray, BG_IGNORE_CAMERA, &hit);
    if (floor != BG_Y_MIN && feet-floor < oot_follow_scale.height) return true;
    kokiri_camera_sincos(facing, &sine, &cosine);
    ray.x += sine * 25 / 65536;
    ray.z += cosine * 25 / 65536;
    ray.y = feet + oot_follow_scale.height * 22 / 10;
    floor = bg_floor(&ray, BG_IGNORE_CAMERA, &hit);
    return floor != BG_Y_MIN && floor > feet;
}

static void clip_eye(const bg_vec_t *at, camera_position_t *eye, int32_t clearance)
{
    bg_vec_t end = {eye->x, eye->y, eye->z}, hit;
    bg_hit_t poly;
    if (bg_line(at, &end, &hit, BG_CHECK_ALL, BG_IGNORE_CAMERA, &poly)) {
        int32_t dx=at->x-hit.x, dy=at->y-hit.y, dz=at->z-hit.z;
        int32_t span=dx<0?-dx:dx, n=dy<0?-dy:dy;
        if (n>span) span=n;
        n=dz<0?-dz:dz; if(n>span) span=n;
        if (span<1) span=1;
        if (clearance>span) clearance=span;
        eye->x=hit.x+dx*clearance/span;
        eye->y=hit.y+dy*clearance/span;
        eye->z=hit.z+dz*clearance/span;
    }
}

void player_camera_constrain(const oot_follow_t *follow,
    const camera_position_t *player, int32_t at_y, camera_position_t *eye,
    int32_t *pitch)
{
    bg_vec_t at={player->x,at_y,player->z};
    bg_vec_t ray;
    bg_hit_t ground;
    int32_t floor, clearance=eye->y-(player->y-OOT_CAM_PLAYER_ORIGIN);
    int32_t old_y=eye->y;
    /* Normal1 raises the focus by the selected age's height, then adds the
     * pitch rise when placing the eye. Collision shortens that same arm;
     * walls, floors and ceilings must constrain ordinary follow too. */
    if (!oot_follow_legacy()) {
        at.x+=follow->aim_q8[0]/256;
        at.y+=follow->aim_q8[1]/256;
        at.z+=follow->aim_q8[2]/256;
    }
    /* Keep the age/profile height plus pitch rise over the ground beneath the
     * desired eye. Merely shortening a ray at a slope hit can leave the eye
     * one unit above the floor, making an entire near cell disappear. */
    if (clearance<8) clearance=8;
    ray=(bg_vec_t){eye->x,eye->y+oot_follow_scale.height*2,eye->z};
    floor=bg_floor(&ray,BG_IGNORE_CAMERA,&ground);
    if (floor!=BG_Y_MIN && eye->y<floor+clearance) eye->y=floor+clearance;
    clip_eye(&at,eye,8);
    if (eye->y>old_y) {
        int32_t dx=eye->x-at.x,dz=eye->z-at.z,large,small;
        if(dx<0)dx=-dx;
        if(dz<0)dz=-dz;
        large=dx>dz?dx:dz;small=dx>dz?dz:dx;
        /* Cheap horizontal length; no wide square root. Keep Link framed
         * when the terrain raises the eye above the requested orbit. */
        *pitch=-(int16_t)kokiri_camera_facing(eye->y-at.y,large+small*3/8);
    }
}

/* Deferred arm collision (2026-10-09 speed): during a catch-up batch only
 * the last eye is drawn, and the follow camera rebuilds the eye from its own
 * state every step without reading it back. recomp.c defers the floor/line
 * constraint and applies it once to the final eye. */
static bool constrain_deferred, constrain_pending;
static const oot_follow_t *pending_follow;
static camera_position_t pending_player;
static int32_t pending_at_y;

void player_camera_defer_constrain(bool on)
{
    constrain_deferred = on;
}

void player_camera_flush_constrain(camera_position_t *eye, int32_t *pitch)
{
    if (!constrain_pending) return;
    constrain_pending = false;
    player_camera_constrain(pending_follow, &pending_player, pending_at_y, eye, pitch);
}

void player_camera_update(player_camera_t *camera, oot_follow_t *follow,
    unsigned mode, const camera_position_t *player, uint16_t facing, bool moving,
    camera_position_t *eye, uint16_t *yaw, int32_t *pitch)
{
    /* Deliberately unobstructed survey views: ordinary arm clipping would
     * pull these back against the very ground being compared. Link's own
     * collision is unaffected. Traversal and first-person retain their views. */
    if (experiment && mode == PLAYER_CAMERA_NORMAL) {
        constrain_pending = false;
        experiment_eye(player,eye,yaw,pitch);
        return;
    }
    oot_follow_profile_t profile = {oot_follow_scale.y_offset, OOT_CAM_PITCH_TARGET, 18, 0};
    camera_position_t anchor = *player;
    int32_t target;
    bool transition;
    if (!camera->initialized) {
        camera->at_y = player->y-OOT_CAM_PLAYER_ORIGIN+oot_follow_scale.height+oot_follow_scale.y_offset;
        camera->previous_y = player->y;
        camera->initialized = true;
    }
    if (mode != camera->mode) {
        if (mode == PLAYER_CAMERA_CLIMB)
            camera->climb_offset = player->y > camera->previous_y ?
                (oot_follow_scale.height == 68 ? -20 : -14) :
                (oot_follow_scale.height == 68 ? -7 : -5);
        if (mode == PLAYER_CAMERA_NORMAL) camera->returning = true;
        oot_follow_look_exit(follow);
    }
    /* sSetNormal0ModeLedgeHangData / Unique1: yOffset -80, pitch 40.
     * Jump2 offsets (-20 +/-10) depend on climb direction on entry.
     * Offsets use Normal1 height scales .464 (child 44) or .68 (adult 68). */
    if (mode == PLAYER_CAMERA_HANG) {
        profile.y_offset = oot_follow_scale.height == 68 ? -54 : -37;
        profile.pitch_target = 7282;
        profile.pitch_rate = 150;
        profile.yaw_policy = 2;
    } else if (mode == PLAYER_CAMERA_CLIMB) {
        profile.y_offset = camera->climb_offset;
        profile.pitch_target = near_climb_end(player, facing) ? 500 : follow->pitch;
        profile.pitch_rate = 30;
        profile.yaw_policy = 1;
    }
    target = player->y-OOT_CAM_PLAYER_ORIGIN+oot_follow_scale.height+profile.y_offset;
    transition = mode != PLAYER_CAMERA_NORMAL || camera->returning;
    camera->at_y = transition ? ease(camera->at_y, target) : target;
    if (camera->at_y == target) camera->returning = false;
    anchor.y += camera->at_y-target;
    oot_follow_update_profile(follow, &anchor, facing, moving, eye, yaw, pitch, &profile);
    if (constrain_deferred) {
        constrain_pending = true;
        pending_follow = follow;
        pending_player = *player;
        pending_at_y = camera->at_y;
    } else {
        constrain_pending = false;
        player_camera_constrain(follow,player,camera->at_y,eye,pitch);
    }
    camera->mode = mode;
    camera->previous_y = player->y;
}


void player_camera_first_person(oot_follow_t *state, const bg_vec_t *focus,
    uint16_t facing, int yaw_input, int pitch_input,
    camera_position_t *eye, uint16_t *yaw, int32_t *pitch, bool aim)
{
    int32_t sy, cy, sp, cp;
    int target = aim ? state->look_pitch - pitch_input : pitch_input * 14400 / 280;
    if (target > 14400) target = 14400;
    if (target < -14400) target = -14400;
    int delta = target - state->look_pitch;
    int step = aim ? delta : delta / 21; /* source SmoothStep /14, adapted 20 -> 30 Hz */
    if (step > 2666) step = 2666;
    if (step < -2666) step = -2666;
    if (step >= 0 && step < 20) step = delta > 20 ? 20 : delta;
    if (step < 0 && step > -20) step = delta < -20 ? -20 : delta;
    state->look_pitch += step;
    state->look_yaw = (int16_t)(state->look_yaw + (aim ? yaw_input : yaw_input * 640 / 420));
    *yaw = facing + state->look_yaw;
    *pitch = state->look_pitch;
    kokiri_camera_sincos(*yaw, &sy, &cy);
    kokiri_camera_sincos((uint16_t)*pitch, &sp, &cp);
    *eye = *focus;
    eye->x -= (sy / 256) * (cp / 256) * 5 / 65536;
    eye->z -= (cy / 256) * (cp / 256) * 5 / 65536;
    eye->y -= sp * 5 / 65536;   /* behind the focus along the view: up looks drop it */
    clip_eye(focus, eye,2);
}
