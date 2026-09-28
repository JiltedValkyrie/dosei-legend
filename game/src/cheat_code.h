#ifndef DOSEI_CHEAT_CODE_H
#define DOSEI_CHEAT_CODE_H
#include <stdbool.h>
#include <stdint.h>
#include "kokiri_camera.h"

/*
** Human-requested cheat (not in the original): Up Up Down Down Left Right
** Left Right A Start toggles enemy dots on the minimap. Fed the normalized
** CAMERA_* pad snapshot once per VBlank; only new presses count, one button
** per press. Any other press breaks the sequence. Platform free.
*/
typedef struct { uint16_t previous; uint8_t position; } cheat_code_t;

static const uint16_t cheat_code_keys[10] = {
    CAMERA_UP, CAMERA_UP, CAMERA_DOWN, CAMERA_DOWN, CAMERA_LEFT, CAMERA_RIGHT,
    CAMERA_LEFT, CAMERA_RIGHT, CAMERA_A, CAMERA_START
};

/* True on the press that completes the code. */
static inline bool cheat_code_sample(cheat_code_t *c, uint16_t held)
{
    uint16_t pressed = (uint16_t)(held & ~c->previous);
    c->previous = held;
    if (!pressed)
        return false;
    if (pressed == cheat_code_keys[c->position]) {
        if (++c->position == 10) {
            c->position = 0;
            return true;
        }
    } else if (!(c->position == 2 && pressed == CAMERA_UP)) {
        /* Up Up Up still counts as the first two Ups. */
        c->position = pressed == cheat_code_keys[0] ? 1 : 0;
    }
    return false;
}

#endif
