#ifndef DOSEI_SCENE_ROOM_TYPE_H
#define DOSEI_SCENE_ROOM_TYPE_H
#include <stdbool.h>
#include "save_state.h"

/*
** curRoom.type == ROOM_TYPE_INDOORS, from the ntsc-1.2 *_room_N.inc.c
** SCENE_CMD_ROOM_BEHAVIOR of every room in each scene: the five Kokiri
** houses and the Kokiri shop. The forest, Lost Woods, Hyrule Field, Deku Tree
** (ROOM_TYPE_DUNGEON) and Gohma's room (ROOM_TYPE_BOSS) are not indoors.
** Player_ActionHandler_10 (Z + A roll/jump slash/sidehop/backflip) is refused
** indoors.
*/
static inline bool scene_room_indoors(unsigned int scene)
{
    switch (scene) {
    case SAVE_SCENE_KOKIRI_SHOP:
    case SAVE_SCENE_LINKS_HOUSE:
    case SAVE_SCENE_KNOW_IT_ALL_HOUSE:
    case SAVE_SCENE_TWINS_HOUSE:
    case SAVE_SCENE_MIDOS_HOUSE:
    case SAVE_SCENE_SARIAS_HOUSE:
        return true;
    default:
        return false;
    }
}

#endif
