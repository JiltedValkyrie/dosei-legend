"""Source child shooting gallery, Bombchu bowling and treasure game."""
import re
from field_enemy_sources import replace_body
from child_route_npcs import append_update
NPC_ACTORS=('En_Syateki_Man','En_Bom_Bowl_Man','En_Takara_Man')
PROP_ACTORS=('En_Syateki_Itm','En_Bom_Bowl_Pit','En_Changer','En_G_Switch','En_Ex_Ruppy',
             'En_Ex_Item','Item_Etcetera','Bg_Bowl_Wall','En_Wall_Tubo')
ACTORS=NPC_ACTORS+PROP_ACTORS
SOURCES=[f'src/overlays/actors/ovl_{a}/z_{a.lower()}.c' for a in ACTORS]
SPRITE_OBJECTS=('object_ossan','object_bg','object_ts')
OBJECTS=SPRITE_OBJECTS+('object_yabusame_point','object_bowl','object_tsubo','object_gi_bombpouch','object_gi_hearts',
    'object_gi_bomb_2','object_gi_bomb_1','object_gi_rupy','object_gi_goddess','object_gi_dekupouch',
    'object_gi_bottle','object_gi_bottle_letter','object_gi_shield_2','object_gi_arrowcase',
    'object_gi_scale','object_gi_key','object_gi_m_arrow')
NPC_SOURCES=[('ACTOR_'+a.upper(),p) for a,p in zip(ACTORS,SOURCES) if a in NPC_ACTORS]
DRAW_SOURCES=[('ACTOR_'+a.upper(),p) for a,p in zip(ACTORS,SOURCES) if a in ('En_G_Switch','Bg_Bowl_Wall')]
SOURCE_SCENES=('syatekijyou','bowling','takaraya')


def adapt(rel,text):
    if rel in [p[:-2]+'.h' for p in SOURCES[:3]]:
        return re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];',r'Vec3s* \1;',text)
    if rel in SOURCES[:3]:
        text='#include "child_route_npc_sprite.h"\n'+text
        text=text.replace('SkelAnime_InitFlex(','OotCore_SpriteInitFlex(')
        text=re.sub(r'Actor_TrackPlayer\([^;]+;','/* No runtime head/torso pose. */',text)
        for fn in re.findall(r'^void (\w*(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{',text,re.M):
            text=replace_body(text,fn,'    /* Source action/eye clocks published by sprite view. */')
        for fn in re.findall(r'^s32 (\w*OverrideLimbDraw)\([^;{}]*\) \{',text,re.M):
            text=replace_body(text,fn,'    return 0; /* Offline source presentation. */')
    elif rel.endswith('ovl_En_Ex_Ruppy/z_en_ex_ruppy.c'):
        text=replace_body(text,'EnExRuppy_Draw','    /* Source rupee color/visibility exported to the resident item atlas. */')
    elif rel.endswith('ovl_En_G_Switch/z_en_g_switch.c'):
        text=replace_body(text,'EnGSwitch_DrawRupee','    /* Source target plus particle snapshots, no runtime rupee mesh. */')
        text=replace_body(text,'EnGSwitch_DrawEffects','    /* Source fragment state exported in EffectView. */')
    elif rel.endswith('ovl_En_Ex_Item/z_en_ex_item.c'):
        for fn in re.findall(r'^void (EnExItem_Draw\w*)\([^;{}]*\) \{',text,re.M):
            text=replace_body(text,fn,'    /* Preloaded source get-item atlas. */')
        text=append_update(text,'EnExItem_Update','    Actor_SetScale(&this->actor, this->scale);')
    elif rel.endswith('ovl_Item_Etcetera/z_item_etcetera.c'):
        text=replace_body(text,'ItemEtcetera_Draw','    /* Preloaded source get-item atlas. */')
        text=replace_body(text,'ItemEtcetera_DrawThroughLens','    /* Lens gate is preserved in the exported item view. */')
    return text
