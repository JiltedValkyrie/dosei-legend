/* Water enemy sprite anchors: offline frame points, never a skeleton walk. */
#include "oot_prelude.h"
#include "water_enemy_sprite.h"
#include "overlays/actors/ovl_En_Tite/z_en_tite.h"
#include "overlays/actors/ovl_En_Firefly/z_en_firefly.h"
#include "overlays/actors/ovl_En_Ny/z_en_ny.h"
#include "assets/objects/object_tite/object_tite.h"
#include "assets/objects/object_firefly/object_firefly.h"
extern "C" int printf(const char*, ...);
extern "C" void abort(void);
#define CHECK(x) do { if (!(x)) { printf("line %d: %s\n", __LINE__, #x); abort(); } } while (0)
#include "anim_defs.inc"
struct FieldAnchorClip { AnimationHeader* animation; u16 frames, points; const s16* xyz; };
#include "../../build/oot-core/water_anchors.inc"
static bool near(f32 a, f32 b) { return a-b < 0.5f && b-a < 0.5f; }

/* Identity actor transform: offset only, so table values are visible. */
Vec3f FieldSprite_Point(Actor* a, f32 x, f32 y, f32 z) {
    return {a->world.pos.x+x, a->world.pos.y+y, a->world.pos.z+z};
}

int main(void) {
    /* Re-read the generated tables through the real lookup. */
    EnTite tite={};
    tite.actor.world.pos={100,200,300};
    tite.skelAnime.animation=&object_tite_Anim_0004F8;
    tite.collider.elements=tite.colliderElements;
    tite.colliderElements[0].dim.modelSphere.center={1,2,3};
    tite.colliderElements[0].dim.modelSphere.radius=20;
    tite.colliderElements[0].dim.scale=1.5f;
    static const int frames[]={0, 7, 14, 99, -3};
    for (int frame : frames) {
        tite.skelAnime.curFrame=frame;
        WaterSprite_Tektite(&tite);
        int f=frame<0 ? 0 : frame>14 ? 14 : frame;
        const s16* p=points_object_tite_Anim_0004F8+f*12;
        CHECK(near(tite.backRightFootPos.x,100+p[0]) && near(tite.backRightFootPos.y,200+p[1]));
        CHECK(near(tite.frontRightFootPos.z,300+p[5]));
        CHECK(near(tite.backLeftFootPos.x,100+p[6]));
        CHECK(near(tite.frontLeftFootPos.z,300+p[11]));
    }
    CHECK(tite.colliderElements[0].dim.worldSphere.center.x==101);
    CHECK(tite.colliderElements[0].dim.worldSphere.center.z==303);
    CHECK(tite.colliderElements[0].dim.worldSphere.radius==30);
    EnFirefly keese={};
    keese.actor.world.pos={-10,0,10};
    keese.skelAnime.animation=&gKeeseFlyAnim;
    keese.skelAnime.curFrame=3;
    const s16* k=points_gKeeseFlyAnim+3*9;
    Vec3f left=WaterSprite_KeeseAnchor(&keese, KEESE_LIMB_LEFT_WING_END);
    Vec3f right=WaterSprite_KeeseAnchor(&keese, KEESE_LIMB_RIGHT_WING_END_ROOT);
    Vec3f body=WaterSprite_KeeseAnchor(&keese, KEESE_LIMB_BODY);
    CHECK(near(left.x,-10+k[0]) && near(right.y,k[4]) && near(body.z,10+k[8]));
    /* Root display offset is baked into the Keese table: body sits high. */
    CHECK(body.y > 1000);
    /* Unknown clip keeps the actor origin; build validation forbids it. */
    keese.skelAnime.animation=NULL;
    body=WaterSprite_KeeseAnchor(&keese, KEESE_LIMB_BODY);
    CHECK(body.x==-10 && body.y==0 && body.z==10);
    /* Spikes: the source sphere follows the actor and Update's scale. */
    EnNy ny={};
    ny.actor.world.pos={7,8,9};
    ny.collider.elements=ny.colliderElements;
    ny.colliderElements[0].dim.modelSphere.radius=15;
    ny.colliderElements[0].dim.scale=2.0f;
    WaterSprite_Spikes(&ny);
    CHECK(ny.colliderElements[0].dim.worldSphere.center.x==7);
    CHECK(ny.colliderElements[0].dim.worldSphere.center.y==8);
    CHECK(ny.colliderElements[0].dim.worldSphere.radius==30);
    printf("water sprite anchors: ok\n");
    return 0;
}
