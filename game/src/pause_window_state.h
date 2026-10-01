#ifndef PAUSE_WINDOW_STATE_H
#define PAUSE_WINDOW_STATE_H
#include <stdint.h>
#include <stdbool.h>
enum { PAUSE_ITEMS, PAUSE_MAP, PAUSE_QUEST, PAUSE_EQUIPMENT, PAUSE_SAVE, PAUSE_EXTRA };
enum { PAUSE_NONE, PAUSE_MOVE, PAUSE_DENY, PAUSE_EQUIP_SWORD, PAUSE_EQUIP_SHIELD, PAUSE_WRITE_SAVE, PAUSE_LOAD_GAME, PAUSE_RETURN_TITLE, PAUSE_LABELS, PAUSE_JUMP_BINDING, PAUSE_RESET_PREFS };
enum { PAUSE_TUNIC_GREEN=32, PAUSE_TUNIC_RED, PAUSE_TUNIC_BLUE };
typedef struct {
    uint8_t page, cursor[6], save_choice, system_confirm;
    bool save_prompt;
} pause_window_state_t;

unsigned pause_window_step(pause_window_state_t *s, int dx, int dy,
    int turn, bool back, bool confirm, unsigned owned);
#endif
