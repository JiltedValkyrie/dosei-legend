/* Host adapter for gameplay.c: the only thing the Saturn supplies that a PC
** cannot is the binang heading, so that is all this stands in for. Everything
** under test -- inventory, pickups, targeting, the swing window, the shield and
** grass cutting -- is the real game code. */
#include <math.h>
#include <assert.h>
#include <stdint.h>
#include "../../src/gameplay.h"
#include "../../src/collide.h"
#include "kokiri_actors.h"
#include "kokiri_dialogue.h"
#include "dialogue_text.h"
#include "../../src/save_file.h"
#include "../../src/actor_sys.h"
#include "../../src/attention.h"
#include "../../src/karebaba.h"
#include "../../src/game_over.h"
#include <limits.h>

uint16_t gameplay_facing(int32_t dx, int32_t dz)
{
    /* Match the Saturn adapter's signed Q16 input range. */
    assert(dx >= -32768 && dx <= 32767 && dz >= -32768 && dz <= 32767);
    double angle = atan2((double)dx, (double)dz);
    double turns = angle / 6.283185307179586;
    return (uint16_t)(int32_t)(turns * 65536.0);
}

static unsigned char contact_storage[0x2000];
__attribute__((constructor)) static void bind_contacts(void)
{
    gameplay_contacts_init(contact_storage, sizeof(contact_storage));
}
/* Actor pool (cart on Saturn). setUp clears it between tests. */
static unsigned char actor_storage[0x2000];
static unsigned char baba_storage[0x1000] __attribute__((aligned(8)));
__attribute__((constructor)) static void bind_actors(void)
{
    actor_sys_init(actor_storage, sizeof(actor_storage));
    karebaba_init(baba_storage, sizeof(baba_storage));
}
void gp_actors_clear(void) { actor_sys_clear(); }

/* Sight stub: a line ending at x == blocked_x is blocked. */
static int blocked_x = INT_MIN;
void gp_sight_block_x(int x) { blocked_x = x; }
bool attention_sight_blocked(const int32_t a[3], const int32_t b[3])
{
    (void)a;
    return b[0] == blocked_x;
}

/* On-screen stub: a focus at x == offscreen_x is off screen. */
static int offscreen_x = INT_MIN;
void gp_offscreen_x(int x) { offscreen_x = x; }
bool attention_on_screen(const int32_t p[3]) { return p[0] != offscreen_x; }

/* Karebaba bg stand-in: a flat floor at y = floor_y. */
static int baba_floor_y = -100000;
void gp_baba_floor(int y) { baba_floor_y = y; }
bool karebaba_bg_move(int32_t pos[3], const int32_t d[3], bool *ground, bool *wall)
{
    pos[0] += d[0]; pos[1] += d[1]; pos[2] += d[2];
    *wall = false;
    *ground = pos[1] <= baba_floor_y * 256;
    if (*ground) pos[1] = baba_floor_y * 256;
    return *ground;
}
int  gp_baba_count(void) { return (int)karebaba_count(); }
int  gp_baba_action(int i) { const karebaba_t *b = karebaba_at(i); return b ? b->action : -1; }
unsigned gp_baba_handle(int i) { const karebaba_t *b = karebaba_at(i); return b ? b->handle : 0; }
void gp_baba_home(int i, int *x, int *y, int *z) { const karebaba_t *b = karebaba_at(i); *x = b->home[0]; *y = b->home[1]; *z = b->home[2]; }
void gp_baba_pos(int i, int *x, int *y, int *z) { const karebaba_t *b = karebaba_at(i); *x = b->pos_q8[0] >> 8; *y = b->pos_q8[1] >> 8; *z = b->pos_q8[2] >> 8; }
/* Stand-in for a sword AC hit on the body (the collision pass itself has
** its own tests); set after a step so the next tick reads it. */
void gp_baba_hit(int i) { karebaba_t *b = (karebaba_t *)karebaba_at(i); if (b) b->hit = true; }
int  gp_baba_body_hard(int i) { const karebaba_t *b = karebaba_at(i); return (b->body.ac_flags & COL_AC_HARD) != 0; }
int  gp_baba_events(void) { return (int)karebaba_events(); }
int  gp_stick_ammo(void) { return save_state.stick_ammo; }
int  gp_stick_upgrade(void) { return save_state.stick_upgrade; }
void gp_sticks(int owned, int ammo, int upgrade) { save_state.stick_owned = (uint8_t)owned; save_state.stick_ammo = (uint8_t)ammo; save_state.stick_upgrade = (uint8_t)upgrade; }

