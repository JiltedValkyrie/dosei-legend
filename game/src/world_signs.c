#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
/* Saturn sign fallback: authored text and hit response; a short fade replaces
 * detached pieces. Core-owned signs use the same visual state via snapshots. */
#include "world_signs.h"
#include "kokiri_actors.h"
#include "save_state.h"
#include "oot_core_host.h"
#define OOT_ACTOR_EN_KANBAN 0x0141
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
static uint16_t visual[KOKIRI_SIGN_COUNT];
static gameplay_input_t last_sign_in;
void world_signs_reset(void)
{
    unsigned int i;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) visual[i]=OOT_SIGN_INTACT;
}
/* Core owns talk/hits and the fade timer; no live actor read while slave runs. */
unsigned int world_signs_visual(unsigned int i)
{
    int q;
    if (i>=KOKIRI_SIGN_COUNT) return 0;
    if (!oot_core_owns_kokiri_npcs()) return visual[i];
    q=oot_core_prop(OOT_ACTOR_EN_KANBAN,kokiri_signs[i].x,kokiri_signs[i].z);
    return q<0 ? 0 : (unsigned int)q;
}
void world_signs_step(const gameplay_input_t *in)
{
    unsigned int i;
    /* Cache position every step: the A-handler can return before
     * world_signs_text() runs, which would leave the HUD prompt stale. */
    last_sign_in=*in;
    if(oot_core_owns_kokiri_npcs()) return;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) if(visual[i]!=OOT_SIGN_INTACT) {
        int dx=in->x-kokiri_signs[i].x,dz=in->z-kokiri_signs[i].z;
        /* Original EnKanban restores a sign after leaving its vicinity.
         * Axis reject keeps the squared distance inside signed 32 bits. */
        if(dx < -500 || dx > 500 || dz < -500 || dz > 500 ||
           dx*dx+dz*dz>500*500) visual[i]=OOT_SIGN_INTACT;
        else if(visual[i]) --visual[i];
    }
}
unsigned int world_signs_text(const gameplay_input_t *in)
{
    unsigned int i;
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST || oot_core_owns_kokiri_npcs()) return 0;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) {
        const kokiri_prop_t *p=&kokiri_signs[i];
        int dx=in->x-p->x,dz=in->z-p->z,dy=in->y-p->y;
        /* Angle queries reach SGL's atan; reject distant/other-room signs
         * first. Keep the original open bounds and circular reach. */
        if(p->room!=in->room || visual[i]!=OOT_SIGN_INTACT || dx<=-70 || dx>=70 || dz<=-70 || dz>=70 ||
           dy<=-40 || dy>=60 || dx*dx+dz*dz>=4900) continue;
        int16_t facing=(int16_t)(gameplay_facing(-dx,-dz)-in->yaw);
        int16_t side=(int16_t)(gameplay_facing(dx,dz)-kokiri_sign_yaws[i]);
        if(facing>-0x4000 && facing<0x4000 &&
           side>-0x4000 && side<0x4000) return kokiri_sign_params[i]|0x300;
    }
    return 0;
}
/* Read-only: true when a sign is within reach and in the facing cone.
 * Mirrors world_signs_text() without consuming input. */
bool world_signs_near(void)
{
    unsigned int i;
    const gameplay_input_t *in = &last_sign_in;
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST) return false;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) {
        const kokiri_prop_t *p=&kokiri_signs[i];
        int dx=in->x-p->x,dz=in->z-p->z,dy=in->y-p->y;
        if(p->room!=in->room || dx<=-70 || dx>=70 || dz<=-70 || dz>=70 ||
           dy<=-40 || dy>=60 || dx*dx+dz*dz>=4900) continue;
        int16_t facing=(int16_t)(gameplay_facing(-dx,-dz)-in->yaw);
        int16_t side=(int16_t)(gameplay_facing(dx,dz)-kokiri_sign_yaws[i]);
        if(facing>-0x4000 && facing<0x4000 &&
           side>-0x4000 && side<0x4000 && world_signs_visual(i)==OOT_SIGN_INTACT) return true;
    }
    return false;
}
void world_signs_register(collider_t *storage,unsigned int capacity,const gameplay_input_t *in)
{
    unsigned int i,n=0;
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST || oot_core_owns_kokiri_npcs()) return;
    for(i=0;i<KOKIRI_SIGN_COUNT && n<capacity;++i) {
        const kokiri_prop_t *p=&kokiri_signs[i];collider_t *c;
        int dx=p->x-in->x,dz=p->z-in->z;
        if(p->room!=in->room || visual[i]!=OOT_SIGN_INTACT || dx<-120 || dx>120 || dz<-120 || dz>120) continue;
        c=&storage[n++];*c=(collider_t){0};c->shape=COLSHAPE_CYLINDER;
        c->x=p->x;c->y=p->y+5;c->z=p->z;c->radius=20;c->height=50;
        c->ac_type=AC_TYPE_PLAYER;c->ac_bumper=DMG_DEFAULT;c->ac_flags=COL_OUTSIDE_ACTOR;c->tag=(uint16_t)(0x700+i);
        collide_set_ac(c);
    }
}
void world_signs_collect(void)
{
    unsigned int j;
    if(oot_core_owns_kokiri_npcs()) return;
    for(j=0;j<collide_event_count();++j) {
        const collide_event_t *e=collide_event(j);
        unsigned int i=e->ac_tag-0x700;
        if(i>=KOKIRI_SIGN_COUNT || visual[i]!=OOT_SIGN_INTACT) continue;
        visual[i]=OOT_SIGN_FADE_TICKS;
        gameplay.events|=GP_EVENT_CUT;
    }
}
