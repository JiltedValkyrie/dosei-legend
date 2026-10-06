#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
#include "game_mode.h"

/*
** The transition table, one bit per reachable mode.
**
** Every edge here is an edge the game actually takes; nothing is allowed "just
** in case". The opening chain is the reason several of them exist:
**
**   TITLE -> FILE_SELECT          Start on the title
**   FILE_SELECT -> TITLE          B backs out
**   FILE_SELECT -> LOADING        a file was chosen
**   LOADING -> CUTSCENE           a new file opens the intro, not the world
**   LOADING -> PLAY               a loaded file resumes where it was saved
**   LOADING -> FILE_SELECT        the disc read failed; do not strand the
**                                 player in a mode with no scene behind it
**   CUTSCENE -> LOADING           CS_DESTINATION hands off to the next scene,
**                                 which is how the four intro cutscenes chain
**   CUTSCENE -> PLAY              CS_MISC_STOP_CUTSCENE ends the last one
**   PLAY -> LOADING               Link walked through a door
**   PLAY -> CUTSCENE              a scripted scene triggers in the world
**   PLAY -> PAUSE / DIALOGUE      Start, and talking
**   PLAY -> GAME_OVER             out of hearts
**   GAME_OVER -> FILE_SELECT      continue
**   GAME_OVER -> TITLE            give up
**
** PAUSE -> LOADING and DIALOGUE -> LOADING are deliberately absent: neither
** screen loads a scene today, and adding the edge before the behaviour exists
** would let a bug through silently.
*/
#define M(mode) (1u << (mode))

static const unsigned int   allowed[GAME_MODE_COUNT] =
{
    [GAME_MODE_TITLE]       = M(GAME_MODE_FILE_SELECT),
    [GAME_MODE_FILE_SELECT] = M(GAME_MODE_TITLE) | M(GAME_MODE_LOADING),
    [GAME_MODE_LOADING]     = M(GAME_MODE_PLAY) | M(GAME_MODE_CUTSCENE) |
                              M(GAME_MODE_FILE_SELECT),
    [GAME_MODE_PLAY]        = M(GAME_MODE_PAUSE) | M(GAME_MODE_DIALOGUE) |
                              M(GAME_MODE_CUTSCENE) | M(GAME_MODE_LOADING) |
                              M(GAME_MODE_GAME_OVER),
    [GAME_MODE_PAUSE]       = M(GAME_MODE_PLAY) | M(GAME_MODE_TITLE) | M(GAME_MODE_FILE_SELECT),
    [GAME_MODE_DIALOGUE]    = M(GAME_MODE_PLAY),
    [GAME_MODE_CUTSCENE]    = M(GAME_MODE_PLAY) | M(GAME_MODE_LOADING),
    [GAME_MODE_GAME_OVER]   = M(GAME_MODE_FILE_SELECT) | M(GAME_MODE_TITLE) |
                              M(GAME_MODE_LOADING)   /* Continue: respawn */
};

static const char *const    names[GAME_MODE_COUNT] =
{
    [GAME_MODE_TITLE]       = "TITLE",
    [GAME_MODE_FILE_SELECT] = "FILE_SELECT",
    [GAME_MODE_LOADING]     = "LOADING",
    [GAME_MODE_PLAY]        = "PLAY",
    [GAME_MODE_PAUSE]       = "PAUSE",
    [GAME_MODE_DIALOGUE]    = "DIALOGUE",
    [GAME_MODE_CUTSCENE]    = "CUTSCENE",
    [GAME_MODE_GAME_OVER]   = "GAME_OVER"
};

static game_mode_t          current = GAME_MODE_TITLE;

game_mode_t         game_mode(void)
{
    return (current);
}

bool                game_mode_can(game_mode_t to)
{
    if (to < 0 || to >= GAME_MODE_COUNT)
        return (false);
    return ((allowed[current] & M(to)) != 0);
}

bool                game_mode_set(game_mode_t to)
{
    if (!game_mode_can(to))
        return (false);
    current = to;
    return (true);
}

void                game_mode_reset(void)
{
    current = GAME_MODE_TITLE;
}

const char         *game_mode_name(game_mode_t mode)
{
    if (mode < 0 || mode >= GAME_MODE_COUNT)
        return ("?");
    return (names[mode]);
}

bool                game_mode_owns_pad(void)
{
    /* The title takes only Start, which recomp.c reads as a raw edge rather than
    ** through the menu mapping, so it is not listed here. A cutscene takes only
    ** A to advance a text box and is handled the same way. */
    return (current == GAME_MODE_FILE_SELECT ||
            current == GAME_MODE_PAUSE ||
            current == GAME_MODE_DIALOGUE);
}

bool                game_mode_world_steps(void)
{
    /* DIALOGUE keeps the world running underneath, exactly as the original
    ** does -- grass still sways and the camera still eases while a Kokiri
    ** talks. PAUSE and CUTSCENE stop it. */
    return (current == GAME_MODE_PLAY || current == GAME_MODE_DIALOGUE);
}
