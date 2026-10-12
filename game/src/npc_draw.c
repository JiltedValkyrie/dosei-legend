/* NPCs are baked sprites. Only scenery/shop props use meshes. */
/* Per-NPC logic, not per-vertex: size over speed (work RAM, BUG-043). */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "npc_draw.h"
#include "world_props_draw.h"
#include "actor_mesh.h"
#include "kokiri_actors.h"
#include "kokiri_sgl.h"
#include "gameplay.h"
#include "recomp.h"
#include "asset_loading.h"
#include "scene_flow.h"
#include "collide.h"
#include "npc_sprite.h"
#include "interior_mask.h"
#include "ram_cart.h"
#include "save_state.h"
#include "navi_npcs.h"
#include "kokiri_camera.h"
#include "cutscene.h"
#include "oot_core_host.h"
#include "perf_sub.h"

#define NPC_MODEL_COUNT 16
/* EnOssan OSSAN_TYPE_KOKIRI (build_npc_models SHOPKEEPER): drawn in the
 * shop at its actor-list spot, facing the counter (rot.y 0). Not a
 * kokiri_npcs entry: the counter talk in gameplay.c already owns her. */
#define NPC_SHOPKEEPER  15
#define NPC_SPRITE_RANGE 1500
static unsigned char *spr[NPC_MODEL_COUNT];
static npc_sprite_inst_t spr_inst[KOKIRI_NPC_COUNT + 1];
static bool navi_cast;
#define SPR(m) (spr[m])
/* En_Tana params 0 at its shop actor-list spot (0,0,-20), rot 0. */
static actor_mesh_t *shelves, *counter;
#define SHOP_SHELVES_X 0
#define SHOP_SHELVES_Y 0
#define SHOP_SHELVES_Z (-20)
/* EnOssan_SpawnItemsOnShelves, Kokiri row of sShopkeeperStores: shelf pos +
 * offset, rot.y + sItemShelfRot; EnGirlA shape.yOffset 24 x scale 0.25 = 6.
 * Mesh per GID (build_shop_props.py ITEMS). Buying stays at the counter
 * menu until the shelf cursor lands (M3d). */
#define SHOP_ITEM_MESHES 7
static const char *const shop_item_files[SHOP_ITEM_MESHES] = {
    "ITEMSHLD.BIN", "ITEMNUTS.BIN", "ITEMSTCK.BIN", "ITEMSEED.BIN",
    "ITEMARR5.BIN", "ITEMARRM.BIN", "ITEMHART.BIN" };
static const struct { int8_t mesh; int16_t x, y, z; uint16_t rot; } shop_slots[8] = {
    { 0,  50, 52, -20, 0xEAAC },   /* SI_DEKU_SHIELD */
    { 1,  50, 76, -20, 0xEAAC },   /* SI_DEKU_NUTS_5 */
    { 1,  80, 52,  -3, 0xEAAC },   /* SI_DEKU_NUTS_10 */
    { 2,  80, 76,  -3, 0xEAAC },   /* SI_DEKU_STICK */
    { 3, -50, 52, -20, 0x1554 },   /* SI_DEKU_SEEDS_30 */
    { 4, -50, 76, -20, 0x1554 },   /* SI_ARROWS_10: GID_ARROWS_5 */
    { 5, -80, 52,  -3, 0x1554 },   /* SI_ARROWS_30: GID_ARROWS_10 */
    { 6, -80, 76,  -3, 0x1554 },   /* SI_RECOVERY_HEART */
};
static actor_mesh_t *shop_items[SHOP_ITEM_MESHES];
/* EnGirlA yRotation (spin while selected) and EnOssan shopItemSelectedTween
** (Q8, 256 = at sSelectedItemPosition), advanced per 20 Hz source update. */
static uint16_t shop_spin[8];
static int shop_tween;
static const int16_t shop_selected_pos[2][3] = { { 17, 58, 30 }, { -17, 58, 30 } };
/* EnOssan_DrawCursor: 4 pulse tiles (build_shop_props.py shop_cursor). */
#define SHOP_CURSOR_PULSES 4
static uint16_t shop_cursor_slot[SHOP_CURSOR_PULSES];
static bool shop_cursor_loaded, shop_cursor_ready;
static int shop_cursor_tween, shop_cursor_rising = 1;   /* Q8 */
static unsigned int uploaded, bank_generation;
static unsigned int previous_step;
typedef char navi_sprite_capacity[NAVI_NPC_COUNT <= KOKIRI_NPC_COUNT && NAVI_NPC_COUNT <= 32 ? 1 : -1];
typedef char npc_visible_mask_fits[KOKIRI_NPC_COUNT <= 32 ? 1 : -1];

