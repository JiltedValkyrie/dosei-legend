"""Great Fairy source rewards, clip-only character and original refill beam."""
import re
from field_enemy_sources import replace_body, replace_once

ACTORS=('Bg_Dy_Yoseizo','En_Dy_Extra')
SOURCES=tuple('src/overlays/actors/ovl_%s/z_%s.c'%(n,n.lower()) for n in ACTORS)
OBJECTS=SPRITE_OBJECTS=('object_dy_obj',)
NPC_SOURCES=[('ACTOR_BG_DY_YOSEIZO',SOURCES[0])]
DRAW_SOURCES=[('ACTOR_EN_DY_EXTRA',SOURCES[1])]
SOURCE_SCENES=('daiyousei_izumi','yousei_izumi_yoko')


def adapt(rel,text):
    if rel==SOURCES[0][:-2]+'.h':
        text=re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];',r'Vec3s* \1;',text)
        # Cosmetic source particles share the bounded Saturn effect budget.
        text=replace_once(text,'#define BG_DY_YOSEIZO_EFFECT_COUNT 200','#define BG_DY_YOSEIZO_EFFECT_COUNT 32')
        text=replace_once(text,'f32 yVelocityPhase;', 's32 yVelocityPhase;')
        text=replace_once(text,'f32 rot;', 's32 rot;')
    elif rel==SOURCES[0]:
        text='#include "child_route_npc_sprite.h"\n'+text
        text=text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
        text=replace_once(text,
            'Actor_TrackPlayer(play, &this->actor, &this->headRot, &this->torsoRot, this->actor.focus.pos);',
            '/* Focus retained; no runtime head/torso pose tracking. */')
        for name in ('BgDyYoseizo_Draw','BgDyYoseizo_DrawEffects'):
            text=replace_body(text,name,'    /* Offline fairy sprite and source particle snapshot. */')
        text=replace_body(text,'BgDyYoseizo_OverrideLimbDraw','    return false; /* No runtime skeleton. */')
        text=replace_once(text,'this->actionFunc = BgDyYoseizo_Kill;',
                          'this->actionFunc = BgDyYoseizo_Kill;\n            this->actor.draw = NULL;')
        # The animation-derived phase can exceed Q16's numeric range. It is
        # an angle count, so retain its full32-bit integer comparisons.
        text=re.sub(r'this->skelAnime.curFrame \* (\d+)\.0f',r'(s32)this->skelAnime.curFrame * \1',text)
        text=re.sub(r'this->curAnimLastFrame \* (\d+)\.0f',r'(s32)this->curAnimLastFrame * \1',text)
        text=text.replace('TRUNCF_BINANG(this->yVelocityPhase)','(s16)this->yVelocityPhase')
        text=replace_once(text,'effect->rot += 3000.0f;', 'effect->rot += 3000;')
    elif rel==SOURCES[1]:
        # Keep source movement, timer and fade; stripped N64 vertices must
        # never be written. Primitive alpha carries the source factor now.
        text=re.sub(r'    static u8 sVerticesAlphaType\[\] = \{.*?\n    \};\n','',text,flags=re.S)
        text=replace_once(text,'    Vtx* vertices = SEGMENTED_TO_VIRTUAL(gGreatFairySpiralBeamVtx);\n','')
        start=text.index('    s32 i;\n',text.index('void EnDyExtra_Draw(Actor* thisx, PlayState* play) {'))
        end=text.index('    OPEN_DISPS(',start)
        text=text[:start]+text[end:]
        text=replace_once(text,'sPrimColors[this->type].b, 255);',
                          'sPrimColors[this->type].b, (u8)(this->alphaFac * 255.0f));')
    return text
