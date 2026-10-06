#pragma GCC optimize("Os") /* per-step logic, small: size over speed (work RAM) */
#pragma GCC optimize ("Os") /* Cold HUD/text updates; preserve high RAM. */
#include <jo/jo.h>
#include "minimap.h"
#include "minimap_data.h"
#include "recomp.h"
#include "cutscene.h"
#include "gameplay.h"
#include "kokiri_sgl.h"
#include "cheat_code.h"
#include "actor_sys.h"
#include "kokiri_actors.h"
#include "gameplay_hud_data.h"
#include "gameplay_hud_state.h"
#include "pause_windows.h"
#include "health_hud.h"
#include "ui_preferences.h"
#include "world_props.h"
#include "world_signs.h"
#include "dungeon_doors.h"
#include "ram_cart.h"
#include "pause_inventory_data.h"

static const uint8_t   *file;
static const minimap_row_t *row;        /* this scene's map, or 0 */
static bool             hidden;
static cheat_code_t     cheat, refill_cheat;
static volatile bool    refill_pending;
static volatile bool    enemy_dots, chime;
static int              marker_sprite = -1;
static bool             hud_ready, map_visible;
static int              hud_variant = -1;
static gameplay_hud_blink_t hud_blink;
static uint32_t         hud_items_key = ~0u, hud_actions_key = ~0u;
static unsigned         hud_item_front;
/* NBG2 palette nibble per composed C-item cell, per bank. */
static unsigned char    hud_item_palette[2][HUD_ITEM_COUNT];

/* Button cells reserve 16 KB at 0x25E44000. Label maps occupy at most 14 KB.
 * Four composed C banks (two assignments x two Navi states) fit the freed
 * map space; source item pixels use B0 slack beyond the heart banks. Pause
 * backs up/restores all these B0 regions. No runtime allocation required. */
#define HUD_NAMES ((volatile unsigned short *)0x25E48000u)
#define HUD_NAMES_CAPACITY 0x3800u
#define HUD_ITEM_CELLS ((volatile unsigned short *)0x25E4B800u)
#define HUD_ITEM_BANK_WORDS 1024u
#define HUD_ICON_ATLAS ((volatile unsigned short *)0x25E52000u)
static bool hud_file(const char *name, unsigned bytes, volatile unsigned short *dst)
{
    int length=0;
    unsigned i;
    /* Boot-only: pause scratch is free. One bulk CD read avoids 112 small
     * sector requests for the icon atlas; VDP2 still gets word writes. */
    const unsigned short *data=ram_cart_load_scratch(name,&length);
    if (!data || length!=(int)bytes) return false;
    for (i=0;i<bytes/2;++i) dst[i]=data[i];
    return true;
}
static bool hud_load(void)
{
    unsigned i;
    if (HUD_PIXEL_BYTES>0x4000u || HUD_MAP_BYTES>HUD_NAMES_CAPACITY ||
        !hud_file("BUTTONS.BIN", HUD_PIXEL_BYTES, (volatile unsigned short *)HUD_VRAM_CELLS) ||
        !hud_file("BUTTONS.MAP", HUD_MAP_BYTES, HUD_NAMES) ||
        PAUSE_ICON_BYTES > 0xE000u ||
        !hud_file("PAUSEINV.BIN", PAUSE_ICON_BYTES, HUD_ICON_ATLAS)) return false;
    for (i=0; i<16; ++i) ((volatile unsigned short *)JO_VDP2_CRAM)[HUD_CRAM+i]=hud_palette[i];
    hud_items_key = hud_actions_key = ~0u;
    return true;
}

bool minimap_icons_ready(void) { return hud_ready; }

static unsigned hud_icon_colour(unsigned colour)
{
    unsigned i, best=1, distance=~0u;
    for (i=1; i<16; ++i) {
        int r=(int)(colour&31)-(int)(hud_palette[i]&31);
        int g=(int)((colour>>5)&31)-(int)((hud_palette[i]>>5)&31);
        int b=(int)((colour>>10)&31)-(int)((hud_palette[i]>>10)&31);
        unsigned d=r*r+g*g+b*b;
        if (d<distance) { best=i; distance=d; }
    }
    return best;
}

static void hud_item_pixel(volatile unsigned short *cells,unsigned x,unsigned y,unsigned colour)
{
    unsigned at=((y/8)*HUD_ITEM_W+x/8)*16+(y&7)*2+(x&7)/4;
    unsigned shift=(3-(x&3))*4, word=cells[at];
    cells[at]=(unsigned short)((word&~(15u<<shift))|(colour<<shift));
}