/* Sheet identity per placement; Saria's cue movement reuses her idle sheet. */
static unsigned int model_for(unsigned int i)
{
    return kokiri_npcs[i].kind == KOKIRI_NPC_MIDO ? 0 :
           kokiri_npcs[i].kind == KOKIRI_NPC_SARIA ? 1 :
           2 + (kokiri_npcs[i].param & 255);
}

void npc_draw_free(void)
{
    unsigned int i;
    for (i = 0; i < NPC_MODEL_COUNT; ++i)
        if (spr[i]) { jo_free(spr[i]); spr[i] = 0; }
    navi_cast = false;
    interior_mask_free();
    world_props_draw_free();
    actor_mesh_free(shelves); shelves = 0;
    actor_mesh_free(counter); counter = 0;
    for (i = 0; i < SHOP_ITEM_MESHES; ++i) { actor_mesh_free(shop_items[i]); shop_items[i] = 0; }
    shop_cursor_loaded = shop_cursor_ready = false;
    uploaded = 0;
    gameplay_npc_turns_reset();
    previous_step = recomp_world_clock() / 3;
}

static bool load_sprite(unsigned int model)
{
    char file[] = "NPC00.SPR";
    int length = 0;
    if (model >= NPC_MODEL_COUNT) return false;
    if (spr[model]) return true;
    file[3] = '0' + model / 10; file[4] = '0' + model % 10;
    asset_loading(file);
    spr[model] = (unsigned char *)jo_fs_read_file(file, &length);
    return spr[model] != 0;
}

bool __attribute__((optimize("Os"))) npc_draw_load(unsigned int scene)
{
    unsigned int i;
    npc_draw_free();
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i)
        if (kokiri_npcs[i].scene == scene && !load_sprite(model_for(i))) {
            npc_draw_free(); return false;
        }
    if (scene == SAVE_SCENE_KOKIRI_SHOP) {
        if (!load_sprite(NPC_SHOPKEEPER)) { npc_draw_free(); return false; }
        if (!interior_mask_load(SCENE_KOKIRI_SHOP)) { npc_draw_free(); return false; }
        asset_loading("SHELVES.BIN");
        shelves = actor_mesh_load_static("SHELVES.BIN");
        if (!shelves) { npc_draw_free(); return false; }
        counter = actor_mesh_load_static("COUNTER.BIN");
        if (!counter) { npc_draw_free(); return false; }
        {
            int length = 0;
            void *pixels = ram_cart_fixed(RAM_CART_CURSOR_OFFSET, RAM_CART_CURSOR_BYTES);
            shop_cursor_loaded = pixels && jo_fs_read_file_ptr("CURSOR.RGB", pixels, &length) &&
                                 length == SHOP_CURSOR_PULSES * 32 * 32 * 2;
            if (!shop_cursor_loaded) { npc_draw_free(); return false; }
        }
        for (i = 0; i < 8; ++i) shop_spin[i] = 0;
        shop_tween = 0;
        for (i = 0; i < SHOP_ITEM_MESHES; ++i) {
            asset_loading(shop_item_files[i]);
            shop_items[i] = actor_mesh_load_static(shop_item_files[i]);
            if (!shop_items[i]) { npc_draw_free(); return false; }

        }
    }
    if (!world_props_draw_load(scene)) { npc_draw_free(); return false; }
    asset_loading_done();
    uploaded = 0xFFFFFFFFu; /* force first actor/prop texture upload */
    bank_generation = kokiri_actor_bank_generation();
    return true;
}

void npc_draw_reupload(void) { uploaded = 0xFFFFFFFFu; }