/* A bare attention actor (enemy stand-in) for M2d tests. */
static const actor_profile_t test_enemy = { 0xF0E1, ACTORCAT_ENEMY, ACTOR_FLAG_TARGETABLE, 0, 0, 0, 0 };
unsigned gp_spawn_enemy(int x, int y, int z, int fx, int fy, int fz, int range, int arrow)
{
    actor_t *a = actor_spawn(&test_enemy, 0, ACTOR_ROOM_NONE, x, y, z, 0, 0);
    if (!a) return 0;
    a->attention = ATTN_ENEMY;
    a->range = (uint8_t)range;
    a->focus[0] = (int16_t)fx; a->focus[1] = (int16_t)fy; a->focus[2] = (int16_t)fz;
    a->arrow_y = (int16_t)arrow;
    return actor_handle(a);
}
void gp_actor_move(unsigned h, int x, int y, int z)
{
    actor_t *a = actor_resolve(h);
    if (a) { a->x = x; a->y = y; a->z = z; }
}
void gp_actor_targetable(unsigned h, int on)
{
    actor_t *a = actor_resolve(h);
    if (!a) return;
    if (on) a->flags |= ACTOR_FLAG_TARGETABLE; else a->flags &= ~ACTOR_FLAG_TARGETABLE;
}
void gp_actor_attention(unsigned h, int kind)
{
    actor_t *a = actor_resolve(h);
    if (a) a->attention = (uint8_t)kind;
}
void gp_actor_kill(unsigned h) { actor_kill(actor_resolve(h)); }
void gp_actors_reap(void) { actor_sys_update(); }
unsigned gp_target_handle(void) { return gameplay.target; }
unsigned gp_arrow_handle(void)  { return gameplay.arrow; }
unsigned gp_npc_handle(int npc)
{
    unsigned i;
    for (i = 0; i < ACTOR_POOL_MAX; ++i) {
        actor_t *a = actor_sys_slot(i);
        if (a && !a->kill && a->profile->id == 0xF001 && a->params == npc)
            return actor_handle(a);
    }
    return 0;
}
void gp_actor_pos(unsigned h, int *x, int *y, int *z)
{
    actor_t *a = actor_resolve(h);
    *x = a ? a->x : 0; *y = a ? a->y : 0; *z = a ? a->z : 0;
}
void gp_navi_hover(int *x, int *y, int *z)
{
    int32_t p[3];
    attention_navi_hover(p);
    *x = p[0]; *y = p[1]; *z = p[2];
}
int gp_navi_colour(void) { return (int)attention_navi_colour(); }
int gp_navi_moving(void) { return attention_navi_moving(); }
int gp_navi_has_actor(void) { return attention_navi_has_actor(); }
void gp_mido_pos(int *x, int *z) { *x = (int)gameplay.mido_x; *z = (int)gameplay.mido_z; }

int gp_contacts_bytes(void) { return (int)gameplay_contacts_bytes(); }

void gameplay_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    double a = yaw * 6.283185307179586 / 65536.0;
    *sine = (int32_t)lround(sin(a) * 65536.0);
    *cosine = (int32_t)lround(cos(a) * 65536.0);
}

/* Stand-in world: a wall at x = wall_x (when set) stops pushes. */
static int32_t wall_x = 0x7FFFFFFF;
void    co_wall(int x) { wall_x = x; }
void    collide_world_push(actor_t *a, int32_t dx, int32_t dz)
{
    a->x += dx;
    if (a->x > wall_x) a->x = wall_x;
    a->z += dz;
}

