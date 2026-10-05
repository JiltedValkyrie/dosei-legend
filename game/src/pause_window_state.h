#ifndef PAUSE_WINDOW_STATE_H
#define PAUSE_WINDOW_STATE_H
#include <stdint.h>
#include <stdbool.h>
enum { PAUSE_ITEMS, PAUSE_MAP, PAUSE_QUEST, PAUSE_EQUIPMENT, PAUSE_SAVE, PAUSE_EXTRA };
enum { PAUSE_NONE, PAUSE_MOVE, PAUSE_DENY, PAUSE_EQUIP_SWORD, PAUSE_EQUIP_SHIELD, PAUSE_WRITE_SAVE, PAUSE_LOAD_GAME, PAUSE_RETURN_TITLE, PAUSE_LABELS, PAUSE_JUMP_BINDING, PAUSE_RESET_PREFS };
enum { PAUSE_TUNIC_GREEN=32, PAUSE_TUNIC_RED, PAUSE_TUNIC_BLUE };
enum { PAUSE_EQUIP_MASTER=40, PAUSE_EQUIP_HYLIAN, PAUSE_EQUIP_BIGGORON, PAUSE_EQUIP_MIRROR };
/* Boots row cells 13..15: Kokiri, Iron, Hover (gameplay checks ownership/age). */
enum { PAUSE_BOOTS_KOKIRI=48, PAUSE_BOOTS_IRON, PAUSE_BOOTS_HOVER };
typedef struct {
    uint8_t page, cursor[6], save_choice, system_confirm;
    bool save_prompt;
} pause_window_state_t;

unsigned pause_window_step(pause_window_state_t *s, int dx, int dy,
    int turn, bool back, bool confirm, unsigned owned);
#endif