static bool upload_visible(unsigned int visible, unsigned int generation)
{
    unsigned int i;
    /* Slots belong to placements for the entire room generation. Turning or
     * crossing an NPC's range must not upload all scenery/actor textures. */
    (void)visible;
    if (uploaded == 0xFFFFFFFFu || generation != bank_generation) {
        kokiri_actor_tiles_reset();
        /* Commit this cache key only after props and masks also fit. A
         * dismissed Jo error must not make a partial bank look complete. */
        uploaded = 0xFFFFFFFFu;
        bank_generation = generation;
        for (i = 0; i <= KOKIRI_NPC_COUNT; ++i) {
            unsigned int m;
            spr_inst[i].slot = NPC_SPRITE_SLOT_NONE;
            if (navi_cast) {
                if (i >= NAVI_NPC_COUNT) continue;
                m = navi_npcs[i].model;
            } else {
                if (i < KOKIRI_NPC_COUNT && kokiri_npcs[i].scene != save_state.scene_id) continue;
                m = i < KOKIRI_NPC_COUNT ? model_for(i) : NPC_SHOPKEEPER;
            }
            if (m < NPC_MODEL_COUNT && spr[m] &&
                !npc_sprite_upload(spr[m], &spr_inst[i])) {
                jo_core_error("NPC texture bank full: sprite %u", i);
                return false;
            }
        }
        if (counter && !actor_mesh_upload(counter)) return false;
        if (shelves && !actor_mesh_upload(shelves)) {
            jo_core_error("NPC texture bank full: shelves");
            return false;
        }
        for (i = 0; i < SHOP_ITEM_MESHES; ++i)
            if (shop_items[i] && !actor_mesh_upload(shop_items[i])) {
                jo_core_error("NPC texture bank full: item %u", i);
                return false;
            }
        shop_cursor_ready = false;
        if (shop_cursor_loaded) {
            const unsigned char *pixels = (const unsigned char *)
                ram_cart_fixed(RAM_CART_CURSOR_OFFSET, RAM_CART_CURSOR_BYTES);
            for (i = 0; i < SHOP_CURSOR_PULSES; ++i) {
                unsigned int slot = kokiri_bank_rgb_upload(pixels + i * 32 * 32 * 2, 32, 32);
                if (slot == KOKIRI_TILE_NONE) {
                    jo_core_error("NPC texture bank full: cursor");
                    return false;
                }
                shop_cursor_slot[i] = (uint16_t)slot;
            }
            shop_cursor_ready = true;
        }
        if (!world_props_draw_upload()) {
            jo_core_error("World prop texture bank full");
            return false;
        }
        if (!interior_mask_upload()) {
            jo_core_error("NPC texture bank full: masks");
            return false;
        }
#ifdef DOSEI_OOT_CORE
        oot_core_meshes_upload();   /* never starves the C uploads */
#endif
        /* Adult hero gear last: artwork never starves an actor. A full bank
         * keeps the selected source geometry with its baked flat colours. */
        (void)kokiri_link_gear_upload();
        uploaded = 0;
    }
    return true;
}

/* View-space projection matching main.c's matrix: flip X, RotX(-pitch),
 * RotY(-yaw), translate, on SGL (x,-y,z) coordinates. */
static bool shop_project(int32_t x, int32_t y, int32_t z, int *sx, int *sy)
{
    int32_t s, c, dx = x - recomp_camera.x, dy = recomp_camera.y - y, dz = z - recomp_camera.z;
    int32_t vx, vz, vy, depth;
    if (dx < -32767 || dx > 32767 || dy < -32767 || dy > 32767 ||
        dz < -32767 || dz > 32767) return false;
    kokiri_camera_sincos((uint16_t)(0u - (uint16_t)recomp_yaw), &s, &c);
    s /= 256; c /= 256;
    vx = (c * dx + s * dz) / 256;
    vz = (c * dz - s * dx) / 256;
    kokiri_camera_sincos((uint16_t)(0u - (uint16_t)recomp_pitch), &s, &c);
    s /= 256; c /= 256;
    vy = (c * dy - s * vz) / 256;
    depth = (s * dy + c * vz) / 256;
    if (depth <= 8) return false;
    *sx = -vx * recomp_screen_distance() / depth;
    *sy = vy * recomp_screen_distance() / depth;
    return true;
}

/* EnOssan_DrawCursor on EnOssan_UpdateCursorPos (the item's screen spot),
 * 16 x cursorZ 1.5 each side; colour pulse EnOssan_UpdateCursorAnim. */
static void shop_cursor_draw(int32_t x, int32_t y, int32_t z)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis, sprNoflip | FUNC_Sprite);
    int sx, sy, pulse = shop_cursor_tween * SHOP_CURSOR_PULSES / 257;
    if (!shop_cursor_ready || !shop_project(x, y, z, &sx, &sy)) return;
    if (shop_cursor_tween >= 230) return;           /* alpha nearly 0 */
    attr.texno = shop_cursor_slot[pulse];
    attr.atrb |= CL32KRGB | (shop_cursor_tween >= 128 ? CL_Trans : 0);
    pos[0] = sx * 65536;
    pos[2] = kokiri_hud_depth(1) * 65536;           /* HUD depth: over the world */
    pos[3] = pos[4] = 98304;                        /* x1.5 */
#ifdef DOSEI_HIRES
    pos[1] = sy * 2 * 65536;
    pos[4] = 2 * 98304;
    slDispSpriteHV(pos, &attr, 0);
#else
    pos[1] = sy * 65536;
    slDispSprite(pos, &attr, 0);
#endif
}

