/* Original En_Ko/En_Md/En_Sa meshes. Scene owns cart assets; room owns tiles. */
/* Per-NPC logic, not per-vertex: size over speed (work RAM, BUG-043). */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "npc_draw.h"
#include "world_props_draw.h"
#include "actor_mesh.h"
#include "kokiri_actors.h"
#include "kokiri_sgl.h"
#include "gameplay.h"
#include "demo.h"
#include "asset_loading.h"
#include "scene_flow.h"
#include "collide.h"
#include "npc_pose.h"
#include "interior_mask.h"
#include "ram_cart.h"
#include "save_state.h"
#include "navi_npcs.h"
#include "kokiri_camera.h"
#include "cutscene.h"

#define NPC_MODEL_COUNT 16
/* EnOssan OSSAN_TYPE_KOKIRI (build_npc_models SHOPKEEPER): drawn in the
 * shop at its actor-list spot, facing the counter (rot.y 0). Not a
 * kokiri_npcs entry: the counter talk in gameplay.c already owns her. */
#define NPC_SHOPKEEPER  15
/*
** Saria's greeting poses.
**
** EnSa_HandleCutscene indexes sAnimationInfo1 with the actor cue id: 1
** look-up/arm-extended, 2 wave, 3 run. Cue 4 is ENSA_ANIM1_MOVE_ARMS_TO_SIDE,
** whose clip is model 1's own, so it maps back to NPC01.
**
** These are clips, not models. They share Saria's skeleton, vertices and all
** 78 of her texture tiles, so they are swapped onto the loaded model 1 rather
** than loaded as meshes of their own: three more uploads of identical tiles
** filled the VDP1 bank and starved the world props.
*/
static const char *const saria_cue_clip[3] = { "NPC16", "NPC17", "NPC18" };
static unsigned char saria_clip_loaded;     /* cue id currently swapped in */
static actor_mesh_t *models[NPC_MODEL_COUNT];
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
static npc_track_t track[KOKIRI_NPC_COUNT];
static unsigned int previous_step;
typedef char navi_track_capacity[NAVI_NPC_COUNT <= KOKIRI_NPC_COUNT && NAVI_NPC_COUNT <= 32 ? 1 : -1];
typedef char npc_turn_mask_fits[KOKIRI_NPC_COUNT <= 32 ? 1 : -1];

/* EnKo child tracking functions (z_en_ko.c), by ENKO_TYPE. */
enum { KO_D68, KO_E18, KO_034, KO_F70, KO_EB0, KO_FULL };
static const uint8_t ko_start[13] = {   /* EnKo_ChildStart */
    KO_D68, KO_E18, KO_034, KO_E18, KO_F70, KO_EB0, KO_FULL,
    KO_EB0, KO_EB0, KO_EB0, KO_E18, KO_EB0, KO_E18 };
static const uint8_t ko_stone[13] = {   /* EnKo_ChildStone */
    KO_FULL, KO_FULL, KO_034, KO_EB0, KO_F70, KO_EB0, KO_FULL,
    KO_EB0, KO_EB0, KO_EB0, KO_E18, KO_EB0, KO_E18 };
/* func_80A97BC0 yOffset, CHILD_START / CHILD_STONE columns. */
static const int8_t ko_offset[2][13] = {
    { 0, 0, 0, -10, 0, 0, 0, 10, -10, -10, 0, -10, 0 },
    { 0, 0, 0, 10, 0, 0, 0, 10, -10, -10, 0, -10, 0 } };

