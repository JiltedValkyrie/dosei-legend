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
** geometry is read into the 4 MB cart, not into work RAM. Together the three
** are about 63 KB of POINT/POLYGON/ATTR, which would not fit below the SGL
** work area but is nothing beside the cart. Their textures go into the VDP1
** bank space the flat Hyrule Field leaves empty, and both are released when
** the cutscene loads another scene.
**
** Polygons per frame are the real ceiling, not storage: the field and three
** riders come to 2,687, which is why the SGL work area is built for 2,900.
*/

typedef enum
{
    CUTSCENE_ACTOR_GANON = 0,
    CUTSCENE_ACTOR_ZELDA,
    CUTSCENE_ACTOR_IMPA,
    CUTSCENE_ACTOR_COUNT
}               cutscene_actor_id;

/* Load every rider. False if any mesh could not be read or would not fit, in
** which case nothing is left half-loaded and none of them draw. */
bool            cutscene_actors_load(void);

/* Release the meshes and the VDP1 space. Safe to call when none are loaded. */
void            cutscene_actors_free(void);

/* True once the riders are resident. */
bool            cutscene_actors_ready(void);

/* Draw one rider at a world position and facing. Does nothing if it is not
** loaded, so a shot that names an actor we failed to read simply lacks it
** rather than dropping the whole cutscene. */
void            cutscene_actor_draw(cutscene_actor_id id,
                                    int32_t x, int32_t y, int32_t z,
                                    uint16_t yaw);

#endif
