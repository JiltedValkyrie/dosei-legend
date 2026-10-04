/* Baked NPC sprite impostors (tools/build_npc_sprites.py, SPR1 files).
** The sheet stays in the cart; each drawn instance owns one VDP1 cel slot
** that is rewritten only when its pose or view direction changes. */
#ifndef DOSEI_NPC_SPRITE_H
#define DOSEI_NPC_SPRITE_H

#include <stdint.h>
#define NPC_SPRITE_SLOT_NONE UINT16_MAX

typedef struct npc_sprite_inst {
    const unsigned char *sheet;     /* sheet the slot's size/CLUT are set for */
    uint16_t slot, colno, shown;
} npc_sprite_inst_t;

/* Claim the instance's cel slot in the actor texture bank. False = full.
** A slot can later draw any sheet whose cel is not bigger than this one's:
** draw rebinds size and CLUT when the sheet changes. */
int  npc_sprite_upload(const unsigned char *spr, npc_sprite_inst_t *inst);
/* frame: source animation frame (ticks table index, wraps). */
void npc_sprite_draw(const unsigned char *spr, npc_sprite_inst_t *inst, unsigned int frame,
                     int x, int y, int z, uint16_t yaw);
/* Target/talk focus height above the actor origin, world units. */
int  npc_sprite_focus_y(const unsigned char *spr);
/* Conservative sphere/frustum rejection before cel uploads or facing math. */
int npc_sprite_in_view(int x, int y, int z, unsigned int radius);
unsigned char *npc_sprite_load(const char *name);

#endif
