"""Execute the temporary combat boundary across skipped/catch-up core steps."""
from pathlib import Path
import os
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT/'src/oot_core_host.c'
PROXY = ROOT/'oot-core/src/bridge_player.cpp'
HEADER = '#include "' + (ROOT/'oot-core/include/oot_core_host.h').as_posix() + '"\n'

class CombatBridge(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_real_octorok_reflection_follows_semantic_shield_plane(self):
        oot = Path(os.environ.get('DOSEI_OOT', ROOT.parents[2]/'game-decomps/n64/oot'))
        projectile = oot/'src/overlays/actors/ovl_En_Okuta/z_en_okuta.c'
        matrix = oot/'src/code/sys_matrix.c'
        if not projectile.exists() or not matrix.exists():
            self.skipTest('local decomp sources required for native projectile regression')
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>
''' + HEADER + r'''
typedef float f32; typedef short s16; typedef int s32;
typedef struct { f32 x,y,z; } Vec3f;
typedef struct { s16 x,y,z; } Vec3s;
typedef union { f32 mf[4][4]; struct {
    f32 xx,yx,zx,wx,xy,yy,zy,wy,xz,yz,zz,wz,xw,yw,zw,ww;
}; } MtxF;
typedef struct { Vec3f pos; Vec3s rot; } PosRot;
typedef struct { PosRot world,home; struct { Vec3s rot; } shape;
    f32 gravity,speed,floorHeight; unsigned int bgCheckFlags; } Actor;
typedef struct { unsigned int atFlags,acFlags,ocFlags1,colMaterial; } Collider;
typedef struct { Collider base; struct { struct { unsigned int dmgFlags; } atDmgInfo; } elem; } ColliderQuad;
typedef struct { Actor actor; MtxF shieldMf; ColliderQuad shieldQuad; int currentShield; } Player;
typedef struct { Player* player; int colChkCtx; } PlayState;
typedef struct { Actor actor; ColliderQuad collider; int timer; } EnOkuta;
static OotCoreCombatState sCombat;
static int adult,ac_calls,at_calls,killed,broken;
static Vec3f quad[4];
#define LINK_IS_ADULT (adult)
#define PLAYER_SHIELD_DEKU 1
#define PLAYER_SHIELD_HYLIAN 2
#define COL_MATERIAL_WOOD 1
#define COL_MATERIAL_METAL 2
#define AT_HIT 1u
#define AT_BOUNCED 2u
#define AT_TYPE_ENEMY 4u
#define AT_TYPE_PLAYER 8u
#define AC_HIT 1u
#define OC1_HIT 1u
#define BGCHECKFLAG_WATER 1u
#define BGCHECKFLAG_WALL 2u
#define BGCHECKFLAG_GROUND 4u
#define BGCHECK_Y_MIN (-32000)
#define DMG_DEKU_STICK 2u
#define GET_PLAYER(p) ((p)->player)
#define CLAMP_MIN(x,minimum) ((x)<(minimum)?(minimum):(x))
#define SQ(x) ((x)*(x))
#define RAD_TO_BINANG(x) ((s16)(int)((x)*(32768.0/3.14159265358979323846)))
static f32 Math_SinS(s16 angle) { return sinf(angle*(3.14159265358979323846f/32768)); }
static f32 Math_CosS(s16 angle) { return cosf(angle*(3.14159265358979323846f/32768)); }
static f32 Math_FAtan2F(f32 y,f32 x) { return atan2f(y,x); }
static void Collider_SetQuadVertices(ColliderQuad* q,Vec3f* a,Vec3f* b,Vec3f* c,Vec3f* d) {
    quad[0]=*a;quad[1]=*b;quad[2]=*c;quad[3]=*d;
}
static void CollisionCheck_SetAC(PlayState* p,int* context,Collider* c) { ++ac_calls; }
static void CollisionCheck_SetAT(PlayState* p,int* context,Collider* c) { ++at_calls; }
#define EffectSsHahen_SpawnBurst(...) (++broken)
#define SfxSource_PlaySfxAtFixedWorldPos(...) ((void)0)
static void Actor_Kill(Actor* actor) { ++killed; }
''' + graphics.function(PROXY, 'static void PlayerProxy_UpdateShield(') + '\n' +
            graphics.function(matrix, 'void Matrix_MtxFToYXZRotS(') + '\n' +
            graphics.function(projectile, 'void EnOkuta_ProjectileFly(EnOkuta* this, PlayState* play) {') + r'''
int main(void) {
    const unsigned short facing[]={0,0x2000,0x4000,0x8000,0xc000,0xe000};
    Player player={0};PlayState play={&player,0};
    player.actor.world.pos=(Vec3f){100,20,-200};
    for(unsigned i=0;i<sizeof(facing)/sizeof(facing[0]);++i) {
        /* Stale pose data must be fully replaced by the actual bridge. */
        for(int r=0;r<4;++r)for(int c=0;c<4;++c) player.shieldMf.mf[r][c]=123;
        adult=i&1;player.currentShield=adult?PLAYER_SHIELD_HYLIAN:PLAYER_SHIELD_DEKU;
        player.actor.shape.rot.y=(s16)facing[i];sCombat.flags=OOT_COMBAT_SHIELD;
        PlayerProxy_UpdateShield(&player,&play);
        assert(ac_calls==(int)i+1 && at_calls==(int)i+1);
        EnOkuta rock={0};rock.timer=10;rock.actor.floorHeight=0;
        rock.collider.base.atFlags=AT_HIT|AT_BOUNCED|AT_TYPE_ENEMY;
        /* Native actor reads shieldMf through native matrix-angle extraction. */
        EnOkuta_ProjectileFly(&rock,&play);
        assert(!killed && !broken && rock.timer==30);
        assert(rock.collider.base.atFlags==AT_TYPE_PLAYER);
        assert(rock.collider.elem.atDmgInfo.dmgFlags==DMG_DEKU_STICK);
        int error=(short)(rock.actor.world.rot.y-(short)facing[i]);
        assert(error>=-2 && error<=2);
        /* Reflected velocity points out through the actual guard plane. */
        float center_x=(quad[0].x+quad[1].x+quad[2].x+quad[3].x)*.25f-player.actor.world.pos.x;
        float center_z=(quad[0].z+quad[1].z+quad[2].z+quad[3].z)*.25f-player.actor.world.pos.z;
        float outward=center_x*Math_SinS(rock.actor.world.rot.y)+center_z*Math_CosS(rock.actor.world.rot.y);
        assert(outward>17.9f && outward<18.1f);
    }
    sCombat.flags=OOT_COMBAT_SHIELD|OOT_COMBAT_DISABLED;
    PlayerProxy_UpdateShield(&player,&play);assert(ac_calls==6 && at_calls==6);
    return 0;
}
''')

    def test_health_callback_preserves_full_damage_and_predicts_queued_result(self):
        self.run_c(r'''
#include <assert.h>
#include <string.h>
''' + HEADER + '#include "' + (ROOT/'src/gameplay.h').as_posix() + '"\n' +
                   '#include "' + (ROOT/'src/save_state.h').as_posix() + '"\n' + r'''
gameplay_t gameplay;
save_state_t save_state;
static unsigned short recomp_link_yaw=0x4567;
''' + graphics.function(ROOT/'src/save_state.c', 'void            save_heal(') + '\n' +
                   graphics.function(HOST, 'static int host_health_change(') + r'''
int main(void) {
    assert(sizeof gameplay.hurt_damage==2);
    assert(sizeof(((OotCorePlayerHit*)0)->damage)==1); /* collider ABI unchanged */
    save_state.health=save_state.health_capacity=320;
    assert(!host_health_change(-320)); /* 20 full hearts can be lethal */
    assert(gameplay.hurt_pending && gameplay.hurt_damage==320 && save_state.health==320);
    assert(gameplay.hurt_yaw==0x4567 && !gameplay.hurt_core && !gameplay.hurt_speed);
    assert(!host_health_change(-1) && gameplay.hurt_damage==320 && save_state.health==320);
    /* Duplicate calls preserve the already queued result and never debit now. */
    memset(&gameplay,0,sizeof gameplay);
    save_state.health=8; gameplay.invulnerable=1;
    assert(host_health_change(-32768) && gameplay.hurt_damage==32768 && save_state.health==8);
    memset(&gameplay,0,sizeof gameplay);
    save_state.source_double_defense=1; save_state.health=160;
    assert(!host_health_change(-320) && gameplay.hurt_damage==320 && save_state.health==160);
    gameplay.hurt_pending=0; save_state.health=161;
    assert(host_health_change(-320));
    gameplay.hurt_pending=0; save_state.health=3;
    assert(!host_health_change(-5)); /* odd damage rounds upward when halved */
    gameplay.hurt_pending=0; save_state.health=4;
    assert(host_health_change(-5));
    memset(&gameplay,0,sizeof gameplay);
    gameplay.intangible=1; save_state.health=5;
    assert(host_health_change(-32768) && !gameplay.hurt_pending && save_state.health==5);
    memset(&gameplay,0,sizeof gameplay);
    save_state.source_double_defense=0; save_state.health=4;
    assert(host_health_change(12) && save_state.health==16 && !gameplay.hurt_pending);
    assert(host_health_change(32767) && save_state.health==320); /* immediate capped heal */
    gameplay.dead=1; save_state.health=0;
    assert(!host_health_change(-8) && !gameplay.hurt_pending);
    return 0;
}
''')

    def test_tool_spawn_serial_survives_reordering_and_address_reuse(self):
        path = ROOT/'oot-core/src/bridge_items.cpp'
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
typedef unsigned short u16;
typedef struct Actor Actor;
struct Actor { Actor *next; void *update; };
static struct { struct { struct { Actor *head; } actorLists[3]; } actorCtx; } play;
#define gOotCorePlay (&play)
#define ACTORCAT_ITEMACTION 0
#define ACTORCAT_EXPLOSIVE 1
#define ACTORCAT_MISC 2
static const unsigned char sToolCats[]={ACTORCAT_ITEMACTION,ACTORCAT_EXPLOSIVE,ACTORCAT_MISC};
static struct { Actor *actor; u16 serial; } sToolIds[16];
static u16 sToolSerial;
''' + graphics.function(path, 'static bool tool_live_pointer(') + '\n' +
            graphics.function(path, 'static u16 tool_identity(') + r'''
int main(void) {
    Actor arrows[2]={{0}},boom={0};unsigned a,b,c,d;
    arrows[0].next=&arrows[1];arrows[0].update=arrows[1].update=(void*)1;
    play.actorCtx.actorLists[0].head=&arrows[0];
    a=tool_identity(&arrows[0],true);b=tool_identity(&arrows[1],true);
    assert(a && b && a!=b);
    arrows[0].next=0;arrows[1].next=&arrows[0];play.actorCtx.actorLists[0].head=&arrows[1];
    assert(tool_identity(&arrows[0],false)==a && tool_identity(&arrows[1],false)==b);
    c=tool_identity(&arrows[0],true);assert(c!=a && c!=b);
    assert(tool_identity(&arrows[0],false)==c);
    boom.update=(void*)1;play.actorCtx.actorLists[ACTORCAT_MISC].head=&boom;
    d=tool_identity(&boom,true);assert(d && d!=b && d!=c && tool_live_pointer(&boom));
    assert(tool_identity(&boom,false)==d);
    arrows[0].update=0;assert(!tool_live_pointer(&arrows[0]));
    sToolSerial=65535;assert(tool_identity(&arrows[0],true)==1);
    return 0;
}
''')

    def test_host_hit_queue_guard_and_invulnerability(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
''' + HEADER + r'''
#define GP_EVENT_GUARD 128u
static struct {
    int dead,intangible,hurt_pending,hurt_damage,hurt_yaw,hurt_speed,hurt_effect,hurt_large,hurt_core;
    int guard_pending, events;
} gameplay;
static int paused;
static int gameplay_is_paused(void) { return paused; }
''' + graphics.function(HOST, 'static int host_player_hit(') + r'''
int main(void) {
    OotCorePlayerHit hit={4*65536,120,8,2,0};
    assert(host_player_hit(&hit)==1 && gameplay.hurt_pending && gameplay.hurt_damage==8);
    assert(gameplay.hurt_yaw==120 && gameplay.hurt_speed==4*65536 && gameplay.hurt_effect==2);
    /* A second core update before C consumes the hit must not deal damage twice. */
    hit.damage=99;assert(host_player_hit(&hit)==0 && gameplay.hurt_damage==8);
    gameplay.hurt_pending=0;gameplay.intangible=1;assert(!host_player_hit(&hit));
    gameplay.intangible=0;hit.flags=OOT_HIT_GUARD;
    assert(host_player_hit(&hit) && gameplay.guard_pending && !gameplay.hurt_pending);
    hit.flags=OOT_HIT_LARGE;assert(host_player_hit(&hit) && gameplay.hurt_large);
    gameplay.hurt_pending=0;gameplay.intangible=1;
    assert(host_player_hit(&hit) && gameplay.hurt_damage==0 && gameplay.hurt_core);
    gameplay.intangible=0;
    gameplay.hurt_pending=0;paused=1;assert(!host_player_hit(&hit));
    paused=0;gameplay.dead=1;assert(!host_player_hit(&hit));
    assert(!host_player_hit(0));
    return 0;
}
''')

    def test_proxy_consumes_ac_and_knockback_once(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
''' + HEADER + r'''
typedef int PlayState;
typedef struct Actor Actor;
struct Actor { struct { unsigned int damage; int acHitSpecialEffect; } colChkInfo; };
typedef struct { unsigned int acFlags; Actor *ac; } Collider;
typedef struct {
    Actor actor;
    struct { Collider base; } shieldQuad,cylinder;
    int knockbackType,knockbackDamage,knockbackRot,knockbackSpeed;
} Player;
static OotCoreCombatState sCombat;
#define AC_BOUNCED 2u
#define AC_HIT 1u
#define PLAYER_KNOCKBACK_NONE 0
#define PLAYER_KNOCKBACK_LARGE 2
#define PLAYER_KNOCKBACK_LARGE_ELECTRIFIED 3
#define HIT_SPECIAL_EFFECT_NONE 0
#define HIT_SPECIAL_EFFECT_ELECTRIC 3
#define HIT_SPECIAL_EFFECT_KNOCKBACK 4
static int OotCore_BgInt(int x) { return x; }
static int Actor_WorldYawTowardActor(Actor *a,Actor *b) { return 123; }
static void Collider_ResetCylinderAC(PlayState *p,Collider *c) { c->acFlags &= ~AC_HIT; }
static void Collider_ResetQuadAC(PlayState *p,Collider *c) { c->acFlags=0; }
static OotCorePlayerHit received;
static int calls;
static int receive(const OotCorePlayerHit *h) { ++calls;received=*h;return 1; }
static const OotCoreHost host={.player_hit=receive};
static const OotCoreHost *gOotCoreHost=&host;
''' + graphics.function(PROXY, 'static void PlayerProxy_ReceiveHit(') + r'''
int main(void) {
    Player player={0}; Actor enemy={0}; PlayState play=0;
    player.cylinder.base.acFlags=AC_HIT;player.cylinder.base.ac=&enemy;
    player.actor.colChkInfo.damage=8;player.actor.colChkInfo.acHitSpecialEffect=2;
    PlayerProxy_ReceiveHit(&player,&play);
    assert(calls==1 && received.damage==8 && received.effect==2 && received.yaw==123);
    assert(sCombat.flags & OOT_COMBAT_INTANGIBLE);
    PlayerProxy_ReceiveHit(&player,&play);assert(calls==1);
    sCombat.flags=0;player.cylinder.base.acFlags=AC_HIT;
    player.shieldQuad.base.acFlags=AC_BOUNCED;
    PlayerProxy_ReceiveHit(&player,&play);
    assert(calls==2 && received.flags==OOT_HIT_GUARD && !player.cylinder.base.acFlags);
    player.knockbackType=PLAYER_KNOCKBACK_LARGE_ELECTRIFIED;
    player.knockbackDamage=4;player.knockbackRot=555;player.knockbackSpeed=7;
    PlayerProxy_ReceiveHit(&player,&play);
    assert(calls==3 && received.damage==12 && received.yaw==555 && received.speed_q16==7*65536);
    assert(received.effect==3 && (received.flags&OOT_HIT_LARGE));
    assert(!player.knockbackType && !player.knockbackDamage);
    sCombat.flags=OOT_COMBAT_INTANGIBLE;player.knockbackType=PLAYER_KNOCKBACK_LARGE;
    player.shieldQuad.base.acFlags=AC_BOUNCED;
    PlayerProxy_ReceiveHit(&player,&play);
    assert(calls==4 && received.damage==0 && received.flags==OOT_HIT_LARGE);
    sCombat.flags=OOT_COMBAT_DISABLED;player.cylinder.base.acFlags=AC_HIT;
    PlayerProxy_ReceiveHit(&player,&play);assert(calls==4 && !player.cylinder.base.acFlags);
    return 0;
}
''')

    def test_host_melee_snapshot_preserves_source_weapon_flags(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
''' + HEADER + '#include "' + (ROOT/'src/player_attack.h').as_posix() + '"\n' + r'''
#define EQUIP_VALUE_SWORD_BIGGORON 3
static struct { unsigned attack_id,shielding,intangible,hurt_pending,invulnerable,dead,face_locked,swing_count; } gameplay;
static struct { unsigned link_age,equip_sword,equip_shield; } save_state;
static int stick;
static int player_items_stick(void) { return stick; }
static int gameplay_is_paused(void) { return 0; }
static int gameplay_blocks_world(void) { return 0; }
''' + graphics.function(HOST, 'static void host_player_combat(') + r'''
int main(void) {
    OotCoreCombatState out;
    save_state.link_age=1;gameplay.attack_id=ATTACK_FORWARD;gameplay.swing_count=7;
    host_player_combat(&out);assert(out.damage_flags==DMG_SLASH_KOKIRI && out.damage==1 && out.swing==7);
    gameplay.attack_id=ATTACK_JUMP_FINISH;host_player_combat(&out);
    assert(out.damage_flags==DMG_JUMP_KOKIRI && out.damage==2);
    save_state.link_age=0;save_state.equip_sword=3;host_player_combat(&out);
    assert(out.damage_flags==DMG_JUMP_GIANT && out.damage==8);
    stick=1;host_player_combat(&out);assert(out.damage_flags==DMG_DEKU_STICK && out.damage==4);
    gameplay.shielding=1;gameplay.hurt_pending=1;save_state.equip_shield=2;host_player_combat(&out);
    assert(out.flags&(OOT_COMBAT_SHIELD|OOT_COMBAT_INTANGIBLE));assert(out.shield==2);
    return 0;
}
''')

if __name__ == '__main__': unittest.main()