static const unsigned char hud_item_at[3][2]={{25,18},{3,2},{47,2}};
typedef struct {
    const volatile unsigned char *record[3];
    unsigned short rgb[3][16];
} hud_item_art_t;

static unsigned hud_source_index(unsigned tile,unsigned x,unsigned y)
{
    const volatile unsigned short *source=(const volatile unsigned short *)HUD_VRAM_CELLS;
    return (source[tile*16+(y&7)*2+(x&7)/4]>>((3-(x&3))*4))&15;
}

/* Composed RGB555|0x8000 of one item-region pixel; 0 = transparent. Later
 * slots overwrite earlier ones, and Navi's overlay sits on top. */
static unsigned hud_item_rgb(const hud_item_art_t *art,unsigned px,unsigned py,bool navi)
{
    unsigned cell=(py/8)*HUD_ITEM_W+px/8, slot, index, colour;
    if (navi && (index=hud_source_index(HUD_NAMES[HUD_NAVI_OFFSET+cell],px,py)))
        return 0x8000u|(hud_palette[index]&0x7FFFu);
    index=hud_source_index(HUD_NAMES[(HUD_ITEM_Y+cell/HUD_ITEM_W)*HUD_MAP_W+
                                     HUD_ITEM_X+cell%HUD_ITEM_W],px,py);
    colour=index ? 0x8000u|(hud_palette[index]&0x7FFFu) : 0;
    for (slot=0; slot<3; ++slot) {
        unsigned x=px-hud_item_at[slot][0], y=py-hud_item_at[slot][1], sample;
        if (!art->record[slot] || x>=26 || y>=26) continue;
        sample=(y*28/26)*28+x*28/26;
        index=(art->record[slot][32+sample/2]>>(sample&1 ? 0 : 4))&15;
        if (index) colour=0x8000u|art->rgb[slot][index];
        else {
            index=hud_source_index(HUD_NAMES[HUD_ITEM_OFFSET+cell],px,py);
            colour=index ? 0x8000u|(hud_palette[index]&0x7FFFu) : 0;
        }
    }
    return colour;
}

static unsigned hud_rgb_distance(unsigned a,unsigned b)
{
    int r=(int)(a&31)-(int)(b&31), g=(int)((a>>5)&31)-(int)((b>>5)&31);
    int bl=(int)((a>>10)&31)-(int)((b>>10)&31);
    return (unsigned)(r*r+g*g+bl*bl);
}

static unsigned hud_overlap(unsigned a,unsigned b)
{
    /* Cell [a,a+8) against icon [b,b+26). */
    unsigned lo=a>b ? a : b, hi=a+8<b+26 ? a+8 : b+26;
    return hi>lo ? hi-lo : 0;
}

/* Compose both Navi phases off-screen, then publish their bank on success.
 * The key includes actual ItemIds: an upgraded ocarina or filled bottle can
 * change its picture without changing the assigned inventory slot.
 * Each icon gets its own NBG2 palette (5..10: bank*3+slot), built from the
 * colours of the cells it covers, so it keeps the menu icon's colours
 * instead of snapping to the shared button palette. */
