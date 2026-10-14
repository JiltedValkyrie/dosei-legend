"""Source mask customers plus Skull Kid's original child/adult actions."""
import re
from field_enemy_sources import replace_body
from child_route_npcs import append_update
ACTORS=('En_Cs','En_Mm','En_Skj','En_Skjneedle')
SOURCES=[f'src/overlays/actors/ovl_{a}/z_{a.lower()}.c' for a in ACTORS]
OBJECTS=('object_cs','object_mm','object_skj','object_sd')
NPC_SOURCES=[('ACTOR_'+a.upper(),p) for a,p in zip(ACTORS,SOURCES)]
STATIC_SPRITES={'object_skj':('gSkullKidNeedleDL','gSkullKidNeedleDL',(('gSkullKidNeedleDL',),))}


def adapt(rel,text):
    if rel.endswith("ovl_En_Heishi2/z_en_heishi2.h"):
        return text.replace("MtxF mtxf_330;", "/* Keaton mask transform baked offline. */")
    if rel in [p[:-2]+'.h' for p in SOURCES]:
        text=re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];',r'Vec3s* \1;',text)
        return re.sub(r'MtxF (spookyMaskMtx|unk_208);','/* Mask transform baked offline. */',text)
    if rel not in SOURCES:return text
    text='#include "child_route_npc_sprite.h"\n'+text
    text=text.replace('SkelAnime_InitFlex(','OotCore_SpriteInitFlex(')
    text=text.replace('Npc_TrackPoint(','ChildRouteSprite_TrackBody(')
    text=re.sub(r'Actor_TrackPlayer\([^;]+;','/* Baked head/torso tracking. */',text)
    for name in re.findall(r'^void (\w*(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{',text,re.M):
        text=replace_body(text,name,'    /* Sprite presentation, source actions retained. */')
    for name in re.findall(r'^s32 (\w*OverrideLimbDraw)\([^;{}]*\) \{',text,re.M):
        text=replace_body(text,name,'    return 0; /* No runtime pose. */')
    if rel.endswith('z_en_cs.c'):text=append_update(text,'EnCs_Update','    Actor_SetFocus(&this->actor, 35.0f);')
    if rel.endswith('z_en_mm.c'):text=append_update(text,'EnMm_Update','    Actor_SetFocus(&this->actor, 60.0f);')
    if rel.endswith('z_en_skj.c'):
        for name in ('EnSkj_TranslucentDL','EnSkj_OpaqueDL'):
            text=replace_body(text,name,'    return NULL; /* Alpha published in the sprite view. */')
    return text
