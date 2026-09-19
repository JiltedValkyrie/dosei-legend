/* Host adapter for gameplay.c: the only thing the Saturn supplies that a PC
** cannot is the binang heading, so that is all this stands in for. Everything
** under test -- inventory, pickups, targeting, the swing window, the shield and
** grass cutting -- is the real game code. */
#include <math.h>
#include <stdint.h>
#include "../../src/gameplay.h"
#include "kokiri_actors.h"

uint16_t gameplay_facing(int32_t dx, int32_t dz)
{
    double angle = atan2((double)dx, (double)dz);
    double turns = angle / 6.283185307179586;
    return (uint16_t)(int32_t)(turns * 65536.0);
}

/* Small readers so the test does not have to mirror the struct layout. */
int gp_owned(void)      { return gameplay.owned; }
int gp_equipped(void)   { return gameplay.equipped; }
int gp_target(void)     { return gameplay.target; }
int gp_swing(void)      { return gameplay.swing; }
int gp_events(void)     { return (int)gameplay.events; }
int gp_cut_count(void)  { return gameplay.cut_count; }
int gp_shielding(void)  { return gameplay.shielding ? 1 : 0; }
int gp_face_locked(void){ return gameplay.face_locked ? 1 : 0; }
int gp_face_yaw(void)   { return gameplay.face_yaw; }
int gp_grass_total(void){ return KOKIRI_GRASS_COUNT; }
int gp_npc_total(void)  { return KOKIRI_NPC_COUNT; }
int gp_pickup_total(void) { return KOKIRI_PICKUP_COUNT; }

void gp_pickup_at(int i, int *x, int *y, int *z, int *item)
{
    *x = kokiri_pickups[i].x; *y = kokiri_pickups[i].y;
    *z = kokiri_pickups[i].z; *item = kokiri_pickups[i].item;
}

void gp_grass_at(int i, int *x, int *y, int *z)
{
    *x = kokiri_grass[i].x; *y = kokiri_grass[i].y; *z = kokiri_grass[i].z;
}

void gp_npc_at(int i, int *x, int *y, int *z)
{
    *x = kokiri_npcs[i].x; *y = kokiri_npcs[i].y; *z = kokiri_npcs[i].z;
}

static unsigned int test_room;
void gp_room(unsigned int room) { test_room = room; }
int gp_rupees(void) { return gameplay.rupees; }
void gp_wallet(unsigned int amount) { gameplay.rupees = amount; }
int gp_drop(unsigned int i) { return gameplay.grass_rupee[i]; }
int gp_drop_age(unsigned int i) { return gameplay.grass_age[i]; }
void gp_seed(unsigned int seed) { gameplay.drop_rng = seed; }
void gp_rupee_at(int i, int *x, int *y, int *z, int *value, int *room)
{
    *x=kokiri_rupees[i].x; *y=kokiri_rupees[i].y; *z=kokiri_rupees[i].z;
    *value=kokiri_rupees[i].value; *room=kokiri_rupees[i].room;
}

/* One step with the flags spelled out, so the test never builds a struct. */
void gp_step_full(int x, int y, int z, int yaw, int attack, int shield,
                  int target, int interact, int grounded, int cancel,
                  int pause, int menu_step)
{
    /* Zero first: every field must be set explicitly, or a member added to
    ** gameplay_input_t later arrives as stack garbage and silently changes
    ** what the tests are exercising. That is exactly how an uninitialised
    ** `pause` once made every dialogue test fail. */
    gameplay_input_t in = {0};
    in.room = test_room;
    in.pause = pause != 0;
    in.menu_step = (int8_t)menu_step;
    in.x = x; in.y = y; in.z = z; in.yaw = (uint16_t)yaw;
    in.attack = attack != 0; in.shield = shield != 0;
    in.target = target != 0; in.interact = interact != 0;
    in.grounded = grounded != 0; in.cancel = cancel != 0;
    gameplay_step(&in);
}

void gp_step(int x, int y, int z, int yaw, int attack, int shield,
             int target, int interact, int grounded, int cancel)
{
    gp_step_full(x, y, z, yaw, attack, shield, target, interact, grounded,
                 cancel, 0, 0);
}

int gp_paused(void) { return gameplay_is_paused() ? 1 : 0; }
int gp_cursor(void) { return gameplay.cursor; }

int gp_talking(void)     { return gameplay_is_talking() ? 1 : 0; }
int gp_prompt(void)      { return gameplay.prompt; }
int gp_speaker(void)     { return gameplay.speaker; }
int gp_page(void)        { return gameplay.page; }
int gp_convo(void)       { return gameplay.convo; }
int gp_page_lines(void)  { return (int)gameplay_page_lines(); }

const char *gp_page_line(int i)   { return gameplay_page_line((unsigned)i); }
const char *gp_speaker_name(void) { return gameplay_speaker_name(); }

int gp_npc_param(int i)  { return kokiri_npcs[i].param; }
int gp_npc_kind(int i)   { return kokiri_npcs[i].kind; }