uint16_t collide_heading(int32_t dx, int32_t dz)
{
    return gameplay_facing(dx, dz);
}

/* Sword/nut platform hooks. Blade points off by default: the sector
** stand-in keeps the old tests' reach. */
static int test_blade_on, test_blade_wall, test_ball_wall;
static int32_t test_blade[2][3];
void gp_blade_set(int on, int bx, int by, int bz, int tx, int ty, int tz)
{
    test_blade_on = on;
    test_blade[0][0] = bx; test_blade[0][1] = by; test_blade[0][2] = bz;
    test_blade[1][0] = tx; test_blade[1][1] = ty; test_blade[1][2] = tz;
}
void gp_blade_wall(int on) { test_blade_wall = on; }
void gp_ball_wall(int on)  { test_ball_wall = on; }
bool gameplay_blade_points(int32_t base[3], int32_t tip[3])
{
    int k;
    if (!test_blade_on) return false;
    for (k = 0; k < 3; ++k) { base[k] = test_blade[0][k]; tip[k] = test_blade[1][k]; }
    return true;
}
bool gameplay_blade_wall(const int32_t from[3], const int32_t to[3], unsigned int *material)
{
    (void)from; (void)to; *material = 0;
    return test_blade_wall != 0;
}
bool gameplay_ball_move(int32_t pos[3], int32_t dx, int32_t dy, int32_t dz)
{
    pos[0] += dx; pos[1] += dy; pos[2] += dz;
    return test_ball_wall != 0 || pos[1] < -1000;
}
int  gp_nut_state(void)   { return gameplay.nut_state; }
int  gp_nut_reflected(void) { return gameplay.nut_reflected; }
int  gp_nut_yaw(void)     { return gameplay.nut_yaw; }
void gp_nut_pos(int *x, int *y, int *z) { *x = gameplay.nut_x >> 16; *y = gameplay.nut_y >> 16; *z = gameplay.nut_z >> 16; }
int  gp_hurt(void)        { return gameplay.hurt_pending; }
void gp_set_bounced(void) { gameplay.blade_bounced = true; }

/* Small readers so the test does not have to mirror the struct layout. */
int gp_owned(void)      { return gameplay.owned; }
int gp_equipped(void)   { return gameplay.equipped; }
int gp_target(void)     { return gameplay_target_npc(); }
int gp_target_hold(void){ return gameplay.target_hold; }
int gp_swing(void)      { return gameplay.swing; }
int gp_events(void)     { return (int)gameplay.events; }
int gp_cut_count(void)  { return gameplay.cut_count; }
int gp_shielding(void)  { return gameplay.shielding ? 1 : 0; }
int gp_face_locked(void){ return gameplay.face_locked ? 1 : 0; }
int gp_face_yaw(void)   { return gameplay.face_yaw; }
int gp_grass_total(void){ return KOKIRI_GRASS_COUNT; }
int gp_npc_total(void)  { return KOKIRI_NPC_COUNT; }
/* Test setup only: put gear in the save and the cache, owned and equipped,
** the way the pause menu leaves it. The game has no such grant. */
void gp_grant(int item)
{
    gameplay.owned |= (uint8_t)item;
    gameplay.equipped |= (uint8_t)item;
    if (item & GP_SWORD) {
        save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI);
        save_set_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI);
    }
    if (item & GP_SHIELD) {
        save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU);
        save_set_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU);
    }
}

