"""Child route source adaptations (docs/CHILD_ROUTE_DODONGO_PLAN.md).

Actors are listed in scene_pack_actors.SOURCE_ACTORS and drawn through the
generic shim (oot_core_import.GENERIC_DRAW_SOURCES). Only Saturn-required
substitutions live here; source actions, flags and rewards stay intact.
"""
from field_enemy_sources import replace_once

BREAKWALL = 'src/overlays/actors/ovl_Bg_Breakwall/z_bg_breakwall.c'


def adapt(rel, text):
    if rel == BREAKWALL:
        # Dodongo's Cavern entrance (Death Mountain Trail): the opening
        # cutscene halts Player until the complete scene-local source script
        # ends. Resolve its stable id through the core, retaining the original
        # event flag, source Player halt and chime.
        text = replace_once(
            text,
            '            Cutscene_SetScript(play, gDcOpeningCs);\n'
            '            gSaveContext.cutsceneTrigger = 1;\n'
            '            SFX_PLAY_CENTERED(NA_SE_SY_CORRECT_CHIME);\n'
            '            Player_SetCsActionWithHaltedActors(play, NULL, PLAYER_CSACTION_49);\n',
            '            OotCore_RouteCutscene(play, OOT_ROUTE_CS_DC_OPENING);\n'
            '            SFX_PLAY_CENTERED(NA_SE_SY_CORRECT_CHIME);\n')
        text = '#include "oot_route_cutscene.h"\n' + text
    return text
