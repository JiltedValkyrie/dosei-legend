#pragma GCC optimize("Os") /* per-step logic, small: size over speed (work RAM) */
#include "player_slope.h"
#include "kokiri_camera.h"

static int32_t approach(int32_t v,int32_t target,int32_t up,int32_t down)
{
    if (v<target) { v+=up; if(v>target)v=target; }
    else if(v>target) { v-=down; if(v<target)v=target; }
    return v;
}
static uint16_t turn(uint16_t from,uint16_t to,int32_t step)
{
    int32_t d=(int16_t)(uint16_t)(to-from);
    if(d>step)d=step;
    if(d<-step)d=-step;
    return (uint16_t)(from+d);
}

void player_slope_update(player_slope_t *s,const bg_hit_t *floor,
                          uint16_t movement_yaw,int32_t movement_speed_q8,uint16_t *facing)
{
    int32_t ny,target,up,down,diff;
    uint16_t downhill;
    bool slippery;
    if(!floor || floor->normal[1]<=0) {
        s->active=false; s->speed_q8=s->push_q8=0; return;
    }
    ny=floor->normal[1]; if(ny>16384)ny=16384;
    downhill=kokiri_camera_facing(floor->normal[0],floor->normal[2]);
    slippery=bg_floor_effect(floor)==1;
    target=(16384-ny)*40*256/16384;
    if(!s->active) {
        s->push_q8=slippery?s->push_q8:0;
        if(!slippery)return;
        diff=(int16_t)(uint16_t)(downhill-movement_yaw);
        if(diff<0)diff=-diff;
        if(diff>0x3E80) {
            up=target*target/25600; if(up<205)up=205;
            s->push_yaw=downhill;
            s->push_q8=approach(s->push_q8,target,up,up);
            return;
        }
        s->active=true; s->speed_q8=movement_speed_q8;
        s->yaw=movement_yaw; s->push_q8=0;
        diff=(int16_t)(uint16_t)(*facing-downhill);
        s->face_up=diff>=0x4000 || diff<=-0x4000;
    }
    if(target>10*256)target=10*256;
    up=target*target/25600; if(up<171)up=171;
    down=ny*512/(16384*300); if(down<1)down=1;
    if(!slippery) { target=0; down=ny*5120/(16384*3); if(down<1)down=1; }
    s->speed_q8=approach(s->speed_q8,target,up,down);
    if(!s->speed_q8 && !target)s->active=false;
    /* SmoothStep is per-update (2/3); ScaledStep already includes 1.5. */
    diff=(int16_t)(uint16_t)(downhill-s->yaw);
    if(diff<0)diff=-diff;
    diff/=15; if(diff<533)diff=533; if(diff>2667)diff=2667;
    s->yaw=turn(s->yaw,downhill,diff);
    *facing=turn(*facing,(uint16_t)(downhill+(s->face_up?0x8000:0)),2000);
}

unsigned player_fall_damage(int32_t distance,unsigned floor_type)
{
    if(floor_type==6 || floor_type==9 || distance<400)return 0;
    return distance<800?8:16;
}

bool player_slope_ground(bg_vec_t *feet)
{
    bg_vec_t from=*feet;
    bg_hit_t hit;
    int32_t y;
    from.y++;
    y=bg_floor(&from,BG_IGNORE_ENTITY,&hit);
    if(y==BG_Y_MIN || y>feet->y || feet->y-y>18)return false;
    feet->y=y;
    return true;
}