static void shop_items_draw(unsigned int steps)
{
    unsigned int i, n, st = gameplay.shop_state, cursor = gameplay.shop_cursor & 7;
    /* EnOssan_UpdateItemSelectedProperty: the cursor slot is selected while
     * browsing (drawCursor), choosing or refused; the tween takes it off the
     * shelf only while chosen (TakeItemOffShelf / ReturnItemToShelf). */
    bool browsing = st == GP_SHOP_BROWSE;
    bool chosen = st == GP_SHOP_SELECTED || st == GP_SHOP_RESULT;
    for (n = 0; n < steps; ++n) {
        for (i = 0; i < 8; ++i) {
            if ((browsing || chosen) && i == cursor) {
                shop_spin[i] = (uint16_t)(shop_spin[i] + 0x1F4);
            } else {                                /* Math_SmoothStepToS(,0,10,0x7D0,0) */
                int d = (int16_t)(0u - shop_spin[i]) / 10;
                if (d > 0x7D0) d = 0x7D0;
                if (d < -0x7D0) d = -0x7D0;
                shop_spin[i] = d ? (uint16_t)(shop_spin[i] + d) : 0;
            }
        }
        if (chosen) {                               /* ApproachF(1, 1, 0.15) */
            shop_tween += 38;
            if (shop_tween >= 218) shop_tween = 256;
        } else if (st == GP_SHOP_QUICK || st == GP_SHOP_GET) {
            shop_tween = 0;                         /* HandleCanBuyItem reset */
        } else {
            shop_tween -= 38;
            if (shop_tween <= 38) shop_tween = 0;
        }
        shop_cursor_tween += shop_cursor_rising ? 13 : -13;   /* 0.05 */
        if (shop_cursor_tween >= 256) { shop_cursor_tween = 256; shop_cursor_rising = 0; }
        if (shop_cursor_tween <= 0) { shop_cursor_tween = 0; shop_cursor_rising = 1; }
    }
    for (i = 0; i < 8; ++i) {
        int32_t ox = shop_slots[i].x, oy = shop_slots[i].y, oz = shop_slots[i].z;
        if (i == cursor && shop_tween) {            /* EnOssan_PositionSelectedItem */
            const int16_t *to = shop_selected_pos[i >> 2];
            ox += (to[0] - ox) * shop_tween / 256;
            oy += (to[1] - oy) * shop_tween / 256;
            oz += (to[2] - oz) * shop_tween / 256;
        }
        actor_mesh_draw_static(shop_items[shop_slots[i].mesh],
                               SHOP_SHELVES_X + ox, SHOP_SHELVES_Y + oy + 6,
                               SHOP_SHELVES_Z + oz,
                               (uint16_t)(shop_slots[i].rot + shop_spin[i]));
        if (browsing && i == cursor)                /* focus: world.pos + 5 */
            shop_cursor_draw(SHOP_SHELVES_X + ox, SHOP_SHELVES_Y + oy + 5,
                             SHOP_SHELVES_Z + oz);
    }
}

