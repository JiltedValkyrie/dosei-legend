/*
 * The Player frame bank decoder (PlayerFrameBank_Decode) in the core
 * (PLAYER_SOURCE=1). Same source as the host round-trip test, so the game
 * decodes exactly what oot-core/tests checks against the Python reference.
 */
#include <stdint.h>
/* The decomp's libc stdint.h has no fixed-width types. */
typedef unsigned char uint8_t;
typedef signed short int16_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef signed int int32_t;

extern "C" {
#include "../tests/player_frame_decode.c"
}

/* z_player.c reads gEntranceTable only for the title card, and only when the
 * scene has a title file (play->loadedScene has none on Saturn): one entry,
 * defined here, away from scene.h's ENTR_MAX declaration. */
struct OotEntranceStub {
    signed char sceneId, spawn;
    unsigned short field;
};
OotEntranceStub gEntranceTable[1];
