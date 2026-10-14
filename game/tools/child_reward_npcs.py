"""Child route dog, token family, Dampe and Medigoron source actions."""
import re
from field_enemy_sources import replace_body, replace_once
from child_route_npcs import append_update

ACTORS = ('En_Dog', 'En_Gm', 'En_Ssh', 'En_Sth', 'En_Tk')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
OBJECTS = ('object_dog', 'object_gm', 'object_oF1d_map', 'object_ssh', 'object_ahg', 'object_boj', 'object_tk')
NPC_SOURCES = [('ACTOR_' + name.upper(), source) for name, source in zip(ACTORS, SOURCES)]
SOURCE_SCENES = ('kinsuta', 'spot02')
ANIMATION_OBJECTS = {'object_oF1d_map': ('object_gm',)}


def adapt(rel, text):
    if rel in [p[:-2] + '.h' for p in SOURCES]:
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];', r'Vec3s* \1;', text)
    if rel not in SOURCES:
        return text
    text = '#include "child_route_npc_sprite.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(').replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    text = re.sub(r'Actor_TrackPlayer\([^;]+;', '/* Focus/body actions retained; head pose is baked. */', text)
    text = re.sub(r'Math_SmoothStepToS\(&this->(?:headRot|unk_2AC)\.[^;]+;', '/* Baked head pose. */', text)
    for name in re.findall(r'^void (\w*(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    /* Baked sprite; source actions run in Update. */')
    for name in re.findall(r'^s32 (\w*OverrideLimbDraw)\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    return 0; /* No runtime pose. */')
    if rel.endswith('z_en_gm.c'):
        # Source Draw translated local Z before the secondary zero-origin
        # rotation. Keep those exact actor-relative cylinder/talk/focus points.
        text = replace_body(text, 'func_80A3E090', """
    f32 sn = Math_SinS(this->actor.shape.rot.y);
    f32 cs = Math_CosS(this->actor.shape.rot.y);
    f32 distance = 2600.0f * this->actor.scale.z;
    this->collider.dim.pos.x = this->actor.world.pos.x + sn * distance;
    this->collider.dim.pos.y = this->actor.world.pos.y;
    this->collider.dim.pos.z = this->actor.world.pos.z + cs * distance;
    distance = 4300.0f * this->actor.scale.z;
    this->talkPos = this->actor.world.pos;
    this->talkPos.x += sn * distance;
    this->talkPos.z += cs * distance;
    distance = 3800.0f * this->actor.scale.z;
    this->actor.focus.pos = this->actor.world.pos;
    this->actor.focus.pos.x += sn * distance;
    this->actor.focus.pos.z += cs * distance;
    this->actor.focus.pos.y += 100.0f;""")
        text = text.replace('void EnGm_Update(Actor* thisx, PlayState* play) {',
            'void func_80A3E090(EnGm* this);\nvoid EnGm_Update(Actor* thisx, PlayState* play) {')
        text = append_update(text, 'EnGm_Update', '    func_80A3E090(this);')
    elif rel.endswith('z_en_sth.c'):
        text = replace_once(text, '#include "assets/overlays/ovl_En_Sth/ovl_En_Sth.c"',
            'static AnimationHeader sChildDanceAnim = { { 30 }, NULL, NULL, 0 };\n'
            'static AnimationHeader sParentDanceAnim = { { 28 }, NULL, NULL, 0 };')
        text = replace_body(text, 'EnSth_AllocColorDList', '    return NULL; /* Offline material. */')
        text = append_update(text, 'EnSth_Update2', '    Actor_SetFocus(&this->actor, 60.0f);\n    this->unk_2B2 &= ~2;')
    elif rel.endswith('z_en_tk.c'):
        text = replace_body(text, 'func_80B1D200', '    /* Shovel is included in the sprite. */')
        # Source uses shape yaw directly as radians here, despite it being a
        # binary angle. Keep its nearby reward origin with the intended yaw.
        text = replace_once(text,
            'Matrix_RotateY(this->actor.shape.rot.y, MTXMODE_NEW);\n            Matrix_MultVec3f(&rewardOrigin, &rewardPos);',
            'rewardPos.x = Math_SinS(this->actor.shape.rot.y) * rewardOrigin.z;\n'
            '            rewardPos.y = 0.0f;\n'
            '            rewardPos.z = Math_CosS(this->actor.shape.rot.y) * rewardOrigin.z;')
        text = text.replace('#include "child_route_npc_sprite.h"', '#include "child_route_npc_sprite.h"\n#include "child_reward_anchors.inc"')
        text = append_update(text, 'EnTk_Update', """
    Actor_SetFocus(&this->actor, 55.0f);
    this->v3f_304 = this->actor.world.pos;
    this->v3f_304.x -= Math_SinS(this->actor.shape.rot.y) * 40.0f;
    this->v3f_304.z -= Math_CosS(this->actor.shape.rot.y) * 40.0f;
    /* Source facing checks consume these two summed jaw yaw angles. */
    s32 clip = this->skelAnime.animation == &gDampeWalkAnim ? 1 :
               this->skelAnime.animation == &gDampeDigAnim ? 2 : 0;
    s32 sample = (s32)this->skelAnime.curFrame * 4 / (s32)this->skelAnime.animLength;
    this->h_21E = sDampeJawYaw[clip][sample & 3];""")
    elif rel.endswith('z_en_ssh.c'):
        text = replace_once(text, '#include "assets/overlays/ovl_En_Ssh/ovl_En_Ssh.c"',
            '/* Source decorative geometry is an offline sprite input. */')
        text = text.replace('#include "child_route_npc_sprite.h"', '#include "child_route_npc_sprite.h"\n#include "child_reward_anchors.inc"')
        # The blur endpoints use the actor's transform only; no skeleton pose.
        text = replace_once(text, 'Matrix_Push();\n    Matrix_MultVec3f(&p1base, &p1);\n    Matrix_MultVec3f(&p2base, &p2);\n    Matrix_Pop();', """
    f32 sn = Math_SinS(this->actor.shape.rot.y), cs = Math_CosS(this->actor.shape.rot.y);
    p1 = this->actor.world.pos; p2 = p1;
    p1.x += p1base.x * this->actor.scale.x * cs;
    p1.z -= p1base.x * this->actor.scale.x * sn;
    p1.y += p1base.y * this->actor.scale.y;
    p2.x += p2base.x * this->actor.scale.x * cs;
    p2.z -= p2base.x * this->actor.scale.x * sn;
    p2.y += p2base.y * this->actor.scale.y;""")
        # Remaining source matrices position the sway and cylinders in world
        # space, not character bones; preserve that gameplay math.
        text = append_update(text, 'EnSsh_Update', """
    EnSsh_CheckBodyStickHit(this, play);
    EnSsh_Sway(this);
    if (this->spinTimer && !this->swayTimer) {
        if (this->spinTimer >= 2) EnSsh_AddBlureVertex(this);
        else EnSsh_AddBlureSpace(this);
    }
    s32 clip = this->skelAnime.animation == &object_ssh_Anim_000304 ? 0 :
               this->skelAnime.animation == &object_ssh_Anim_0055F8 ? 1 :
               this->skelAnime.animation == &object_ssh_Anim_005BE8 ? 2 : 0;
    s32 sample = (s32)this->skelAnime.curFrame * 4 / (s32)this->skelAnime.animLength;
    ColliderJntSphElementDim* dim = &this->colliderJntSph.elements[0].dim;
    const s16* point = sCursedFamilyContact[clip][sample & 3];
    f32 sn = Math_SinS(this->actor.shape.rot.y), cs = Math_CosS(this->actor.shape.rot.y);
    f32 x = point[0] * this->actor.scale.x, z = point[2] * this->actor.scale.z;
    dim->worldSphere.center.x = this->actor.world.pos.x + x * cs + z * sn;
    dim->worldSphere.center.y = this->actor.world.pos.y + point[1] * this->actor.scale.y;
    dim->worldSphere.center.z = this->actor.world.pos.z + z * cs - x * sn;
    dim->worldSphere.radius = dim->modelSphere.radius * dim->scale;""")
    return text