void gp_scene(int scene)   { save_state.scene_id = (uint8_t)scene; }
int  gp_chest_total(void)  { return KOKIRI_CHEST_COUNT; }
void gp_chest_at(int i, int *x, int *y, int *z, int *yaw, int *room)
{
    *x = kokiri_chests[i].x; *y = kokiri_chests[i].y; *z = kokiri_chests[i].z;
    *yaw = kokiri_chests[i].yaw; *room = kokiri_chests[i].room;
}
int  gp_chest_param(int i) { return kokiri_chests[i].param; }
int  gp_chest_prompt(void) { return gameplay.chest_prompt; }
int  gp_get_item(void)     { return gameplay.get_item; }
int  gp_wonder_total(void) { return KOKIRI_WONDER_COUNT; }
void gp_wonder_at(int i, int *x, int *y, int *z, int *mode, int *value,
                  int *room, int *rot_z, int *param)
{
    const kokiri_wonder_t *w = &kokiri_wonders[i];
    *x = w->x; *y = w->y; *z = w->z; *mode = w->mode; *value = w->value;
    *room = w->room; *rot_z = w->rot_z; *param = w->param;
}
int  gp_wonder_done(void)  { return gameplay.wonder_done; }
int  gp_wonder_drop(int i) { return gameplay.wonder_drop[i]; }
int  gp_mido_x(void)       { return gameplay.mido_x; }
int  gp_mido_z(void)       { return gameplay.mido_z; }
int  gp_mido_state(void)   { return gameplay.mido_state; }
int  gp_shop_prompt(void)  { return gameplay.shop_prompt ? 1 : 0; }
int  gp_choice(void)       { return gameplay.choice; }
int  gp_choice_lines(void) { return (int)gameplay_choice_lines(); }
int  gp_mido_body(int room, int *x, int *z)
{
    int32_t bx, bz;
    if (!gameplay_mido_body((unsigned)room, &bx, &bz)) return 0;
    *x = bx; *z = bz;
    return 1;
}

void gp_grass_at(int i, int *x, int *y, int *z)
{
    *x = kokiri_grass[i].x; *y = kokiri_grass[i].y; *z = kokiri_grass[i].z;
}

void gp_npc_at(int i, int *x, int *y, int *z)
{
    *x = kokiri_npcs[i].x; *y = kokiri_npcs[i].y; *z = kokiri_npcs[i].z;
}

int  gp_health(void) { return save_state.health; }
int  gp_intangible(void) { return gameplay.intangible; }
void gp_health_set(int h, int cap) { save_state.health = (uint16_t)h; save_state.health_capacity = (uint16_t)cap; }
int  gp_dead(void) { return gameplay.dead ? 1 : 0; }
void gp_land(int fell, int rolled) { gameplay_land(fell, rolled != 0); }
void gp_void_respawned(void) { gameplay_void_respawned(); }
void gp_hurt_set(int damage, int yaw) { gameplay.hurt_pending = 1; gameplay.hurt_damage = (uint8_t)damage; gameplay.hurt_yaw = (uint16_t)yaw; }
int  gp_go_state(void) { return (int)game_over_state(); }
int  gp_go_step(int step, int confirm) { return (int)game_over_step(step, confirm != 0); }
void gp_go_save_done(int ok) { game_over_save_done(ok != 0); }
int  gp_go_events(void) { return (int)game_over_events(); }
int  gp_go_failed(void) { return game_over_save_failed() ? 1 : 0; }
void gp_go_reset(void) { game_over_reset(); }
void gp_death_anim_done(void) { gameplay_death_anim_done(); }

static int test_c_up;
void gp_c_up(int on) { test_c_up = on; }
void gp_navi_timer_set(int t) { save_state.navi_timer = (uint16_t)t; }
int  gp_navi_timer(void) { return save_state.navi_timer; }
int  gp_navi_text(void) { return gameplay.navi_text; }
int  gp_events2(void) { return (int)gameplay.events2; }
void gp_actor_navi_text(unsigned h, int text)
{
    actor_t *a = actor_resolve(h);
    if (a) a->navi_text = (uint16_t)text;
}
void gp_actor_hostile(unsigned h)
{
    actor_t *a = actor_resolve(h);
    if (a) a->flags |= ACTOR_FLAG_HOSTILE;
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
static int test_stick = -1, test_moving, test_held;
void gp_hold_x(int held) { test_held = held; }
int  gp_charge(void) { return gameplay.charge_q16; }
void gp_stick(int dir, int moving) { test_stick = dir; test_moving = moving; }
int  gp_attack_id(void)    { return gameplay.attack_id; }
int  gp_attack_phase(void) { return gameplay.attack_phase; }
int  gp_sword_live(void) { return gameplay_sword_active() ? 1 : 0; }
int  gp_attack_pose(void)
{
    unsigned int clip, frame;
    return gameplay_attack_pose(&clip, &frame) ? (int)(clip << 8 | frame) : -1;
}

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
    in.menu_dy = (int8_t)menu_step;
    in.x = x; in.y = y; in.z = z; in.yaw = (uint16_t)yaw;
    in.attack = attack != 0; in.shield = shield != 0;
    /* Hold targeting: this is L HELD for the step, not a press edge. */
    in.target_held = target != 0; in.interact = interact != 0;
    in.grounded = grounded != 0; in.cancel = cancel != 0;
    in.stick_dir = (int8_t)test_stick; in.moving = test_moving != 0;
    in.attack_held = test_held || attack != 0;
    /* Link's focus.pos: about 56 above the feet at idle. */
    in.focus[0] = x; in.focus[1] = y + 56; in.focus[2] = z;
    in.c_up = test_c_up != 0;
    gameplay_step(&in);
}

