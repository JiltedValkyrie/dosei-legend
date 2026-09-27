#include <jo/jo.h>
#include "minimap.h"
#include "minimap_data.h"
#include "demo.h"
#include "cutscene.h"
#include "gameplay.h"
#include "kokiri_sgl.h"
#include "cheat_code.h"
#include "kokiri_actors.h"

static const uint8_t   *file;
static const minimap_row_t *row;        /* this scene's map, or 0 */
static bool             hidden;
static cheat_code_t     cheat;
static volatile bool    enemy_dots, chime;
static int              marker_sprite = -1;

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
    return marker_sprite >= 0;
}

void    minimap_scene(unsigned int save_scene)
{
    volatile uint16_t *map = (volatile uint16_t *)MINIMAP_VRAM_MAP;
    volatile uint16_t *cells = (volatile uint16_t *)MINIMAP_VRAM_CELLS;
    /* One-word names count 32-byte cells from the bank start; SGL's
    ** slPageNbg2 supplies the bank bits from the cell address. */
    const unsigned int base = (MINIMAP_VRAM_CELLS - MINIMAP_VRAM_MAP) / 32u;
    unsigned int i, x, y;
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
    if (!row)
        return;
    for (i = 0; i < row->bytes / 2u; ++i)
        cells[i] = (uint16_t)be16(file + row->offset + i * 2u);
    for (i = 0; i < 64u * 64u; ++i)
        map[i] = (uint16_t)base;                         /* cell 0: blank */
    for (y = 0; y < row->cells_h; ++y)
        for (x = 0; x < row->cells_w; ++x)
            map[y * 64u + x] = (uint16_t)(base + 1u + y * row->cells_w + x);
    slCharNbg2(COL_TYPE_16, CHAR_SIZE_1x1);
    slPageNbg2((void *)MINIMAP_VRAM_CELLS, (void *)(JO_VDP2_CRAM + MINIMAP_CRAM_MAP * 2u),
               PNB_1WORD | CN_12BIT);
    slPlaneNbg2(PL_SIZE_1x1);
    slMapNbg2((void *)MINIMAP_VRAM_MAP, (void *)MINIMAP_VRAM_MAP,
              (void *)MINIMAP_VRAM_MAP, (void *)MINIMAP_VRAM_MAP);
    /* Scroll so cell (0,0) lands on sOwMinimapPosX/Y. */
    slScrPosNbg2(-(FIXED)row->x * 65536, -(FIXED)row->y * 65536);
}

void    minimap_set_hidden(bool h) { hidden = h; }

void    minimap_cheat_sample(uint16_t held)
{
    if (cheat_code_sample(&cheat, held)) {
        enemy_dots = !enemy_dots;
        chime = true;
    }
}

bool    minimap_cheat_chime(void)
{
    if (!chime)
        return false;
    chime = false;
    return true;
}

bool    minimap_enemy_dots(void) { return enemy_dots; }

/* Minimap_Draw runs in play only; the text box and pause dim it away
** (z_parameter.c minimapAlpha), the title and cutscenes never show it. */
static bool shown(void)
{
    return row && !hidden && demo_link_active && !demo_title_is_visible() &&
           !demo_file_select_is_visible() && !cutscene_is_playing() &&
           !gameplay_is_talking() && !gameplay_is_paused();
}

uint32_t minimap_layer_flags(void)
{
    return shown() ? NBG2ON : 0;
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
    pos[2] = 31 * 65536;
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
    /* Cheat only, not in the original: live enemies (the M2c test nut). */
    if (enemy_dots) {
        int32_t nx, ny, nz;
#ifndef DOSEI_CLEAN_TEST
        /* The M2c nutsball launcher (demo.c nut_test_emitter), a stand-in
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
