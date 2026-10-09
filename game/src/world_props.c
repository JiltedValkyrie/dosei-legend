#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* Source actors: EnIshi, ObjTsubo, EnItem00. Runtime objects live in the
 * existing cart actor pool. Original placements/params come from the ROM. */
#include "world_props.h"
#include "world_signs.h"
#include "kokiri_actors.h"
#include "item_drop.h"
#include "save_state.h"
#include "player_lift.h"
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
static const actor_profile_t prop_profile = {WORLD_PROP_ID, ACTORCAT_PROP, 0, 0,0,0,0};
static const actor_profile_t drop_profile = {DROP_ACTOR_ID, ACTORCAT_ITEMACTION, 0, 0,0,0,0};
static uint32_t removed;
static actor_handle_t carried;
static bool carry_action;
static int current_room;
static uint32_t rng = 0x761234u;
static gameplay_input_t last_in; /* cached each step for query functions */
#if KOKIRI_WORLD_PROP_COUNT > 32
#error Expand world prop removal bitset
#endif
static uint32_t random_next(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
static bool near(const gameplay_input_t *in, const actor_t *a, int radius)
{
    int dx = in->x-a->x, dz = in->z-a->z, dy = in->y-a->y;
    return dx >= -radius && dx <= radius && dz >= -radius && dz <= radius &&
           dx*dx+dz*dz < radius*radius && dy > -40 && dy < 40;
}
static bool spawn_drop(int x, int y, int z, unsigned int item, unsigned int count,
                       unsigned int flag, bool placed)
{
    while (count--) {
        actor_t *a;
        if (item == DROP_NONE) return true;
        if (flag && save_get_collectible(save_state.scene_id, flag)) return true;
        a = actor_spawn(&drop_profile, save_state.scene_id, current_room,
                        x,y,z,0,(uint16_t)item);
        if (!a) return false; /* actor pool records refusal; authored items retry */
        a->data[0] = placed ? -1 : DROP_LIFETIME;
        a->data[1] = placed ? GP_DROP_DELAY : 0;
        a->data[2] = (int32_t)flag;
        a->data[3] = y;
    }
    return true;
}
bool world_props_enemy_drop(int32_t x,int32_t y,int32_t z,unsigned item,unsigned count)
{
    return spawn_drop(x,y,z,item,count,0,false);
}
void world_props_reset(void)
{
    unsigned int i;
    world_signs_reset();
    removed = 0; carried = ACTOR_HANDLE_NONE; carry_action = false;
    for (i=0;i<ACTOR_POOL_MAX;++i) {
        actor_t *a = actor_sys_slot(i);
        if (a && (a->profile->id == WORLD_PROP_ID || a->profile->id == DROP_ACTOR_ID)) actor_kill(a);
    }
}
bool world_props_present(unsigned int i)
{
    return i < KOKIRI_WORLD_PROP_COUNT && !(removed & (1u<<i)) &&
           kokiri_world_props[i].scene == save_state.scene_id;
}
static void break_prop(actor_t *a)
{
    const kokiri_world_prop_t *p = &kokiri_world_props[a->data[0]];
    item_drop_t drop;
    unsigned int flag = 0;
    if (p->id == 0x111) {
        drop.item = (uint8_t)item_drop_filter(p->param & 31);
        drop.count = 1; flag = (p->param >> 9) & 63;
    } else drop = item_drop_random((p->param >> 8)&15, random_next());
    spawn_drop(a->x,a->y,a->z,drop.item,drop.count,flag,false);
    removed |= 1u << a->data[0];
    actor_kill(a);
    gameplay.events |= GP_EVENT_CUT;
}
void world_props_grass_drop(unsigned int index, unsigned int random)
{
    const kokiri_prop_t *p = &kokiri_grass[index];
    unsigned int param = kokiri_grass_params[index];
    item_drop_t drop;
    if ((param & 3) == 1) {
        drop.item = (uint8_t)item_drop_filter((random & 1) ? 3 : 16);
        drop.count = 1;
    } else drop = item_drop_random((param >> 8)&15, random);
    spawn_drop(p->x,p->y,p->z,drop.item,drop.count,0,false);
}
void world_props_step(const gameplay_input_t *in)
{
    unsigned int i;
    actor_t *a = 0;
    uint32_t spawned = 0;
    typedef char world_prop_mask_fits[KOKIRI_WORLD_PROP_COUNT <= 32 ? 1 : -1];
    last_in = *in;
    current_room=in->room;
    world_signs_step(in);
    /* 2026-10-09 speed: one pool scan for the spawned prop indices, not a
     * full actor-pool scan per prop in the room (32 x 96 slots per step). */
    while ((a = actor_sys_find(WORLD_PROP_ID,a)))
        if ((uint32_t)a->data[0] < KOKIRI_WORLD_PROP_COUNT) spawned |= 1u << a->data[0];
    a = 0;
    for (i=0; i<KOKIRI_WORLD_PROP_COUNT; ++i) {
        const kokiri_world_prop_t *p = &kokiri_world_props[i];
        if (p->room != in->room || !world_props_present(i)) continue;
        if (spawned & (1u << i)) continue;
        if (p->id == 0x15) {
            /* Authored hearts do not use the random/drop health conversion. */
            if (spawn_drop(p->x,p->y,p->z,p->param&255,1,(p->param>>8)&63,true))
                removed |= 1u<<i;
        } else {
            a=actor_spawn(&prop_profile,p->scene,p->room,p->x,p->y,p->z,p->yaw,p->param);
            if (a) a->data[0]=(int32_t)i;
            a=0;
        }
    }
    while ((a=actor_sys_find(DROP_ACTOR_ID,a))) {
        if (a->scene != save_state.scene_id) continue;
        if (a->data[0] == 0) { actor_kill(a); continue; }
        if (a->data[0] > 0) --a->data[0];
        if (a->data[1] < GP_DROP_DELAY) { ++a->data[1]; continue; }
        if (near(in,a,30)) {
            bool first = (a->params==12 && !save_state.nut_owned) ||
                         (a->params==13 && !save_state.stick_owned);
            if (!item_drop_give(a->params)) continue;
            if (a->data[2]) save_set_collectible(a->scene,(unsigned)a->data[2]);
            gameplay.rupees=save_state.rupees;
            if(a->params<=2)gameplay.events|=GP_EVENT_RUPEE;
            else gameplay.events2|=a->params==3?GP2_EVENT_HP_RECOVER:GP2_EVENT_GET_ITEM;
            unsigned item=a->params;
            actor_kill(a);
            if (first) { gameplay_drop_message(item); return; }
        }
    }
    a=0;
    while ((a=actor_sys_find(WORLD_PROP_ID,a))) {
        if (a->scene != save_state.scene_id) continue;
        if(a->data[6]>0) --a->data[6];
        if (actor_handle(a)==carried) {
            continue; /* player_lift attachment events own the hand transform */
        }
        if (a->data[1]) {
            if(--a->data[5]<=0) { removed|=1u<<a->data[0];actor_kill(a);continue; }
            int32_t s,c,pos[3]={a->x,a->y,a->z};
            gameplay_sincos(a->yaw,&s,&c);
            a->data[2] -= 137; /* -1.2 * (20/30)^2 in Q8 */
            if (gameplay_ball_move(pos,(s*a->data[3])>>16,a->data[2]/256,(c*a->data[3])>>16)) {
                a->x=pos[0]; a->y=pos[1]+6; a->z=pos[2];
                if(a->data[1]==2) { a->data[1]=0; a->data[2]=0; }
                else break_prop(a);
            } else { a->x=pos[0]; a->y=pos[1]; a->z=pos[2]; }
        }
    }
}
bool world_props_carrying(void) { return actor_resolve(carried) != 0; }

/* Read-only range/facing check: true when a liftable prop is in reach.
 * Mirrors world_props_interact() conditions without consuming A or changing state. */
bool world_props_near_liftable(void)
{
    actor_t *a = 0;
    if (actor_resolve(carried)) return false;
    while ((a = actor_sys_find(WORLD_PROP_ID, a))) {
        unsigned int id = kokiri_world_props[a->data[0]].id;
        int16_t turn;
        if (id != 0x111 && id != 0x14E) continue;
        if (a->scene != save_state.scene_id || a->room != last_in.room || a->data[1]) continue;
        if (!near(&last_in, a, 50)) continue;
        turn = (int16_t)(gameplay_facing(a->x - last_in.x, a->z - last_in.z) - last_in.yaw);
        if (turn < -0x2AAA || turn > 0x2AAA) continue;
        return true;
    }
    return false;
}

bool world_props_interact(const gameplay_input_t *in)
{
    actor_t *a=actor_resolve(carried);
    if (a) {
        carry_action = in->interact || in->attack;
        if (carry_action) gameplay.events |= GP_EVENT_PICKUP; /* consume A */
        return true;
    }
    if (!in->interact || !in->grounded || gameplay_is_talking() || gameplay.attack_phase) return false;
    while ((a=actor_sys_find(WORLD_PROP_ID,a))) {
        int16_t turn;
        unsigned int id=kokiri_world_props[a->data[0]].id;
        if(id!=0x111 && id!=0x14E) continue;
        if (a->scene != save_state.scene_id || a->room != in->room || a->data[1] || !near(in,a,50)) continue;
        turn=(int16_t)(gameplay_facing(a->x-in->x,a->z-in->z)-in->yaw);
        if (turn < -0x2AAA || turn > 0x2AAA) continue;
        carried=actor_handle(a);a->room=ACTOR_ROOM_NONE; gameplay.events |= GP_EVENT_PICKUP; return true;
    }
    return false;
}
bool world_props_lift_action(void)
{
    bool result=carry_action;carry_action=false;return result;
}
void world_props_lift_sync(unsigned int events,int speed_q8,int vy_q8,
                          uint16_t yaw,const int32_t hand[3])
{
    actor_t *a=actor_resolve(carried);
    if(!a) return;
    if(events & LIFT_ATTACH) a->data[4]=1;
    if(a->data[4] && hand) { a->x=hand[0];a->y=hand[1];a->z=hand[2]; }
    if(events & LIFT_RELEASE) {
        a->data[4]=0;a->yaw=yaw;a->room=(int8_t)current_room;a->data[5]=450;
        a->data[1]=speed_q8 ? 1 : 2;
        a->data[2]=vy_q8*2/3;a->data[3]=speed_q8*2/(3*256);
        carried=ACTOR_HANDLE_NONE;
    }
}
void world_props_drop_carried(void)
{
    world_props_lift_sync(LIFT_RELEASE,0,0,0,0);
    carry_action=false;
}
void world_props_register(collider_t *storage, unsigned int capacity, const gameplay_input_t *in)
{
    actor_t *a=0; unsigned int n=0;
    while (n<capacity && (a=actor_sys_find(WORLD_PROP_ID,a))) {
        collider_t *c;
        if (!near(in,a,120) || a->scene!=save_state.scene_id || a->data[1] || actor_handle(a)==carried) continue;
        if (kokiri_world_props[a->data[0]].id != 0x111 &&
            kokiri_world_props[a->data[0]].id != 0x1B9) continue; /* sword cannot break rocks */
        c=&storage[n++]; *c=(collider_t){0};
        c->shape=COLSHAPE_CYLINDER; c->actor=a;
        /* Actor-owned cylinders use offsets, not world coordinates. */
        c->radius=12;c->height=32;
        if(kokiri_world_props[a->data[0]].id==0x1B9) { c->radius=21;c->height=48;c->ac_flags=COL_AC_HARD; }
        c->ac_type=AC_TYPE_PLAYER; c->ac_bumper=DMG_DEFAULT; c->tag=0x600;
        collide_set_ac(c);
    }
    world_signs_register(storage+n,capacity-n,in);
}
void world_props_collect(void)
{
    world_signs_collect();
    unsigned int i;
    for (i=0;i<collide_event_count();++i) {
        const collide_event_t *e=collide_event(i);
        actor_t *a=actor_resolve(e->ac_actor);
        if (a && a->profile->id==WORLD_PROP_ID) {
            if(kokiri_world_props[a->data[0]].id==0x1B9) {
                if(!a->data[6]) { a->data[6]=24;gameplay.events|=GP_EVENT_WALL_HIT; }
            } else break_prop(a);
        }
    }
}
static void body_push(int32_t *x,int32_t *z,int px,int py,int pz,int y,int radius,int height)
{
    int dx=*x-px,dz=*z-pz,dist;
    if(y>=py+height || y+40<=py || dx<=-radius || dx>=radius || dz<=-radius || dz>=radius) return;
    dist=(int)collide_isqrt((uint32_t)(dx*dx+dz*dz));
    if(dist>=radius) return;
    if(!dist) { dx=0;dz=-1;dist=1; }
    *x+=dx*(radius-dist)/dist;*z+=dz*(radius-dist)/dist;
}
void world_props_displace(int32_t x,int32_t y,int32_t z,unsigned int room,int32_t out[2])
{
    int32_t px=x,pz=z;unsigned int i;actor_t *a=0;
    while((a=actor_sys_find(WORLD_PROP_ID,a)))
        if(a->scene==save_state.scene_id && a->room==(int)room && !a->data[1] && actor_handle(a)!=carried) {
            const kokiri_world_prop_t *p=&kokiri_world_props[a->data[0]];
            int radius=22,height=18;
            if(p->id==0x111) { radius=24;height=32; }
            else if(p->id==0x1B9) { radius=33;height=48; }
            else if(p->id==0x14F && (p->param&3)==2) { radius=24;height=44; }
            body_push(&px,&pz,a->x,a->y,a->z,y,radius,height);
        }
    for(i=0;i<KOKIRI_CHEST_COUNT;++i) {
        const kokiri_chest_t *c=&kokiri_chests[i];
        if(c->scene==save_state.scene_id && c->room==room)
            body_push(&px,&pz,c->x,c->y,c->z,y,(c->param>>12)==5 ? 22 : 32,40);
    }
    if(save_state.scene_id==SAVE_SCENE_KOKIRI_FOREST)
        for(i=0;i<KOKIRI_SIGN_COUNT;++i) {
            const kokiri_prop_t *s=&kokiri_signs[i];
            if(s->room==room) body_push(&px,&pz,s->x,s->y,s->z,y,24,50);
        }
    out[0]=px-x;out[1]=pz-z;
}
