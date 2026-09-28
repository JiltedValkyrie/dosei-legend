/* Interior occlusion masks. Contract and source basis in interior_mask.h
 * and tools/build_interior_masks.py. Data lives in the jo_malloc heap (the
 * cart zone: one room's tiles exceed the work-RAM arena); VRAM tiles go into
 * the actor bank npc_draw rebuilds, so they are re-uploaded with it. */
#include <jo/jo.h>
#include "interior_mask.h"
#include "kokiri_sgl.h"
#include "asset_names.h"
#include "scene_table.h"

#define MASK_HEADER 8
#define MASK_RECORD 12
#define MASK_TILES_MAX 256

static unsigned char *mask_data;
static unsigned int   mask_count, mask_tile;
static uint16_t       mask_slot[MASK_TILES_MAX];
static bool           mask_ready;

static unsigned int be16(const unsigned char *p) { return (unsigned)p[0] << 8 | p[1]; }

void interior_mask_free(void)
{
    if (mask_data) jo_free(mask_data);
    mask_data = 0;
    mask_count = 0;
    mask_ready = false;
}

bool interior_mask_load(unsigned int scene_index)
{
    char name[] = "S0R0.MSK";
    int bytes = 0;
    unsigned int need;
    interior_mask_free();
    name[1] = asset_name_digit(scene_index);
    /* Shop only until its crossings are proven (Astra 2026-09-28). */
    if (scene_index != SCENE_KOKIRI_SHOP) return true;
    mask_data = (unsigned char *)jo_fs_read_file(name, &bytes);
    if (!mask_data || bytes < MASK_HEADER ||
        mask_data[0] != 'K' || mask_data[1] != 'M' || mask_data[2] != 'S' ||
        mask_data[3] != 'K') { interior_mask_free(); return false; }
    mask_count = be16(mask_data + 4);
    mask_tile = be16(mask_data + 6);
    need = MASK_HEADER + mask_count * (MASK_RECORD + mask_tile * mask_tile * 2);
    if (mask_count > MASK_TILES_MAX || mask_tile != 16 || (unsigned)bytes != need) {
        interior_mask_free();
        return false;
    }
    return true;
}

bool interior_mask_upload(void)
{
    unsigned int i;
    const unsigned char *p = mask_data + MASK_HEADER;
    mask_ready = false;
    if (!mask_data) return true;
    for (i = 0; i < mask_count; ++i, p += MASK_RECORD + mask_tile * mask_tile * 2) {
        unsigned int slot = kokiri_bank_rgb_upload(p + MASK_RECORD, mask_tile, mask_tile);
        if (slot == KOKIRI_TILE_NONE) return false;
        mask_slot[i] = (uint16_t)slot;
    }
    mask_ready = true;
    return true;
}

/* Screen-space sprites at the tile's view depth: SGL's Z sort puts an
 * actor polygon farther than the surface under the mask, a nearer one over. */
void interior_mask_draw(void)
{
    unsigned int i;
    const unsigned char *p = mask_data + MASK_HEADER;
    if (!mask_ready || !kokiri_scene_backdrop_active()) return;
    for (i = 0; i < mask_count; ++i, p += MASK_RECORD + mask_tile * mask_tile * 2) {
        FIXED pos[5];
        SPR_ATTR attr = SPR_ATTRIBUTE(0, No_Palet, No_Gouraud, ECdis,
                                      sprNoflip | FUNC_Sprite);
        int x = (int16_t)be16(p), y = (int16_t)be16(p + 2);
        int z = (int16_t)be16(p + 8);
        attr.texno = mask_slot[i];
        attr.atrb |= CL32KRGB;
        pos[0] = (x + (int)mask_tile / 2 - JO_TV_WIDTH_2) * 65536;
        pos[2] = z * 65536;
        pos[3] = pos[4] = 65536;
#ifdef DOSEI_HIRES
        pos[1] = ((y + (int)mask_tile / 2) * 2 - JO_TV_HEIGHT_2) * 65536;
        pos[4] = 2 * 65536;
        slDispSpriteHV(pos, &attr, 0);
#else
        pos[1] = (y + (int)mask_tile / 2 - JO_TV_HEIGHT_2) * 65536;
        slDispSprite(pos, &attr, 0);
#endif
    }
}
