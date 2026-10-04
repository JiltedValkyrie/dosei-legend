#include <jo/jo.h>
#include "../../shared/lib/camera/kokiri_camera.c"
#include "demo.h"
#include "collide.h"
#include "kokiri_collision.h"

void kokiri_camera_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    *sine = slSin((ANGLE)yaw);
    *cosine = slCos((ANGLE)yaw);
}

/* Heading of a movement delta, in the same basis kokiri_camera_update uses:
 * forward is (sin,cos), so the heading is atan2(dx, dz). */
uint16_t kokiri_camera_facing(int32_t dx, int32_t dz)
{
    /* toFIXED(variable) uses software double on SH-2. Scale large deltas
     * together before the integer Q16 conversion so neither component wraps
     * or changes quadrant. Keep the original conversion exact in its range. */
    while (dx < -32768 || dx > 32767 || dz < -32768 || dz > 32767) {
        dx /= 2;
        dz /= 2;
    }
    return (uint16_t)slAtan(dz * 65536, dx * 65536);
}

/* gameplay.c is platform free, so the Saturn build supplies its heading helper
** here. The host tests bind the same name to libm. */
uint16_t gameplay_facing(int32_t dx, int32_t dz)
{
    return kokiri_camera_facing(dx, dz);
}

/* Q16 sine/cosine for gameplay.c (chest frame, Mido's block offset). */
void gameplay_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine)
{
    kokiri_camera_sincos(yaw, sine, cosine);
}

/* collide.c's OC push for pool actors: the same wall/floor checks Link
** uses, so a push stops at scenery (actor y is feet). */
void collide_world_push(actor_t *a, int32_t dx, int32_t dz)
{
    camera_position_t p;
    p.x = a->x;
    p.y = a->y + DEMO_LINK_EYE_HEIGHT;
    p.z = a->z;
    kokiri_collision_move_actor(&p, dx, 0, dz);
    a->x = p.x;
    a->y = p.y - DEMO_LINK_EYE_HEIGHT;
    a->z = p.z;
}

/* collide.c's sector heading: same basis as gameplay_facing. */
uint16_t collide_heading(int32_t dx, int32_t dz)
{
    return kokiri_camera_facing(dx, dz);
}