void gp_step(int x, int y, int z, int yaw, int attack, int shield,
             int target, int interact, int grounded, int cancel)
{
    gp_step_full(x, y, z, yaw, attack, shield, target, interact, grounded,
                 cancel, 0, 0);
}

int gp_paused(void) { return gameplay_is_paused() ? 1 : 0; }
int gp_cursor(void) { return gameplay.pause_window.cursor[gameplay.pause_window.page]; }
int gp_save_prompt(void) { return gameplay.pause_window.save_prompt; }
int gp_slot_count(void) { return GP_SLOT_COUNT; }
int gp_slot_item(int slot) { return (int)gameplay_slot_item((unsigned)slot); }
const char *gp_slot_name(int s) { return gameplay_slot_name((unsigned)s); }
const char *gp_slot_use(int s)  { return gameplay_slot_use((unsigned)s); }

int gp_talking(void)     { return gameplay_is_talking() ? 1 : 0; }
int gp_prompt(void)      { return gameplay.prompt; }
int gp_speaker(void)     { return gameplay.speaker; }
int gp_page(void)        { return gameplay.page; }
int gp_convo(void)       { return gameplay.rule; }
/* Which original message the selected rule points at. This is the check that
** matters for quest-correct dialogue: the rule index alone does not say
** whether Mido is about to speak his fresh-file line or a later-quest one. */
int gp_rule_text_id(void)
{
    if (gameplay.rule < 0) return -1;
    return (int)dialogue_rules[gameplay.rule].text_id;
}
int gp_page_lines(void)  { return (int)gameplay_page_lines(); }

const char *gp_page_line(int i)   { return gameplay_page_line((unsigned)i); }
const char *gp_speaker_name(void) { return gameplay_speaker_name(); }

int gp_npc_param(int i)  { return kokiri_npcs[i].param; }
int gp_npc_kind(int i)   { return kokiri_npcs[i].kind; }
int gp_npc_count(void)   { return KOKIRI_NPC_COUNT; }

/* The real serialiser, so a test can perform the same save and load the pause
** menu and the file select do, without a backup device. */
void gp_save_pack(unsigned char *out) { save_file_pack(&save_state, out); }
int  gp_save_unpack(const unsigned char *in, unsigned int bytes)
{
    return (int)save_file_unpack(&save_state, in, bytes);
}

int  gp_bind_text(const uint8_t *blob, uint32_t bytes) { return dialogue_text_bind(blob, bytes); }

int  gp_boulder(int *x, int *y, int *z) {
    *x = gameplay.boulder_x >> 16; *y = gameplay.boulder_y >> 16; *z = gameplay.boulder_z >> 16;
    return gameplay.boulder_state; }
int  gp_boulder_next(void) { return gameplay.boulder_next; }
int  gp_boulder_live(void) { return gameplay.boulder_live; }
int  gp_boulder_hit(void) { return gameplay.boulder_hit; }
int  gp_knock_yaw(void) { return gameplay.knock_yaw; }

int  gp_lunge(void) { return gameplay.lunge_q16; }
