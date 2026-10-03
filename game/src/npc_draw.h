#ifndef DOSEI_NPC_DRAW_H
#define DOSEI_NPC_DRAW_H
#include <stdbool.h>
bool npc_draw_load(unsigned int save_scene);
void npc_draw_free(void);
/* Force the next draw to re-upload the actor texture bank. */
void npc_draw_reupload(void);
void npc_draw(unsigned int tick);
bool npc_draw_load_navi(void);
/* Saria's greeting-cutscene clips: loaded with the greeting, freed with it. */
bool npc_draw_load_saria_cutscene(void);
void npc_draw_free_saria_cutscene(void);
void npc_draw_navi(unsigned int frame);
#endif
