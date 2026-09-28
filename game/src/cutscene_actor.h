#ifndef DOSEI_CUTSCENE_ACTOR_H
#define DOSEI_CUTSCENE_ACTOR_H
#include <stdbool.h>
#include <stdint.h>

/*
** The dream's riders: Ganondorf, Zelda and Impa.
**
** These are not gameplay actors and deliberately share nothing with the actor
** pool the progression plan describes. They exist for one shot, they are
** placed by that shot's baked cues, and they are gone when it ends.
**
** Where they live matters more than what they are. Each mesh is a KFR1 file
** on the disc -- the same container FOREST.BIN and LINK.BIN use -- and its
** geometry and vertex animation tracks are read into the 4 MB cart. Textures
** occupy the VDP1 bank above the nightmare's larger command reservation.
** Every actor is released on the next scene. SGL allows 3,750 polygons;
** the complete dream bank, Link, field and rain require 3,710.
*/

typedef enum
{
    CUTSCENE_ACTOR_GANON = 0,
    CUTSCENE_ACTOR_ZELDA,
    CUTSCENE_ACTOR_IMPA,
    CUTSCENE_ACTOR_HORSE_ZELDA,
    CUTSCENE_ACTOR_HORSE_GANON,
    CUTSCENE_ACTOR_BRIDGE,
    CUTSCENE_ACTOR_CHAINS,
    CUTSCENE_ACTOR_GATE_FIRE,
    CUTSCENE_ACTOR_COUNT
}               cutscene_actor_id;

/* Load every rider. False if any mesh could not be read or would not fit, in
** which case nothing is left half-loaded and none of them draw. */
bool            cutscene_actors_load(void);

/* Release the meshes and the VDP1 space. Safe to call when none are loaded. */
void            cutscene_actors_free(void);

/* True once the riders are resident. */
bool            cutscene_actors_ready(void);
/* Prepare poses and cart-to-VRAM residency before drawing any actor. */
void            cutscene_actors_prepare(void);
void            cutscene_gate_fire_draw(void);

/* Draw one rider at a world position and facing. Does nothing if it is not
** loaded, so a shot that names an actor we failed to read simply lacks it
** rather than dropping the whole cutscene. */
void            cutscene_actor_draw(cutscene_actor_id id,
                                    int32_t x, int32_t y, int32_t z,
                                    uint16_t yaw);

#endif