static void hud_items_compose(uint32_t items)
{
    volatile unsigned short *cram=(volatile unsigned short *)JO_VDP2_CRAM;
    unsigned back=hud_item_front^1u, cell, slot, i, j, x, y, phase;
    volatile unsigned short *dst=HUD_ITEM_CELLS+back*2u*HUD_ITEM_BANK_WORDS;
    unsigned char owner[HUD_ITEM_COUNT];
    hud_item_art_t art;
    for (slot=0; slot<3; ++slot) {
        unsigned item=(items>>(slot*8))&255;
        art.record[slot]=item<PAUSE_ICON_COUNT ? (const volatile unsigned char *)HUD_ICON_ATLAS+
            PAUSE_ICON_META+item*PAUSE_ICON_RECORD+32 : 0;
        for (i=0; art.record[slot] && i<16; ++i)
            art.rgb[slot][i]=(((unsigned)art.record[slot][i*2]<<8)|art.record[slot][i*2+1])&0x7FFFu;
    }
    /* A cell takes the palette of the icon covering most of it; 3 = none. */
    for (cell=0; cell<HUD_ITEM_COUNT; ++cell) {
        unsigned best=0;
        owner[cell]=3;
        for (slot=0; slot<3; ++slot) {
            unsigned area=hud_overlap((cell%HUD_ITEM_W)*8,hud_item_at[slot][0])*
                          hud_overlap((cell/HUD_ITEM_W)*8,hud_item_at[slot][1]);
            if (art.record[slot] && area>best) { best=area; owner[cell]=(unsigned char)slot; }
        }
        hud_item_palette[back][cell]=owner[cell]<3 ? (unsigned char)(5u+back*3u+owner[cell]) : 2u;
    }
    for (slot=0; slot<4; ++slot) {
        unsigned short colour[64], count[64];
        unsigned n=0;
        if (slot<3) {
            /* Distinct colours of both phases: <= 3 icons x 15 + 15 HUD. */
            for (cell=0; cell<HUD_ITEM_COUNT; ++cell) if (owner[cell]==slot)
                for (y=0; y<8; ++y) for (x=0; x<8; ++x) for (phase=0; phase<2; ++phase) {
                    unsigned c=hud_item_rgb(&art,(cell%HUD_ITEM_W)*8+x,(cell/HUD_ITEM_W)*8+y,phase);
                    if (!c) continue;
                    c&=0x7FFFu;
                    for (i=0; i<n && colour[i]!=c; ++i) {}
                    if (i==n) { if (n==64) continue; colour[n]=(unsigned short)c; count[n++]=0; }
                    if (count[i]<0xFFFFu) ++count[i];
                }
            /* Merge the closest pair into its more common colour until 15. */
            while (n>15) {
                unsigned a=0, b=1, best=~0u;
                for (i=0; i<n; ++i) for (j=i+1; j<n; ++j) {
                    unsigned d=hud_rgb_distance(colour[i],colour[j]);
                    if (d<best) { best=d; a=i; b=j; }
                }
                if (count[b]>count[a]) colour[a]=colour[b];
                count[a]=(unsigned short)(count[a]+count[b]>0xFFFFu ? 0xFFFFu : count[a]+count[b]);
                colour[b]=colour[--n]; count[b]=count[n];
            }
            cram[768u+(5u+back*3u+slot)*16u]=0;
            for (i=0; i<15; ++i) cram[768u+(5u+back*3u+slot)*16u+1u+i]=i<n ? colour[i] : 0;
        }
        for (cell=0; cell<HUD_ITEM_COUNT; ++cell) if (owner[cell]==slot)
            for (phase=0; phase<2; ++phase) for (y=0; y<8; ++y) for (x=0; x<8; ++x) {
                unsigned px=(cell%HUD_ITEM_W)*8+x, py=(cell/HUD_ITEM_W)*8+y;
                unsigned c=hud_item_rgb(&art,px,py,phase), index=0;
                if (c && slot==3) index=hud_icon_colour(c&0x7FFFu);
                else if (c) {
                    unsigned best=~0u;
                    for (i=0; i<n; ++i) {
                        unsigned d=hud_rgb_distance(c,colour[i]);
                        if (d<best) { best=d; index=i+1; }
                    }
                }
                hud_item_pixel(dst+phase*HUD_ITEM_BANK_WORDS,px,py,index);
            }
    }
    hud_item_front=back;
}

static void map_visibility(bool visible)
{
    unsigned int x, y;
    volatile uint16_t *map = (volatile uint16_t *)MINIMAP_VRAM_MAP;
    unsigned int base = (MINIMAP_VRAM_CELLS - MINIMAP_VRAM_MAP) / 32u;
    if (visible == map_visible) return;
    if (row) {
        for (y = 0; y < row->cells_h; ++y)
            for (x = 0; x < row->cells_w; ++x)
                map[(row->y / 8 + y) * 64u + row->x / 8 + x] =
                    (uint16_t)(visible ? base + 1u + y * row->cells_w + x : base);
    }
    map_visible = visible;
}

