"""Source NPC adapters for the child route through King Dodongo.

Only presentation changes here: original action, dialogue, inventory, reward,
cucco-count and gate state machines remain in the decomp sources. Character
objects contain clock headers and sprite identities, never runtime poses.
"""
import re

from field_enemy_sources import replace_body, replace_once

ACTORS = ('En_Go2', 'En_Du', 'En_Heishi2', 'En_Daiku_Kakariko', 'En_Niw_Lady', 'En_Sa')
SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in ACTORS]
OBJECTS = ('object_oF1d_map', 'object_du', 'object_sd', 'object_daiku',
           'object_ane', 'object_os_anime', 'object_sa')
NPC_SOURCES = [('ACTOR_' + name.upper(), source) for name, source in zip(ACTORS, SOURCES)]
# Guard actions write directly to these two source gates. They retain their
# original dynamic collision, saved open flags and mesh draws (not characters).
GATE_ACTORS = ('Bg_Gate_Shutter', 'Bg_Spot15_Saku')
GATE_SOURCES = [f'src/overlays/actors/ovl_{name}/z_{name.lower()}.c' for name in GATE_ACTORS]
GATE_DRAW_SOURCES = [('ACTOR_' + name.upper(), source) for name, source in zip(GATE_ACTORS, GATE_SOURCES)]
GATE_OBJECTS = ('object_spot01_matoyab', 'object_spot15_obj')

# Cucco lady's skeleton and animation headers are in different objects. The
# runtime key still uses the real animation symbol; the offline reader needs
# its own object bytes instead of interpreting the same offset in object_ane.
ANIMATION_OBJECTS = {'object_ane': 'object_os_anime'}

# Source Draw switches from the Goron skeleton to these whole-body lists.
# Keep one archive/skeleton identity, with the list symbol as animation key.
STATIC_CLIPS = (
    ('object_oF1d_map', 'gGoronSkel', 'gGoronDL_00BD80', ('gGoronDL_00BD80',)),
    ('object_oF1d_map', 'gGoronSkel', 'gGoronDL_00C140', ('gGoronDL_00C140',)),
    ('object_sd', 'gEnHeishiSkel', 'gHeishiKingGuardDL', ('gHeishiKingGuardDL',)),
    ('object_dekunuts', 'gDekuNutsSkel', 'gDekuNutsFlowerDL', ('gDekuNutsFlowerDL',)),
)


def append_update(text, name, body):
    marker = f'void {name}(Actor* thisx, PlayState* play) {{'
    if text.count(marker) != 1:
        raise ValueError(f'{name}: source Update moved')
    end = text.index('\n}', text.index(marker))
    return text[:end] + '\n' + body + text[end:]


def adapt(rel, text):
    if rel in [path[:-2] + '.h' for path in SOURCES]:
        text = re.sub(r'Vec3s (jointTable|morphTable)\[[^\]]+\];', r'Vec3s* \1;', text)
        if rel.endswith('z_en_go2.h'):
            text = replace_once(text, '} EnGo2;', '    u8 spriteDrawMode; /* 0 standing, 1 curled, 2 rolling */\n} EnGo2;')
        return text
    if rel not in SOURCES:
        return text
    text = '#include "child_route_npc_sprite.h"\n' + text
    text = text.replace('SkelAnime_InitFlex(', 'OotCore_SpriteInitFlex(')
    text = text.replace('SkelAnime_Init(', 'OotCore_SpriteInit(')
    text = text.replace('Npc_TrackPoint(', 'ChildRouteSprite_TrackBody(')
    # Draw contains no surviving actions except Go2's effects clock/focus,
    # which are moved to Update below. Header pose arrays become null pointers.
    for name in re.findall(r'^void ((?:EnGo2|EnDu|EnHeishi2|EnDaikuKakariko|EnNiwLady|EnSa)_(?:Draw\w*|PostLimbDraw))\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    /* Offline sprite; source actions run in Update. */')
    for name in re.findall(r'^s32 ((?:EnGo2|EnDu|EnHeishi2|EnDaikuKakariko|EnNiwLady|EnSa)_(?:OverrideLimbDraw|Draw\w*))\([^;{}]*\) \{', text, re.M):
        text = replace_body(text, name, '    return 0; /* No runtime character pose. */')

    if rel.endswith('z_en_go2.c'):
        text = replace_once(text,
            '    if (this->unk_211 == true) {\n        Actor_UpdateFidgetTables(play, this->fidgetTableY, this->fidgetTableZ, 18);\n    }',
            '    /* Fidget tables fed only the removed limb callback. */')
        text = append_update(text, 'EnGo2_Update', '''    EnGo2_UpdateEffects(this);
    this->spriteDrawMode = 0;
    if (this->actionFunc == EnGo2_CurledUp && this->skelAnime.playSpeed == 0.0f &&
        this->skelAnime.curFrame == 0.0f) this->spriteDrawMode = 1;
    else if (this->actionFunc == EnGo2_SlowRolling || this->actionFunc == EnGo2_ReverseRolling ||
             this->actionFunc == EnGo2_ContinueRolling) this->spriteDrawMode = 2;
    Actor_SetFocus(&this->actor, this->spriteDrawMode ? 0 : this->collider.dim.height);''')
    elif rel.endswith('z_en_du.c'):
        text = append_update(text, 'EnDu_Update', '    Actor_SetFocus(&this->actor, 60.0f);')
    elif rel.endswith('z_en_heishi2.c'):
        text = replace_once(text,
            '        Actor_TrackPlayer(play, &this->actor, &this->unk_260, &this->unk_26C, this->actor.focus.pos);',
            '        /* Head/torso tracking only fed the removed draw callbacks. */')
        text = replace_once(text,
            '        this->actor.draw = EnHeishi2_DrawKingGuard;',
            '''        OotCore_SpriteInit(play, &this->skelAnime, &gEnHeishiSkel,
                           &gEnHeishiIdleAnim, NULL, NULL, 17);
        this->actor.draw = EnHeishi2_DrawKingGuard;''')
    elif rel.endswith('z_en_daiku_kakariko.c'):
        # Source whole-body turning still runs. Head-only changes have no
        # action consumers; the actor's flags and path timers remain intact.
        text = replace_once(text,
            '    Math_SmoothStepToS(&this->neckAngle.x, this->neckAngleTarget.x, 1, 1820, 0);',
            '    Actor_SetFocus(&this->actor, 60.0f);')
    elif rel.endswith('z_en_sa.c'):
        text = append_update(text, 'EnSa_Update', '    Actor_SetFocus(&this->actor, 40.0f);')
    else:
        text = replace_once(text,
            '    this->headRot = this->interactInfo.headRot;\n'
            '    this->torsoRot = this->interactInfo.torsoRot;\n'
            '    if (this->unk_276 == 0) {\n'
            '        Math_SmoothStepToS(&this->headRot.y, 0, 5, 3000, 0);\n    }',
            '    /* Body turning retained; no head/torso interpolation. */')
    return text
