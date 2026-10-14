"""Source Castle approach/stealth and Meadow warp-pad dependencies."""
import re
from field_enemy_sources import replace_body, replace_once

SPRITE_ACTORS = ('En_Heishi1', 'En_Heishi3')
PROP_ACTORS = ('Bg_Spot15_Rrbox', 'Bg_Spot00_Hanebasi', 'Bg_Mjin')
ACTORS = SPRITE_ACTORS + PROP_ACTORS
SOURCES = tuple(f'src/overlays/actors/ovl_{n}/z_{n.lower()}.c' for n in ACTORS)
SPRITE_OBJECTS = ('object_sd',)
OBJECTS = SPRITE_OBJECTS + ('object_spot15_obj', 'object_spot00_objects',
    'object_mjin', 'object_mjin_oka', 'object_mjin_wind', 'object_mjin_soul',
    'object_mjin_dark', 'object_mjin_ice', 'object_mjin_flame', 'object_mjin_flash')
NPC_SOURCES = [('ACTOR_'+n.upper(),s) for n,s in zip(ACTORS,SOURCES) if n in SPRITE_ACTORS]
DRAW_SOURCES = [('ACTOR_'+n.upper(),s) for n,s in zip(ACTORS,SOURCES) if n in PROP_ACTORS]

def adapt(rel,text):
    if rel in tuple(s[:-2]+'.h' for s in SOURCES[:2]):
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];',r'Vec3s* \1;',text)
    if rel == SOURCES[3]:  # Bg_Spot00_Hanebasi
        # Fx32 range: 37500.0f and 1024000.0f saturate. Scale stays <= 0.008,
        # so 375 * 100 is exact; x / 1024000 is x * 8 / 125 raw Q16 units.
        text=replace_once(text,'sTorchFlameScale * 37500.0f','sTorchFlameScale * 375.0f * 100')
        return replace_once(text,'((thisx->shape.rot.x * -1) - 0x2000) * (1.0f / 1024000.0f)',
            '(f32)((((thisx->shape.rot.x * -1) - 0x2000) * 8) / 125) * 1.52587890625e-05f')
    if rel not in SOURCES[:2]:
        return text
    text='#include "sprite_actor.h"\n'+text
    text=text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    prefix='EnHeishi1' if rel.endswith('z_en_heishi1.c') else 'EnHeishi3'
    text=replace_body(text,prefix+'_Draw','    /* Baked guard; source sight and patrol remain in Update. */')
    text=replace_body(text,prefix+'_OverrideLimbDraw','    return false;')
    if prefix=='EnHeishi1':
        text=replace_once(text,'''                        Matrix_Push();
                        Matrix_RotateY(BINANG_TO_RAD_ALT(this->actor.shape.rot.y + this->headAngle), MTXMODE_NEW);
                        searchBallMult.z = 30.0f;
                        Matrix_MultVec3f(&searchBallMult, &searchBallVel);
                        Matrix_Pop();''','''                        s16 sightYaw = this->actor.shape.rot.y + (s16)this->headAngle;
                        searchBallVel.x = Math_SinS(sightYaw) * 30;
                        searchBallVel.y = 0;
                        searchBallVel.z = Math_CosS(sightYaw) * 30;''')
    return text
