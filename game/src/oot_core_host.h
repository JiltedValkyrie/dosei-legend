#ifndef DOSEI_OOT_CORE_HOST_H
#define DOSEI_OOT_CORE_HOST_H
/*
** C side of the oot-core blob (oot-core/include/oot_core_api.h). Boot loads
** OOTCORE.BIN and the scene collision blobs into their cart carves; each
** 30 Hz gameplay step drives the decomp play state at the decomp's 20 Hz.
** Built only with OOT_CORE=1; the calls compile to nothing otherwise.
*/
#include <stdbool.h>

#ifdef DOSEI_OOT_CORE
#include "oot_core_api.h"

/* Boot: load + init the blob and run the gate bench. False if not loaded. */
bool oot_core_boot(void);
#include "gameplay.h"
/* After gameplay_step (fixed 30 Hz). Starts/stops the decomp play state
** with the scene and steps it 2 of every 3 calls. `in` = that step's input. */
void oot_core_frame(const gameplay_input_t *in);
/* Bit 0: a decomp conversation or text box is up (C Link and C A/B
** actions wait). Bit 1: a decomp actor offers talk (A goes to it). */
unsigned int oot_core_talk(void);
/* Decomp NPCs the C npc_draw renderer draws (OotCoreNpcView). */
int oot_core_npcs(const OotCoreNpcView **out);
/* Draw the decomp text box (VDP2 text + VDP1 panel); true while it is up. */
bool oot_core_message_box(void);
/* prop_query: decomp state word of actor `id` near (x, z), -1 if none. */
int oot_core_prop(short id, int x, int z);
const char *oot_core_debug_text(void);
const char *oot_core_debug_text2(void);
/* Phase 2 draw shim meshes: upload after a bank reset, draw the items. */
void oot_core_meshes_upload(void);
void oot_core_meshes_draw(void);

bool oot_core_is_loaded(void);
/* Play state active for the current scene. */
bool oot_core_is_playing(void);
const OotCoreBench *oot_core_bench_result(void);
/* Time of the last decomp update step (Actor_UpdateAll, collision, effects), us. */
unsigned int oot_core_update_us(void);
int oot_core_actors(int category);
/* Live actors of a category, for C drawing (see OotCoreActorView). */
int oot_core_view(int category, OotCoreActorView *out, int max);
/* Kokiri Forest grass (En_Kusa) and floor rupees (En_Item00) belong to the
** decomp while it plays: the C copies stop drawing, cutting and collecting. */
static inline bool oot_core_owns_kokiri_props(void) { return oot_core_is_playing(); }
/* Kokiri children (En_Ko), Mido (En_Md) and the wonder spots (En_Wonder_
** Item/Talk2) belong to the decomp while it plays. Saria stays C (her
** greeting is a C cutscene until z_demo). */
/* 2026-10-03: off. Decomp NPC logic in 64-bit Fx cost 11.5 ms per step;
** C keeps them (fast) until the 32-bit Fx conversion lands. */
static inline bool oot_core_owns_kokiri_npcs(void) { return false; }
#else
#define oot_core_frame(in) ((void)0)
static inline bool oot_core_owns_kokiri_props(void) { return false; }
static inline bool oot_core_owns_kokiri_npcs(void) { return false; }
static inline unsigned int oot_core_talk(void) { return 0; }
static inline unsigned int oot_core_update_us(void) { return 0; }
static inline bool oot_core_message_box(void) { return false; }
static inline int oot_core_prop(short id, int x, int z) { (void)id; (void)x; (void)z; return -1; }
#endif

#endif
