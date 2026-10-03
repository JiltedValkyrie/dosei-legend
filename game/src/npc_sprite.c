/* Baked NPC sprite impostors. Format: tools/build_npc_sprites.py docstring. */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "npc_sprite.h"
#include "kokiri_sgl.h"
#include "gameplay.h"
#include "demo.h"

#define U16(s, o) ((unsigned int)((s)[o] << 8 | (s)[(o) + 1]))
#define CELS(s) (0x34u + ((U16(s, 0x0C) * 2u + 3u) & ~3u))

int npc_sprite_upload(const unsigned char *spr, npc_sprite_inst_t *inst)
{
    unsigned int colno = 0;
    inst->slot = (uint16_t)kokiri_bank_tile_upload(spr + CELS(spr), spr + 0x14,
                                                   U16(spr, 4), U16(spr, 6), &colno);
    inst->colno = (uint16_t)colno;
    inst->shown = 0;
    inst->sheet = spr;
    return inst->slot != KOKIRI_TILE_NONE;
}

int npc_sprite_focus_y(const unsigned char *spr) { return (int16_t)U16(spr, 0x12); }

void npc_sprite_draw(const unsigned char *spr, npc_sprite_inst_t *inst, unsigned int frame,
                     int x, int y, int z, uint16_t yaw)
{
    unsigned int bytes = U16(spr, 4) * U16(spr, 6) / 2;
    /* phi: camera seen from the actor's frame, 0 = in front (bake view()).
    ** Sign confirmed in Kronos 2026-10-03. */
    uint16_t phi = (uint16_t)(yaw - gameplay_facing(demo_camera.x - x, demo_camera.z - z));
    unsigned int d8 = ((phi + 0x1000u) >> 13) & 7, dir = d8 <= 4 ? d8 : 8 - d8;
    unsigned int pose = U16(spr, 0x34 + (frame % U16(spr, 0x0C)) * 2);
    unsigned int cel = pose * U16(spr, 8) + dir;
    FIXED pos[5];
    /* SGL sprHflip is broken (PDATA16 typo): bit 4 is the H flip. */
    SPR_ATTR attr = SPR_ATTRIBUTE(0, 0, No_Gouraud, CL16Look | ECdis,
                                  (d8 > 4 ? (1 << 4) : 0) | sprNoflip | FUNC_Sprite);
    if (inst->slot == KOKIRI_TILE_NONE) return;
    if (inst->sheet != spr) {
        jo_texture_definition *t = &__jo_sprite_def[inst->slot];
        uint16_t *clut = (uint16_t *)(JO_VDP1_VRAM + inst->colno * 8u);
        unsigned int k;
        t->width = (unsigned short)U16(spr, 4);
        t->height = (unsigned short)U16(spr, 6);
        t->size = JO_MULT_BY_32(t->width & 0x1f8) | t->height;
        for (k = 0; k < 16; ++k) clut[k] = (uint16_t)U16(spr, 0x14 + k * 2);
        inst->sheet = spr;
        inst->shown = 0xFFFF;
    }
    if (cel != inst->shown) {
        const uint32_t *from = (const uint32_t *)(spr + CELS(spr) + cel * bytes);
        uint32_t *to = (uint32_t *)__jo_sprite_pic[inst->slot].data;
        unsigned int k;
        for (k = 0; k < bytes / 4; ++k) to[k] = from[k];
        inst->shown = (uint16_t)cel;
    }
    pos[0] = x * 65536;
    pos[1] = -(y * 65536 + (int16_t)U16(spr, 0x0E) * 4096);
    pos[2] = z * 65536;
    pos[3] = pos[4] = (FIXED)U16(spr, 0x10) * 256;
    attr.texno = inst->slot;
    attr.colno = inst->colno;
    slPutSprite(pos, &attr, 0);
}
