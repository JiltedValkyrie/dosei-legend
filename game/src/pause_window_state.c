#pragma GCC optimize("Os") /* small logic: size over speed (work RAM) */
#include "pause_window_state.h"
unsigned pause_window_step(pause_window_state_t *s, int dx, int dy,
                                         int turn, bool back, bool confirm, unsigned owned)
{
    int column, row, width, height;
    if (back) {
        if (s->system_confirm) s->system_confirm = 0;
        else if (s->save_prompt) s->save_prompt = false;
        else if (s->page == PAUSE_EXTRA) s->page = PAUSE_EQUIPMENT;
        else { s->save_prompt = true; s->save_choice = 0; }
        return PAUSE_MOVE;
    }
    if (s->system_confirm) {
        if (dx || dy) { s->save_choice ^= 1; return PAUSE_MOVE; }
        if (confirm) {
            unsigned result = s->system_confirm == 1 ? PAUSE_LOAD_GAME : PAUSE_RETURN_TITLE;
            s->system_confirm = 0;
            return s->save_choice ? PAUSE_MOVE : result;
        }
        return PAUSE_NONE;
    }
    if (s->save_prompt) {
        if (dx || dy) { s->save_choice ^= 1; return PAUSE_MOVE; }
        if (confirm) {
            if (s->save_choice) { s->save_prompt = false; return PAUSE_MOVE; }
            return PAUSE_WRITE_SAVE;
        }
        return PAUSE_NONE;
    }
    if (turn) {
        int page = s->page == PAUSE_EXTRA ? 4 : s->page;
        page = (page + (turn > 0 ? 1 : 4)) % 5;
        s->page = page == 4 ? PAUSE_EXTRA : page;
        return PAUSE_MOVE;
    }
    if (s->page == PAUSE_EXTRA) {
        if (dy || dx) {
            int step = dy ? dy : dx;
            s->cursor[PAUSE_EXTRA] = (s->cursor[PAUSE_EXTRA] + step + 6) % 6;
            return PAUSE_MOVE;
        }
        if (confirm) {
            if (s->cursor[PAUSE_EXTRA] >= 3) return PAUSE_LABELS + s->cursor[PAUSE_EXTRA] - 3;
            if (!s->cursor[PAUSE_EXTRA]) { s->save_prompt = true; s->save_choice = 0; }
            else { s->system_confirm = s->cursor[PAUSE_EXTRA]; s->save_choice = 1; }
            return PAUSE_MOVE;
        }
        return PAUSE_NONE;
    }
    if (s->page == PAUSE_MAP) return confirm ? PAUSE_DENY : PAUSE_NONE;
    if (s->page == PAUSE_QUEST) {
        if (dx || dy) {
            s->cursor[PAUSE_QUEST]=(s->cursor[PAUSE_QUEST]+(dx ? dx : dy)+24)%24;
            return PAUSE_MOVE;
        }
        return confirm ? PAUSE_DENY : PAUSE_NONE;
    }
    width = s->page == PAUSE_ITEMS ? 6 : s->page == PAUSE_EQUIPMENT ? 4 : 6;
    height = s->page == PAUSE_MAP ? 2 : 4;
    if (dx || dy) {
        column = s->cursor[s->page] % width;
        row = s->cursor[s->page] / width;
        column = (column + dx + width) % width;
        row = (row + dy + height) % height;
        s->cursor[s->page] = (uint8_t)(row * width + column);
        return PAUSE_MOVE;
    }
    if (!confirm) return PAUSE_NONE;
    if (s->page == PAUSE_EQUIPMENT) {
        if(s->cursor[s->page]>=9 && s->cursor[s->page]<=11)
            return PAUSE_TUNIC_GREEN+s->cursor[s->page]-9;
        if (s->cursor[s->page] == 1 && (owned & 1)) return PAUSE_EQUIP_SWORD;
        if (s->cursor[s->page] == 2 && (owned & 1)) return PAUSE_EQUIP_MASTER;
        if (s->cursor[s->page] == 5 && (owned & 2)) return PAUSE_EQUIP_SHIELD;
        if (s->cursor[s->page] == 6 && (owned & 2)) return PAUSE_EQUIP_HYLIAN;
        if (s->cursor[s->page] == 3 && (owned & 1)) return PAUSE_EQUIP_BIGGORON;
        if (s->cursor[s->page] == 7 && (owned & 2)) return PAUSE_EQUIP_MIRROR;
        if (s->cursor[s->page] >= 13) return PAUSE_BOOTS_KOKIRI + s->cursor[s->page] - 13;
    }
    return PAUSE_DENY;
}
