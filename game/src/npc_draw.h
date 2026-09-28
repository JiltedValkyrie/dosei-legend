#ifndef DOSEI_NPC_DRAW_H
#define DOSEI_NPC_DRAW_H
#include <stdbool.h>
bool npc_draw_load(unsigned int save_scene);
void npc_draw_free(void);
void npc_draw(unsigned int tick);
bool npc_draw_load_navi(void);
void npc_draw_navi(unsigned int frame);
#endif