/* Tracking mode, preset and yOffset for one NPC this step. */
static unsigned int track_mode(unsigned int i, int angle, int32_t distance,
                               unsigned int *preset, int32_t *offset)
{
    const kokiri_npc_t *npc = &kokiri_npcs[i];
    bool talking = gameplay.talking && gameplay.speaker == (int)i;
    bool facing = angle > -0x3FFC && angle < 0x3FFC;  /* EnKo_IsWithinTalkAngle */
    unsigned int type = npc->param & 255, stone;
    *preset = 2;
    if (npc->kind == KOKIRI_NPC_MIDO) {                 /* EnMd_UpdateTalking */
        bool gate = npc->scene == SAVE_SCENE_KOKIRI_FOREST;
        *offset = 0;
        if (gate && gameplay.mido_state == 1) return NPC_TRACKING_NONE;  /* EnMd_Walk */
        if (talking || (gate && gameplay.mido_state == 2)) return NPC_TRACKING_FULL_BODY;
        return distance < 170 && angle >= -0x3FFC && angle <= 0x3FFC ?
               NPC_TRACKING_HEAD_AND_TORSO : NPC_TRACKING_NONE;
    }
    if (npc->kind == KOKIRI_NPC_SARIA) {                /* EnSa_UpdateTrackingMode */
        *offset = 4;
        /* In Kokiri Forest the source returns NPC_TRACKING_NONE while
         * actionFunc is EnSa_HandleCutscene: the cue rotations own her facing
         * during the greeting, so she must not turn to look at Link. */
        return gameplay_saria_cutscene() ? NPC_TRACKING_NONE : NPC_TRACKING_FULL_BODY;
    }
    if (type > 12) type = 12;
    stone = save_check_quest_item(QUEST_KOKIRI_EMERALD);
    *offset = ko_offset[stone][type];
    switch ((stone ? ko_stone : ko_start)[type]) {
    case KO_D68:
        return talking ? NPC_TRACKING_HEAD_AND_TORSO : NPC_TRACKING_NONE;
    case KO_E18:
        if (talking) return NPC_TRACKING_FULL_BODY;
        /* lookDist: sInteractInfo + collider radius 20. */
        if (distance > (type == 5 ? 240 : 180) + 20) return NPC_TRACKING_NONE;
        return facing ? NPC_TRACKING_HEAD_AND_TORSO : NPC_TRACKING_NONE;
    case KO_034:
        *preset = 5;
        return talking && facing ? NPC_TRACKING_HEAD_AND_TORSO : NPC_TRACKING_NONE;
    case KO_F70:
        *preset = 5;
        return talking ? NPC_TRACKING_HEAD_AND_TORSO : NPC_TRACKING_NONE;
    case KO_EB0:
        return facing ? NPC_TRACKING_HEAD_AND_TORSO : NPC_TRACKING_NONE;
    default:
        return NPC_TRACKING_FULL_BODY;
    }
}

/* One 20 Hz source update: Npc_TrackPoint toward Link's feet. */
static void track_step(unsigned int i)
{
    int32_t dx = demo_link.x - gameplay_npc_x(i);
    int32_t dz = demo_link.z - gameplay_npc_z(i);
    int32_t distance = (int32_t)collide_isqrt((uint32_t)(dx*dx + dz*dz)), offset;
    uint16_t shape = gameplay_npc_yaw(i);
    int16_t yaw_to = (int16_t)gameplay_facing(dx, dz);
    unsigned int preset, mode = track_mode(i, (int16_t)(yaw_to - (int16_t)shape),
                                           distance, &preset, &offset);
    int16_t pitch_to = (int16_t)gameplay_facing(gameplay_npc_y(i) + offset -
                                                (demo_link.y - DEMO_LINK_EYE_HEIGHT),
                                                distance);
    npc_track_point(&track[i], &shape, yaw_to, pitch_to, preset, mode);
    if (mode == NPC_TRACKING_FULL_BODY) gameplay_npc_turn(i, shape);
}

static int32_t q14_sin(int16_t a) { return slSin((ANGLE)a) / 4; }
static int32_t q14_cos(int16_t a) { return slCos((ANGLE)a) / 4; }

/*
** The model a placement owns for as long as the scene is loaded.
**
** This is what npc_draw_load reads to decide which NPC<nn>.BIN the scene
** needs, so it must never name one of Saria's greeting clips: those are
** loaded and freed by the greeting itself, and asking the scene loader for
** one fails to open a file that is not part of the scene at all.
*/
static unsigned int model_for(unsigned int i)
{
    return kokiri_npcs[i].kind == KOKIRI_NPC_MIDO ? 0 :
           kokiri_npcs[i].kind == KOKIRI_NPC_SARIA ? 1 :
           2 + (kokiri_npcs[i].param & 255);
}

/*
** Follow the cue's clip on Saria's one model.
**
** Called once per drawn frame while the greeting owns her. A failed swap keeps
** whatever clip is already on the mesh: a wrong-looking pose is better than a
** hard stop in the middle of her cutscene.
*/
static void saria_follow_cue(void)
{
    unsigned int cue = cutscene_actor_channel_cue(GAMEPLAY_SARIA_CUE_CHANNEL);
    unsigned int want = cue >= 1 && cue <= 3 ? cue : 0;

    if (!models[1] || want == saria_clip_loaded) return;
    if (want == 0) {
        if (actor_mesh_swap_clip(models[1], "NPC01")) saria_clip_loaded = 0;
        return;
    }
    if (actor_mesh_swap_clip(models[1], saria_cue_clip[want - 1]))
        saria_clip_loaded = (unsigned char)want;
}