void npc_draw(unsigned int tick)
{
    unsigned int i, visible = 0, people = 0;
    unsigned int steps = tick / 3 - previous_step;
    unsigned int generation = kokiri_actor_bank_generation();
    previous_step = tick / 3;
    if (steps > 4) steps = 4;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        int32_t dx, dz, distance;
        if (!gameplay_npc_present(i)) continue;
        dx = gameplay_npc_x(i) - recomp_link.x;
        dz = gameplay_npc_z(i) - recomp_link.z;
        /* EnKo sInteractInfo / EnMd_UpdateAlphaByDistance / EnSa_Update.
         * Interiors always show their whole cast. Fade interpolation is
         * separate from this visibility bound. */
        distance = kokiri_npcs[i].kind == KOKIRI_NPC_CHILD ?
                   ((kokiri_npcs[i].param & 255) == 5 ? 240 : 180) : 400;
        /* Saturn: a sprite costs one cel, so it shows far past the 3D fade
         * range (human 2026-10-03). Logic/talk ranges are unchanged. */
        if (SPR(model_for(i))) distance = NPC_SPRITE_RANGE;
        /* EnSa_Update pins alpha to 255 while EnSa_HandleCutscene runs, so the
         * distance fade does not apply: her first cue stands her 900 units out
         * and she has to be on screen from the first frame of the shot. */
        if (!scene_flow_is_interior() && !(gameplay_saria_cutscene() &&
              kokiri_npcs[i].kind == KOKIRI_NPC_SARIA) &&
            (dx < -distance || dx > distance || dz < -distance || dz > distance ||
             dx * dx + dz * dz > distance * distance)) continue;
        visible |= 1u << model_for(i);
        people |= 1u << i;
    }
    if (spr[NPC_SHOPKEEPER] && save_state.scene_id == SAVE_SCENE_KOKIRI_SHOP)
        visible |= 1u << NPC_SHOPKEEPER;
    if (!upload_visible(visible, generation)) return;
    interior_mask_draw();
    if (recomp_shop_browsing()) actor_mesh_draw_static(counter, 0, 0, 0, 0);
    world_props_draw(tick);
    actor_mesh_draw_static(shelves, SHOP_SHELVES_X, SHOP_SHELVES_Y, SHOP_SHELVES_Z, 0);
    if (shelves) {
        shop_items_draw(steps);
    }
    {
    PS_T0();
    if (visible & (1u << NPC_SHOPKEEPER))
        npc_sprite_draw(spr[NPC_SHOPKEEPER], &spr_inst[KOKIRI_NPC_COUNT], tick / 3,
                        KOKIRI_SHOPKEEPER_X, KOKIRI_SHOPKEEPER_Y, KOKIRI_SHOPKEEPER_Z, 0);
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i)
        if (people & (1u << i)) {
            unsigned int model = model_for(i);
            int32_t focus[3] = {0, npc_sprite_focus_y(spr[model]), 0};
            int32_t pos[3];
            uint16_t yaw;
            gameplay_npc_pose(i, pos, &yaw);
            unsigned int d0 = frame_timer_ticks();
            npc_sprite_draw(spr[model], &spr_inst[i], tick / 3, pos[0], pos[1], pos[2], yaw);
            PS_ACC(PS_NDRAW, frame_timer_ticks_to_us(frame_timer_ticks() - d0));
            gameplay_npc_focus(i, focus);
        }
    PS_ADD(PS_DPPL);
    }
}

/* Greeting uses the resident sprite; cue movement and dialogue stay live. */
bool npc_draw_load_saria_cutscene(void) { return spr[1] != 0; }
void npc_draw_free_saria_cutscene(void) {}

/* Authored flyby cast is independent of Link's current save scene. */
bool npc_draw_load_navi(void)
{
    unsigned int i;
    npc_draw_free();
    navi_cast = true;
    for (i = 0; i < NAVI_NPC_COUNT; ++i)
        if (!load_sprite(navi_npcs[i].model)) { npc_draw_free(); return false; }
    uploaded = 0xFFFFFFFFu;
    return true;
}

/* Q8 view rotation: callers bound deltas to 1600 before multiplication. */
static bool navi_in_view(const navi_npc_t *p)
{
    int32_t sy,cy,sp,cp;
    int x=p->x-recomp_camera.x, y=p->y+40-recomp_camera.y, z=p->z-recomp_camera.z;
    int horizontal,depth,right,up;
    int distance=(int)cutscene_screen_distance();
    kokiri_camera_sincos(recomp_yaw,&sy,&cy);
    kokiri_camera_sincos(recomp_pitch,&sp,&cp);
    sy /= 256; cy /= 256; sp /= 256; cp /= 256;
    horizontal=(x*sy+z*cy)/256;
    right=(-x*cy+z*sy)/256;
    depth=(horizontal*cp+y*sp)/256;
    up=(y*cp-horizontal*sp)/256;
    if (depth+100<=0) return false;
    if (right<0) right=-right;
    if (up<0) up=-up;
    return right*distance <= depth*200+100*(distance+200) &&
           up*distance <= depth*200+100*(distance+200);
}

void npc_draw_navi(unsigned int frame)
{
    unsigned int i, people = 0, visible = 0;
    for (i = 0; i < NAVI_NPC_COUNT; ++i) {
        const navi_npc_t *p = &navi_npcs[i];
        int dx = recomp_camera.x-p->x, dy = recomp_camera.y-p->y, dz = recomp_camera.z-p->z;
        int radius = p->model == 0 ? 1600 : p->model == 7 ? 960 : 720;
        if (dx < -radius || dx > radius || dy < -radius || dy > radius ||
            dz < -radius || dz > radius || dx*dx+dy*dy+dz*dz > radius*radius) continue;
        if (navi_in_view(p)) { people |= 1u << i; visible |= 1u << p->model; }
    }
    if (!upload_visible(visible,kokiri_actor_bank_generation())) return;
    for (i = 0; i < NAVI_NPC_COUNT; ++i) if (people & (1u << i)) {
        const navi_npc_t *p = &navi_npcs[i];
        npc_sprite_draw(spr[p->model], &spr_inst[i], frame, p->x,p->y,p->z,p->yaw);
    }
}
