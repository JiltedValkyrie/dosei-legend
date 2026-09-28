#include "player_camera.h"
#include "kokiri_camera.h"

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
    if (floor != BG_Y_MIN && feet-floor < OOT_CAM_PLAYER_HEIGHT) return true;
    kokiri_camera_sincos(facing, &sine, &cosine);
    ray.x += sine * 25 / 65536;
    ray.z += cosine * 25 / 65536;
    ray.y = feet + OOT_CAM_PLAYER_HEIGHT * 22 / 10;
    floor = bg_floor(&ray, BG_IGNORE_CAMERA, &hit);
    return floor != BG_Y_MIN && floor > feet;
}

static void clip_eye(const bg_vec_t *at, camera_position_t *eye)
{
    bg_vec_t end = {eye->x, eye->y, eye->z}, hit;
    bg_hit_t poly;
    if (bg_line(at, &end, &hit, BG_CHECK_ALL, BG_IGNORE_CAMERA, &poly)) {
        int32_t dx=at->x-hit.x, dy=at->y-hit.y, dz=at->z-hit.z;
        int32_t span=dx<0?-dx:dx, n=dy<0?-dy:dy;
        if (n>span) span=n;
        n=dz<0?-dz:dz; if(n>span) span=n;
        if (span<1) span=1;
        eye->x=hit.x+dx*2/span;
        eye->y=hit.y+dy*2/span;
        eye->z=hit.z+dz*2/span;
    }
}

void player_camera_update(player_camera_t *camera, oot_follow_t *follow,
    unsigned mode, const camera_position_t *player, uint16_t facing, bool moving,
    camera_position_t *eye, uint16_t *yaw, int32_t *pitch)
{
    oot_follow_profile_t profile = {OOT_CAM_Y_OFFSET, OOT_CAM_PITCH_TARGET, 18, 0};
    camera_position_t anchor = *player;
    int32_t target;
    bool transition;
    if (!camera->initialized) {
        camera->at_y = player->y-OOT_CAM_PLAYER_ORIGIN+OOT_CAM_PLAYER_HEIGHT+OOT_CAM_Y_OFFSET;
        camera->previous_y = player->y;
        camera->initialized = true;
    }
    if (mode != camera->mode) {
        if (mode == PLAYER_CAMERA_CLIMB)
            camera->climb_offset = player->y > camera->previous_y ? -14 : -5;
        if (mode == PLAYER_CAMERA_NORMAL) camera->returning = true;
        oot_follow_look_exit(follow);
    }
    /* sSetNormal0ModeLedgeHangData / Unique1: yOffset -80, pitch 40.
     * Jump2 offsets (-20 +/-10) depend on climb direction on entry.
     * All offsets use the Normal1 player-height scale .464 (child 44, BUG-009). */
    if (mode == PLAYER_CAMERA_HANG) {
        profile.y_offset = -37;
        profile.pitch_target = 7282;
        profile.pitch_rate = 150;
        profile.yaw_policy = 2;
    } else if (mode == PLAYER_CAMERA_CLIMB) {
        profile.y_offset = camera->climb_offset;
        profile.pitch_target = near_climb_end(player, facing) ? 500 : follow->pitch;
        profile.pitch_rate = 30;
        profile.yaw_policy = 1;
    }
    target = player->y-OOT_CAM_PLAYER_ORIGIN+OOT_CAM_PLAYER_HEIGHT+profile.y_offset;
    transition = mode != PLAYER_CAMERA_NORMAL || camera->returning;
    camera->at_y = transition ? ease(camera->at_y, target) : target;
    if (camera->at_y == target) camera->returning = false;
    anchor.y += camera->at_y-target;
    oot_follow_update_profile(follow, &anchor, facing, moving, eye, yaw, pitch, &profile);
    if (transition && !oot_follow_legacy()) {
        bg_vec_t at = {player->x, camera->at_y, player->z};
        /* Keep the ray's direction while shortening it. Integer rounding of
         * the 2-unit clearance is below one unit on each transverse axis. */
        clip_eye(&at, eye);
    }
    camera->mode = mode;
    camera->previous_y = player->y;
}


void player_camera_first_person(oot_follow_t *state, const bg_vec_t *focus,
    uint16_t facing, int yaw_input, int pitch_input,
    camera_position_t *eye, uint16_t *yaw, int32_t *pitch)
{
    int32_t sy, cy, sp, cp;
    int target = pitch_input * 14400 / 280;
    int delta = target - state->look_pitch;
    int step = delta / 21; /* source SmoothStep /14, adapted 20 -> 30 Hz */
    if (step > 2666) step = 2666;
    if (step < -2666) step = -2666;
    if (step >= 0 && step < 20) step = delta > 20 ? 20 : delta;
    if (step < 0 && step > -20) step = delta < -20 ? -20 : delta;
    state->look_pitch += step;
    state->look_yaw = (int16_t)(state->look_yaw + yaw_input * 640 / 420);
    *yaw = facing + state->look_yaw;
    *pitch = state->look_pitch;
    kokiri_camera_sincos(*yaw, &sy, &cy);
    kokiri_camera_sincos((uint16_t)*pitch, &sp, &cp);
    *eye = *focus;
    eye->x -= (sy / 256) * (cp / 256) * 5 / 65536;
    eye->z -= (cy / 256) * (cp / 256) * 5 / 65536;
    eye->y -= sp * 5 / 65536;
    clip_eye(focus, eye);
}