void npc_draw_free(void)
{
    unsigned int i;
    for (i = 0; i < NPC_MODEL_COUNT; ++i) {
        actor_mesh_free(models[i]); models[i] = 0;
    }
    interior_mask_free();
    world_props_draw_free();
    actor_mesh_free(shelves); shelves = 0;
    actor_mesh_free(counter); counter = 0;
    for (i = 0; i < SHOP_ITEM_MESHES; ++i) { actor_mesh_free(shop_items[i]); shop_items[i] = 0; }
    shop_cursor_loaded = shop_cursor_ready = false;
    /* The models are gone, so whatever clip was swapped onto Saria went with
    ** them: a fresh NPC01 carries her idle clip again. */
    saria_clip_loaded = 0;
    uploaded = 0;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) track[i] = (npc_track_t){{0, 0}, {0, 0}};
    gameplay_npc_turns_reset();
    previous_step = demo_world_clock() / 3;
}

bool __attribute__((optimize("Os"))) npc_draw_load(unsigned int scene)
{
    unsigned int i;
    npc_draw_free();
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        unsigned int model = model_for(i);
        char file[] = "NPC00.BIN";
        if (kokiri_npcs[i].scene != scene) continue;
        if (model >= NPC_MODEL_COUNT) { npc_draw_free(); return false; }
        if (models[model]) continue;
        file[3] = '0' + model / 10; file[4] = '0' + model % 10;
        asset_loading(file);
        models[model] = actor_mesh_load(file);
        if (!models[model]) { npc_draw_free(); return false; }
    }
    if (scene == SAVE_SCENE_KOKIRI_SHOP) {
        asset_loading("NPC15.BIN");
        models[NPC_SHOPKEEPER] = actor_mesh_load("NPC15.BIN");
        if (!models[NPC_SHOPKEEPER]) { npc_draw_free(); return false; }
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

static void draw_pose(unsigned int model, unsigned int tick,
              int x, int y, int z, uint16_t yaw,
              const npc_track_t *t, int32_t focus[3])
{
    int16_t head[9], torso[9];

    bool turn_head = t->head[0] || t->head[1];
    bool turn_torso = t->torso[0] || t->torso[1];
    /* Override limb draws: head Rx(y) Rz(x) about its pivot; torso
     * EnKo Rx(-y) Rz(x), EnMd Rx(x) Ry(y), EnSa Ry(y) Rx(x). */
    if (turn_head)
        npc_rot_matrix(head, 0, q14_sin(t->head[1]), q14_cos(t->head[1]),
                       2, q14_sin(t->head[0]), q14_cos(t->head[0]));
    if (turn_torso) {
        int16_t tx = t->torso[0], ty = t->torso[1];
        if (model == 0)
            npc_rot_matrix(torso, 0, q14_sin(tx), q14_cos(tx), 1, q14_sin(ty), q14_cos(ty));
        else if (model == 1)
            npc_rot_matrix(torso, 1, q14_sin(ty), q14_cos(ty), 0, q14_sin(tx), q14_cos(tx));
        else
            npc_rot_matrix(torso, 0, q14_sin((int16_t)-ty), q14_cos((int16_t)-ty),
                           2, q14_sin(tx), q14_cos(tx));
    }
    actor_mesh_draw(models[model], tick / 3,
                    x, y, z, yaw,
                    turn_head ? head : 0, turn_torso ? torso : 0, focus);
}

static bool upload_visible(unsigned int visible, unsigned int generation)
{
    unsigned int i;
    if (visible != uploaded || generation != bank_generation) {
        kokiri_actor_tiles_reset();
        /* Commit this cache key only after props and masks also fit. A
         * dismissed Jo error must not make a partial bank look complete. */
        uploaded = 0xFFFFFFFFu;
        bank_generation = generation;
        for (i = 0; i < NPC_MODEL_COUNT; ++i) {
            if (!(visible & (1u << i))) continue;
            if (!actor_mesh_upload(models[i])) {
                jo_core_error("NPC texture bank full: %u", i);
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
        uploaded = visible;
    }
    return true;
}

/* View-space projection matching main.c's matrix: flip X, RotX(-pitch),
 * RotY(-yaw), translate, on SGL (x,-y,z) coordinates. */
static bool shop_project(int32_t x, int32_t y, int32_t z, int *sx, int *sy)
{
    int32_t s, c, dx = x - demo_camera.x, dy = demo_camera.y - y, dz = z - demo_camera.z;
    int32_t vx, vz, vy, depth;
    kokiri_camera_sincos((uint16_t)(0u - (uint16_t)demo_yaw), &s, &c);
    vx = (int32_t)(((int64_t)c * dx + (int64_t)s * dz) >> 16);
    vz = (int32_t)(((int64_t)c * dz - (int64_t)s * dx) >> 16);
    kokiri_camera_sincos((uint16_t)(0u - (uint16_t)demo_pitch), &s, &c);
    vy = (int32_t)(((int64_t)c * dy - (int64_t)s * vz) >> 16);
    depth = (int32_t)(((int64_t)s * dy + (int64_t)c * vz) >> 16);
    if (depth <= 8) return false;
    *sx = -vx * demo_screen_distance() / depth;
    *sy = vy * demo_screen_distance() / depth;
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
    unsigned int i, n, visible = 0, people = 0;
    unsigned int steps = tick / 3 - previous_step;
    unsigned int generation = kokiri_actor_bank_generation();
    previous_step = tick / 3;
    if (steps > 4) steps = 4;
    if (gameplay_saria_cutscene()) saria_follow_cue();
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        int32_t dx, dz, distance;
        if (!gameplay_npc_present(i)) continue;
        dx = gameplay_npc_x(i) - demo_link.x;
        dz = gameplay_npc_z(i) - demo_link.z;
        /* EnKo sInteractInfo / EnMd_UpdateAlphaByDistance / EnSa_Update.
         * Interiors always show their whole cast. Fade interpolation is
         * separate from this visibility bound. */
        distance = kokiri_npcs[i].kind == KOKIRI_NPC_CHILD ?
                   ((kokiri_npcs[i].param & 255) == 5 ? 240 : 180) : 400;
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
    if (models[NPC_SHOPKEEPER] && save_state.scene_id == SAVE_SCENE_KOKIRI_SHOP)
        visible |= 1u << NPC_SHOPKEEPER;
    if (!upload_visible(visible, generation)) return;
    interior_mask_draw();
    if (demo_shop_browsing()) actor_mesh_draw_static(counter, 0, 0, 0, 0);
    world_props_draw(tick);
    actor_mesh_draw_static(shelves, SHOP_SHELVES_X, SHOP_SHELVES_Y, SHOP_SHELVES_Z, 0);
    if (shelves) {
        shop_items_draw(steps);
    }
    if (visible & (1u << NPC_SHOPKEEPER)) {
        static const npc_track_t still = {{0, 0}, {0, 0}};
        int32_t focus[3];
        draw_pose(NPC_SHOPKEEPER, tick, KOKIRI_SHOPKEEPER_X, KOKIRI_SHOPKEEPER_Y,
                  KOKIRI_SHOPKEEPER_Z, 0, &still, focus);
    }
    for (n = 0; n < steps; ++n)
        for (i = 0; i < KOKIRI_NPC_COUNT; ++i)
            if (gameplay_npc_present(i)) track_step(i);
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i)
        if (people & (1u << i)) {
            const npc_track_t *t = &track[i];
            unsigned int model = model_for(i);
            uint16_t yaw = gameplay_npc_yaw(i);
            int32_t focus[3], rotated[3];
            draw_pose(model, tick, gameplay_npc_x(i), gameplay_npc_y(i),
                      gameplay_npc_z(i), yaw, t, focus);
            {
                int32_t sine = slSin((ANGLE)yaw) / 4;
                int32_t cosine = slCos((ANGLE)yaw) / 4;
                rotated[0] = (focus[0]*cosine + focus[2]*sine) / (16384*64);
                rotated[1] = focus[1] / 64;
                rotated[2] = (focus[2]*cosine - focus[0]*sine) / (16384*64);
            }
            gameplay_npc_focus(i, rotated);
        }
}

/* Flythrough uses its authored layer, independent of save scene and Link's
 * position in his house. No gameplay actor registry or talk/target changes. */
/*
** Saria's three greeting clips, loaded beside the forest cast for the one
** cutscene that uses them and freed the moment it ends. Failing to load them
** must not start the greeting at all: she would otherwise stand in her idle
** pose through a shot built around her running up and waving.
*/
/*
** The greeting needs no assets of its own: its poses are clips on Saria's
** model, swapped in as her cue changes. This only checks she is actually
** loaded, so the greeting does not start in a scene without her.
*/
bool npc_draw_load_saria_cutscene(void)
{
    return models[1] != 0;
}

/* EnSa_BecomeIdle: back to gSariaWaitArmsToSideAnim. */
void npc_draw_free_saria_cutscene(void)
{
    if (models[1] && saria_clip_loaded)
        if (actor_mesh_swap_clip(models[1], "NPC01")) saria_clip_loaded = 0;
}

bool npc_draw_load_navi(void)
{
    unsigned int i;
    npc_draw_free();
    previous_step = 0;
    for (i = 0; i < NAVI_NPC_COUNT; ++i) {
        unsigned int model = navi_npcs[i].model;
        char file[] = "NPC00.BIN";
        if (model >= NPC_MODEL_COUNT) return false;
        if (models[model]) continue;
        file[3] = '0' + model / 10; file[4] = '0' + model % 10;
        asset_loading(file);
        models[model] = actor_mesh_load(file);
        if (!models[model]) { npc_draw_free(); return false; }
    }
    return true;
}

/* Conservative model sphere: child poses fit within 100 world units of
 * (origin+40Y). Cull whole offscreen actors before SGL consumes vertex slots. */
static bool navi_in_view(const navi_npc_t *p)
{
    int32_t sy,cy,sp,cp;
    int x=p->x-demo_camera.x, y=p->y+40-demo_camera.y, z=p->z-demo_camera.z;
    int horizontal,depth,right,up;
    unsigned int distance=cutscene_screen_distance();
    kokiri_camera_sincos(demo_yaw,&sy,&cy);
    kokiri_camera_sincos(demo_pitch,&sp,&cp);
    horizontal=(int)(((int64_t)x*sy+(int64_t)z*cy)/65536);
    right=(int)((-(int64_t)x*cy+(int64_t)z*sy)/65536);
    depth=(int)(((int64_t)horizontal*cp+(int64_t)y*sp)/65536);
    up=(int)(((int64_t)y*cp-(int64_t)horizontal*sp)/65536);
    if (depth+100<=0) return false;
    if (right<0) right=-right;
    if (up<0) up=-up;
    return (int64_t)right*distance <= (int64_t)depth*200+100*(distance+200) &&
           (int64_t)up*distance <= (int64_t)depth*200+100*(distance+200);
}

void npc_draw_navi(unsigned int frame)
{
    unsigned int i, n, people = 0, visible = 0;
    unsigned int steps = frame >= previous_step ? frame - previous_step : 0;
    previous_step = frame;
    if (steps > 4) steps = 4;
    for (i = 0; i < NAVI_NPC_COUNT; ++i) {
        const navi_npc_t *p = &navi_npcs[i];
        int dx = demo_camera.x-p->x, dy = demo_camera.y-p->y, dz = demo_camera.z-p->z;
        int radius = p->model == 0 ? 1600 : p->model == 7 ? 960 : 720;
        uint16_t yaw = p->yaw;
        if ((int64_t)dx*dx+(int64_t)dy*dy+(int64_t)dz*dz > radius*radius) continue;
        if (navi_in_view(p)) { people |= 1u << i; visible |= 1u << p->model; }
        /* EnKo func_80A9877C/EnMd_UpdateTalking: camera eye, +40 offset,
         * preset 2 head+torso; type 0 keeps its rock-lifting gaze. */
        if (p->model != 2) {
            int distance = collide_isqrt((uint32_t)(dx*dx+dz*dz));
            int16_t target_yaw = (int16_t)gameplay_facing(dx,dz);
            int16_t target_pitch = (int16_t)gameplay_facing(p->y+40-demo_camera.y,distance);
            for (n = 0; n < steps; ++n)
                npc_track_point(&track[i], &yaw, target_yaw, target_pitch,
                                2, NPC_TRACKING_HEAD_AND_TORSO);
        }
    }
    if (!upload_visible(visible,kokiri_actor_bank_generation())) return;
    for (i = 0; i < NAVI_NPC_COUNT; ++i) if (people & (1u << i)) {
        const navi_npc_t *p = &navi_npcs[i];
        int32_t focus[3];
        draw_pose(p->model,frame*3,p->x,p->y,p->z,p->yaw,&track[i],focus);
    }
}