static void hud_visibility(int variant)
{
    unsigned int x, y;
    bool analog = jo_is_pad1_available() && jo_is_input_analog(0);
    unsigned preset = ui_labels() * 2 + analog;
    unsigned weapon = variant >= 0 && (variant & 16) && save_state.equip_sword <= 3u
        ? save_state.equip_sword : 0u;
    uint32_t actions=0, items=0;
    int key = variant < 0 ? -1 : variant + preset * 32 + weapon * 320;
    volatile uint16_t *map = (volatile uint16_t *)MINIMAP_VRAM_MAP;
    unsigned int base = (HUD_VRAM_CELLS - MINIMAP_VRAM_MAP) / 32u;
    for (x=0; x<3; ++x) {
        unsigned action=save_state.c_items[x];
        actions|=(action&63u)<<(x*6);
        items|=save_inventory_item(save_c_item_inventory_slot(action))<<(x*8);
    }
    if (key == hud_variant && actions == hud_actions_key && items == hud_items_key) return;
    if (variant>=0 && (actions!=hud_actions_key || items!=hud_items_key)) {
        hud_items_compose(items);
        hud_actions_key=actions; hud_items_key=items;
    }
    for (y = 0; y < HUD_MAP_H; ++y)
        for (x = 0; x < HUD_MAP_W; ++x)
            /* CN_12BIT: high nibble is the palette within CRAM offset 3. */
            map[(HUD_MAP_Y + y) * 64u + HUD_MAP_X + x] = (uint16_t)
                (variant < 0 ? (MINIMAP_VRAM_CELLS - MINIMAP_VRAM_MAP) / 32u :
                 0x2000u | (base + HUD_NAMES[variant * HUD_MAP_W * HUD_MAP_H + y * HUD_MAP_W + x]));
    if (variant >= 0) {
        unsigned patch = HUD_PATCH_OFFSET + (preset * 2 + !!(variant & 16)) * HUD_PATCH_COUNT;
        for (x=0; x<HUD_PATCH_COUNT; ++x)
            map[hud_patch_positions[x]] = 0x2000u | (base + HUD_NAMES[patch+x]);
        unsigned label = preset >= 8u ? 2u : preset >= 4u ? 1u : 0u;
        patch = HUD_WEAPON_OFFSET + ((label * 4 + weapon) * 8 + ((variant >> 1) & 7)) * HUD_WEAPON_COUNT;
        for (x=0; x<HUD_WEAPON_COUNT; ++x)
            map[hud_weapon_positions[x]] = 0x2000u | (base + HUD_NAMES[patch+x]);
    }
    if (variant >= 0) {
        unsigned patch=((uintptr_t)HUD_ITEM_CELLS-MINIMAP_VRAM_MAP)/32u+
            (hud_item_front*2u+(variant&1))*HUD_ITEM_BANK_WORDS/16u;
        for (x=0; x<HUD_ITEM_COUNT; ++x)
            map[hud_item_positions[x]] = (uint16_t)((hud_item_palette[hud_item_front][x]<<12) | (patch+x));
    }
    hud_variant = key;
}

static unsigned int     be16(const uint8_t *p) { return ((unsigned int)p[0] << 8) | p[1]; }
static uint32_t         be32(const uint8_t *p) { return ((uint32_t)be16(p) << 16) | be16(p + 2); }

bool    minimap_bind(const uint8_t *blob, uint32_t bytes)
{
    unsigned int i;
    file = 0;
    if (!blob || bytes != MINIMAP_FILE_BYTES || blob[0] != 'K' || blob[1] != 'M' ||
        blob[2] != 'A' || blob[3] != 'P' || be16(blob + 4) != MINIMAP_ROW_COUNT)
        return false;
    for (i = 0; i < MINIMAP_ROW_COUNT; ++i)
        if (be32(blob + 6 + 6 * i) != minimap_rows[i].offset ||
            be16(blob + 10 + 6 * i) != minimap_rows[i].bytes ||
            minimap_rows[i].bytes > MINIMAP_VRAM_CELL_BYTES)
            return false;
    file = blob;
    return true;
}

bool    minimap_init(void)
{
    volatile uint16_t *cram = (volatile uint16_t *)JO_VDP2_CRAM;
    unsigned int i;
    if (!file)
        return false;
    /* Nine consecutive 8x8 resident textures, straight from the cart copy. */
    for (i = 0; i < MINIMAP_MARKER_FRAMES; ++i) {
        unsigned int slot;
        if (!kokiri_resident_sprite_8bit(file + MINIMAP_MARKER_OFFSET + i * 64u, 8, 8, &slot))
            return false;
        if (i == 0) marker_sprite = (int)slot;
        else if ((int)slot != marker_sprite + (int)i) return false;
    }
    for (i = 0; i < 8; ++i)
        cram[MINIMAP_CRAM_MAP + i] = minimap_palette[i];
    /* Marker pixels 16/17 in colour bank 0x300: CRAM 784/785. */
    cram[MINIMAP_CRAM_MARKER] = minimap_marker_palette[0];
    cram[MINIMAP_CRAM_MARKER + 1] = minimap_marker_palette[1];
    hud_ready = hud_load();
    if (!health_hud_init()) return false;
    if (!hud_ready) return false;
    minimap_scene(~0u);
    return marker_sprite >= 0;
}

