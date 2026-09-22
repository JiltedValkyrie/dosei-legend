#ifndef DOSEI_GAME_MODE_H
#define DOSEI_GAME_MODE_H
#include <stdbool.h>

/*
** Which screen the game is on, and which screen it is allowed to reach next.
**
** This replaces the pair of booleans demo.c used to carry (`title_visible`,
** `file_select_visible`). Two booleans describe four states, three of which
** were meaningful and one of which -- both set -- was nonsense that nothing
** prevented. The opening cutscene adds enough states (a cutscene that owns the
** camera, a scene load that happens mid-cutscene) that an implicit encoding
** stops being readable at all.
**
** The modes are OoT's, named after what the player sees, per the progression
** plan (docs/OOT_PROGRESSION_PLAN.md).
**
** Platform free on purpose: it names no Jo or SGL type, so the host tests drive
** the real table rather than a copy of it.
*/

typedef enum
{
    GAME_MODE_TITLE = 0,    /* attract flight, PRESS START */
    GAME_MODE_FILE_SELECT,  /* three files, erase, "Open this file?" */
    GAME_MODE_LOADING,      /* a scene is being read off the disc */
    GAME_MODE_PLAY,         /* ordinary gameplay */
    GAME_MODE_PAUSE,        /* the inventory screen */
    GAME_MODE_DIALOGUE,     /* a text box owns the pad */
    GAME_MODE_CUTSCENE,     /* a baked cutscene owns camera, actors and text */
    GAME_MODE_GAME_OVER,
    GAME_MODE_COUNT
}               game_mode_t;

/* The current mode. Starts at GAME_MODE_TITLE. */
game_mode_t     game_mode(void);

/* True when `to` may be reached from the current mode. A mode is never
** reachable from itself: re-entering is a caller bug, not a transition. */
bool            game_mode_can(game_mode_t to);

/* Take the transition. Returns false and changes nothing when the transition
** is not allowed, so a wrong call is visible in a test rather than silently
** putting the game somewhere it cannot draw. */
bool            game_mode_set(game_mode_t to);

/* Back to the title. The one unconditional move, for a reset. */
void            game_mode_reset(void);

/* Short name, for diagnostics and test failure messages. Never NULL. */
const char     *game_mode_name(game_mode_t mode);

/*
** Two questions the rest of the game asks constantly. They are derived from
** the mode rather than tracked separately, because a second source of truth is
** exactly the bug this module exists to remove.
*/

/* True when a menu or text box owns the pad, so the D-pad moves a cursor, A
** confirms and B cancels -- and B must not also toggle walk/run. */
bool            game_mode_owns_pad(void);

/* True when the world advances: Link moves, gravity runs, actors step. False
** on the title, in menus, and during a cutscene, whose actors are driven from
** baked cues instead. */
bool            game_mode_world_steps(void);

#endif
