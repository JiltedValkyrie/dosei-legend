#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
/* EnKanban: authored text, source attack-to-piece masks, no item drops.
 * Signs stay outside the actor pool; detached pieces use temporary slots.
 * Fragment motion is a reduced ballistic path; water/ocarina repair are M4/M7. */
#include "world_signs.h"
#include "actor_sys.h"
#include "kokiri_actors.h"
#include "save_state.h"
#include "player_attack.h"
#include "oot_core_host.h"
#define OOT_ACTOR_EN_KANBAN 0x0141
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
static uint16_t parts[KOKIRI_SIGN_COUNT];
static uint8_t cooldown[KOKIRI_SIGN_COUNT];
static const actor_profile_t piece_profile={SIGN_PIECE_ID,ACTORCAT_PROP,0,0,0,0,0};
static int32_t player_x,player_z;
static gameplay_input_t last_sign_in;
void world_signs_reset(void)
{
    unsigned int i;actor_t *a=0;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) { parts[i]=0x7FF;cooldown[i]=0; }
    while((a=actor_sys_find(SIGN_PIECE_ID,a))) actor_kill(a);
}
/* While the decomp plays, En_Kanban owns reading and cutting; the sign keeps
** its C mesh, drawn with the decomp actor's partFlags. */
unsigned int world_signs_parts(unsigned int i)
{
    int q;
    if (i>=KOKIRI_SIGN_COUNT) return 0;
    if (!oot_core_owns_kokiri_npcs()) return parts[i];
    q=oot_core_prop(OOT_ACTOR_EN_KANBAN,kokiri_signs[i].x,kokiri_signs[i].z);
    return q<0 ? 0 : (unsigned int)q;
}
void world_signs_step(const gameplay_input_t *in)
{
    unsigned int i;actor_t *a=0;
    /* Cache position every step: the A-handler can return before
     * world_signs_text() runs, which would leave the HUD prompt stale. */
    last_sign_in=*in;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) if(cooldown[i]) --cooldown[i];
    while((a=actor_sys_find(SIGN_PIECE_ID,a))) {
        int32_t pos[3]={a->x,a->y,a->z};
        if(--a->data[0]<=0) { actor_kill(a);continue; }
        if(!a->data[3]) {
            a->data[1]-=137;
            if(gameplay_ball_move(pos,0,a->data[1]/256,0)) a->data[3]=1;
            a->x=pos[0];a->y=pos[1]+(a->data[3]?6:0);a->z=pos[2];
        }
    }
}
unsigned int world_signs_text(const gameplay_input_t *in)
{
    unsigned int i;
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST || oot_core_owns_kokiri_npcs()) return 0;
    for(i=0;i<KOKIRI_SIGN_COUNT;++i) {
        const kokiri_prop_t *p=&kokiri_signs[i];
        int dx=in->x-p->x,dz=in->z-p->z,dy=in->y-p->y;
        int16_t facing=(int16_t)(gameplay_facing(-dx,-dz)-in->yaw);
        int16_t side=(int16_t)(gameplay_facing(dx,dz)-kokiri_sign_yaws[i]);
        if(p->room==in->room && parts[i]==0x7FF && dx>-70 && dx<70 && dz>-70 && dz<70 &&
           dx*dx+dz*dz<4900 && dy>-40 && dy<60 && facing>-0x4000 && facing<0x4000 &&
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
        int16_t facing=(int16_t)(gameplay_facing(-dx,-dz)-in->yaw);
        int16_t side=(int16_t)(gameplay_facing(dx,dz)-kokiri_sign_yaws[i]);
        if(p->room==in->room && parts[i]==0x7FF && dx>-70 && dx<70 && dz>-70 && dz<70 &&
           dx*dx+dz*dz<4900 && dy>-40 && dy<60 && facing>-0x4000 && facing<0x4000 &&
           side>-0x4000 && side<0x4000) return true;
    }
    return false;
}
void world_signs_register(collider_t *storage,unsigned int capacity,const gameplay_input_t *in)
{
    unsigned int i,n=0;
    player_x=in->x;player_z=in->z;
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST || oot_core_owns_kokiri_npcs()) return;
    for(i=0;i<KOKIRI_SIGN_COUNT && n<capacity;++i) {
        const kokiri_prop_t *p=&kokiri_signs[i];collider_t *c;
        int dx=p->x-in->x,dz=p->z-in->z;
        if(p->room!=in->room || cooldown[i] || !(parts[i]&0x3FF) || dx<-120 || dx>120 || dz<-120 || dz>120) continue;
        c=&storage[n++];*c=(collider_t){0};c->shape=COLSHAPE_CYLINDER;
        c->x=p->x;c->y=p->y+5;c->z=p->z;c->radius=20;c->height=50;
        c->ac_type=AC_TYPE_PLAYER;c->ac_bumper=DMG_DEFAULT;c->ac_flags=COL_OUTSIDE_ACTOR;c->tag=(uint16_t)(0x700+i);
        collide_set_ac(c);
    }
}
void world_signs_collect(void)
{
    unsigned int j;
    /* EnKanban sCutTypes (PLAYER_MWA_*), sCutFlags. */
    static const uint8_t cuts[28]={1,1,4,4,2,2,2,2,2,2,2,2,0,0,0,0,1,1,1,1,2,2,0,0,0,0,0,0};
    static const uint16_t masks[6]={0x3FF,0x27,0x14B,0x147,0x153,0xD8};
    for(j=0;j<collide_event_count();++j) {
        const collide_event_t *e=collide_event(j);
        unsigned int i=e->ac_tag-0x700,cut,mask;actor_t *piece;
        int16_t side;
        if(i>=KOKIRI_SIGN_COUNT || cooldown[i]) continue;
        cut=gameplay.attack_id<28 ? cuts[gameplay.attack_id] : 0;
        side=(int16_t)(gameplay_facing(player_x-kokiri_signs[i].x,player_z-kokiri_signs[i].z)-kokiri_sign_yaws[i]);
        if(side>0x4000 || side<-0x4000) { if(cut==1) cut=5;else if(cut==4) cut=3; }
        mask=parts[i]&masks[cut];if(!mask) continue;
        piece=actor_spawn(&piece_profile,save_state.scene_id,kokiri_signs[i].room,
                         kokiri_signs[i].x,kokiri_signs[i].y,kokiri_signs[i].z,kokiri_sign_yaws[i],(uint16_t)mask);
        if(!piece) continue;
        piece->data[0]=300;piece->data[1]=1024;
        parts[i]&=(uint16_t)~mask;cooldown[i]=9;gameplay.events|=GP_EVENT_CUT;
    }
}