void    minimap_scene(unsigned int save_scene)
{
    volatile uint16_t *map = (volatile uint16_t *)MINIMAP_VRAM_MAP;
    volatile uint16_t *cells = (volatile uint16_t *)MINIMAP_VRAM_CELLS;
    /* One-word names count 32-byte cells from the bank start; SGL's
    ** slPageNbg2 supplies the bank bits from the cell address. */
    const unsigned int base = (MINIMAP_VRAM_CELLS - MINIMAP_VRAM_MAP) / 32u;
    unsigned int i;
    row = 0;
    if (!file)
        return;
#ifdef DOSEI_HIRES
    /* NBG2 cannot zoom; the 2x-tall hi-res copy is not built yet. */
    return;
#endif
    for (i = 0; i < MINIMAP_ROW_COUNT; ++i)
        if (minimap_rows[i].save_scene == save_scene)
            row = &minimap_rows[i];
    /* Cell zero is blank even in scenes with no minimap. */
    for (i = 0; i < 16; ++i) cells[i] = 0;
    if (row)
        for (i = 0; i < row->bytes / 2u; ++i)
            cells[i] = (uint16_t)be16(file + row->offset + i * 2u);
    for (i = 0; i < 64u * 64u; ++i)
        map[i] = (uint16_t)base;                         /* cell 0: blank */
    map_visible = false;
    hud_variant = -1;
    health_hud_reset();
    slCharNbg2(COL_TYPE_16, CHAR_SIZE_1x1);
    slPageNbg2((void *)MINIMAP_VRAM_CELLS, (void *)(JO_VDP2_CRAM + MINIMAP_CRAM_MAP * 2u),
               PNB_1WORD | CN_12BIT);
    slPlaneNbg2(PL_SIZE_1x1);
    slMapNbg2((void *)MINIMAP_VRAM_MAP, (void *)MINIMAP_VRAM_MAP,
              (void *)MINIMAP_VRAM_MAP, (void *)MINIMAP_VRAM_MAP);
    /* Both HUD and map use absolute screen coordinates, with offline padding. */
    slScrPosNbg2(0, 0);
}

void    minimap_set_hidden(bool h) { hidden = h; }
void minimap_toggle(void) { hidden = !hidden; }

bool    minimap_cheat_sample(uint16_t held)
{
    if (cheat_refill_sample(&refill_cheat, held)) {
        refill_pending = true;
        return true;        /* the final Start must not also pause */
    }
    if (cheat_code_sample(&cheat, held)) {
        enemy_dots = !enemy_dots;
        chime = true;
        return true;
    }
    return false;
}

bool    minimap_cheat_refill_take(void)
{
    bool pending = refill_pending;
    refill_pending = false;
    return pending;
}

void    minimap_cheat_refill_reset(void)
{
    refill_pending = false;
    refill_cheat = (cheat_code_t){0};
}

bool    minimap_cheat_chime(void)
{
    if (!chime)
        return false;
    chime = false;
    return true;
}

bool    minimap_enemy_dots(void) { return enemy_dots; }

/* Session-only cheat. Scene/room changes deliberately never call this. */
void    minimap_session_reset(void)
{
    enemy_dots = chime = false;
    cheat = (cheat_code_t){0};
    minimap_cheat_refill_reset();
}

/* Minimap_Draw runs in play only; the text box and pause dim it away
** (z_parameter.c minimapAlpha), the title and cutscenes never show it. */
static bool shown(void)
{
    return row && !hidden && recomp_link_active && !recomp_title_is_visible() &&
           !recomp_file_select_is_visible() && !cutscene_is_playing() &&
           !gameplay_is_talking() && !gameplay_is_paused();
}

uint32_t minimap_layer_flags(void)
{
    static bool pause_visible;
    if (gameplay_is_paused() && recomp_link_active) {
        pause_visible = true;
        return pause_windows_update() ? NBG0ON : 0;
    }
    if (pause_visible) {
        pause_windows_reset();
        minimap_scene(row ? row->save_scene : ~0u);
        pause_visible = false;
    }
    bool visible = hud_ready && recomp_link_active && !recomp_title_is_visible() &&
        !recomp_file_select_is_visible() && !cutscene_is_playing() &&
        !gameplay_is_talking() && !gameplay_is_paused();
    bool navi = gameplay_hud_blink(&hud_blink, recomp_clock(), gameplay.navi_calling, visible);
    bool carrying = world_props_carrying();
    unsigned int action = gameplay_hud_action(
        recomp_enter_prompt(),
        !carrying && (gameplay.chest_prompt >= 0 || dungeon_doors_prompt()),
        gameplay.shop_prompt || gameplay.prompt >= 0,
        world_signs_near(),
        !carrying && (world_props_near_liftable() || recomp_push_prompt()),
        recomp_lift_hold_actionable(),
        recomp_lift_throw_ready());
#ifdef DOSEI_HIRES
    /* Existing NBG2 HUD remains standard-only until doubled cells are baked. */
    return 0;
#endif
    if (!hud_ready) return 0;
    if (ui_jump_key() == UI_KEY_A) action = 0;
    health_hud_draw(visible);
    map_visibility(shown());
    hud_visibility(visible ? (int)(((gameplay.equipped & GP_SWORD) && ui_jump_key() != UI_KEY_X ? 16u : 0u) + action * 2u + navi) : -1);
    return (shown() || visible) ? NBG2ON : 0;
}

void    minimap_priorities(void)
{
    /* jo_core_set_screens_order puts NBG2 at 6; a sprite wins a tie. */
    slPrioritySpr1(6);
}

static void marker(unsigned int frame, int px, int py)
{
    FIXED pos[5];
    SPR_ATTR attr = SPR_ATTRIBUTE(0, MINIMAP_SPRITE_PRIORITY_BIT | (MINIMAP_CRAM_MAP & 0x700u),
                                  No_Gouraud, CL256Bnk | ECdis, sprNoflip | FUNC_Sprite);
    attr.texno = (Uint16)(marker_sprite + (int)frame);
    pos[0] = (px - JO_TV_WIDTH_2) * 65536;
    pos[1] = (py - JO_TV_HEIGHT_2) * 65536;
    pos[2] = kokiri_hud_depth(1) * 65536;   /* just past the near rejection */
    pos[3] = pos[4] = 65536;
    slDispSprite(pos, &attr, 0);
}

/* Minimap_DrawCompassIcons: tempX = x / R_COMPASS_SCALE_X (s16 division),
** screen = 160 + (R_COMPASS_OFFSET_X + tempX) / 10, 120 - (OFFSET_Y - tempZ) / 10. */
static void world_to_map(int32_t x, int32_t z, int *px, int *py)
{
    int32_t tx = (int16_t)x / row->scale_x, tz = (int16_t)z / row->scale_y;
    *px = 160 + (row->off_x + tx) / 10;
    *py = 120 - (row->off_y - tz) / 10;
}

void    minimap_draw(int32_t x, int32_t z, uint16_t yaw)
{
    int px, py;
    if (!shown() || marker_sprite < 0)
        return;
    world_to_map(x, z, &px, &py);
    marker(((unsigned int)(uint16_t)(yaw + 0x1000u) >> 13) & 7u, px, py);
    /* Cheat only: live forest enemies and the legacy test projectile. */
    if (enemy_dots) {
        int32_t nx, ny, nz;
        unsigned i;
        for (i = 0; i < ACTOR_POOL_MAX; ++i) {
            const actor_t *a = actor_sys_slot(i);
            if (!a || a->kill || !(a->flags & ACTOR_FLAG_HOSTILE) ||
                (a->profile->category != ACTORCAT_ENEMY && a->profile->category != ACTORCAT_BOSS)) continue;
            world_to_map(a->x, a->z, &px, &py);
            marker(MINIMAP_DOT_FRAME, px, py);
        }
#ifndef DOSEI_CLEAN_TEST
        /* The M2c nutsball launcher (recomp.c nut_test_emitter), a stand-in
        ** Deku Scrub at the first Kokiri grass tuft: always marked. */
        if (row->save_scene == SAVE_SCENE_KOKIRI_FOREST) {
            world_to_map(kokiri_grass[0].x, kokiri_grass[0].z, &px, &py);
            marker(MINIMAP_DOT_FRAME, px, py);
        }
#endif
        if (gameplay_nut_body(&nx, &ny, &nz)) {
            world_to_map(nx, nz, &px, &py);
            marker(MINIMAP_DOT_FRAME, px, py);
        }
    }
}
