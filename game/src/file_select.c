#pragma GCC optimize("Os") /* cold menu/save/script code: size over speed (work RAM) */
/*
** File select screen logic. Contract and what is deliberately absent are in
** file_select.h.
*/

#include "file_select.h"
#include "save_device.h"
#include "save_state.h"

file_select_t       file_select;

/* Row detail text is rebuilt into this on request. No stdio on the SH-2 hot
** path, so the numbers are formatted by hand. */
static char         detail[40];

static char        *put_text(char *at, const char *text)
{
    while (*text)
        *at++ = *text++;
    return (at);
}

static char        *put_number(char *at, unsigned int value)
{
    char            digits[6];
    unsigned int    count = 0;

    if (value == 0) {
        *at++ = '0';
        return (at);
    }
    while (value && count < sizeof(digits)) {
        digits[count++] = (char)('0' + value % 10);
        value /= 10;
    }
    while (count)
        *at++ = digits[--count];
    return (at);
}

void                file_select_refresh(void)
{
    unsigned int    slot;

    for (slot = 0; slot < SAVE_FILE_SLOTS; ++slot)
        file_select.status[slot] =
            save_device_summary(slot, &file_select.summary[slot]);
}

void                file_select_open(void)
{
    file_select.mode = FILE_SELECT_CHOOSING;
    file_select.cursor = 0;
    file_select.open_row = FILE_SELECT_OPEN_YES;
    file_select.erase_slot = 0;
    file_select.result = FILE_SELECT_NONE;
    file_select.slot = 0;
    file_select.device_failed = false;
    file_select_refresh();
}

static void         move_cursor(int delta)
{
    int             rows = FILE_SELECT_ROWS;
    int             cursor;

    /* The open panel has its own two-button cursor, kept apart from the file
    ** cursor so leaving the panel returns to the file the player was on. */
    if (file_select.mode == FILE_SELECT_OPEN_CONFIRM) {
        cursor = (int)file_select.open_row + delta;
        if (cursor < 0)
            cursor = FILE_SELECT_OPEN_ROWS - 1;
        else if (cursor >= FILE_SELECT_OPEN_ROWS)
            cursor = 0;
        file_select.open_row = (uint8_t)cursor;
        return;
    }
    /* While picking a file to erase there is no erase row to land on: the row
    ** is what got us here, and B is how you leave. */
    if (file_select.mode == FILE_SELECT_ERASE_PICK)
        rows = SAVE_FILE_SLOTS;
    cursor = (int)file_select.cursor + delta;
    if (cursor < 0)
        cursor = rows - 1;
    else if (cursor >= rows)
        cursor = 0;
    file_select.cursor = (uint8_t)cursor;
}

/* A file can be played if it is either empty (start new) or readable (load).
** A slot that exists but cannot be read is NOT offered: starting a new game
** over it would destroy a save the player may still want to recover, and
** loading it is impossible. Erasing it deliberately is the way past. */
static bool         row_is_playable(unsigned int slot)
{
    return (file_select.status[slot] == SAVE_FILE_OK ||
            file_select.status[slot] == SAVE_FILE_EMPTY);
}

static void         confirm_choosing(void)
{
    unsigned int    slot = file_select.cursor;

    if (slot == FILE_SELECT_ROW_DEBUG) {
        file_select.result = FILE_SELECT_DEBUG;
        return;
    }
    if (slot == FILE_SELECT_ROW_ERASE) {
        file_select.mode = FILE_SELECT_ERASE_PICK;
        file_select.cursor = 0;
        return;
    }
    if (!row_is_playable(slot)) {
        /* Say nothing happened, rather than quietly overwriting. */
        file_select.device_failed = true;
        return;
    }
    /* Picking a file does not open it. The original asks "Open this file?"
    ** first, so nothing is written and no save is loaded until Yes. */
    file_select.slot = (uint8_t)slot;
    file_select.open_row = FILE_SELECT_OPEN_YES;
    file_select.mode = FILE_SELECT_OPEN_CONFIRM;
}

/* Yes or Quit on the "Open this file?" panel. This is where a new file is
** actually created and an existing one actually read. */
static void         confirm_open(void)
{
    unsigned int    slot = file_select.slot;

    if (file_select.open_row == FILE_SELECT_OPEN_QUIT) {
        file_select.mode = FILE_SELECT_CHOOSING;
        return;
    }
    if (file_select.status[slot] == SAVE_FILE_EMPTY) {
        /* save_new_game() decides where a new file begins -- Link's house,
        ** spawn 0, the bed, as in the original. This used to override it to
        ** the forest, from before the house existed, which made every new game
        ** start outside. Do not set the scene here. */
        save_new_game();
        file_select.result = FILE_SELECT_START_NEW;
        return;
    }
    if (save_device_read(slot) != SAVE_FILE_OK) {
        /* It read fine for the summary and not now: report it and go back to
        ** the list instead of dropping the player into an unloaded world. */
        file_select.device_failed = true;
        file_select.mode = FILE_SELECT_CHOOSING;
        file_select_refresh();
        return;
    }
    file_select.result = FILE_SELECT_START_LOAD;
}

static void         confirm_erase_pick(void)
{
    if (file_select.status[file_select.cursor] == SAVE_FILE_EMPTY)
        return;                 /* nothing to erase; not an error */
    file_select.erase_slot = file_select.cursor;
    file_select.mode = FILE_SELECT_ERASE_CONFIRM;
}

static void         confirm_erase(void)
{
    if (!save_device_erase(file_select.erase_slot))
        file_select.device_failed = true;
    file_select_refresh();
    file_select.mode = FILE_SELECT_CHOOSING;
    file_select.cursor = file_select.erase_slot;
}

file_select_result  file_select_step(const file_select_input *in)
{
    if (!in || file_select.result != FILE_SELECT_NONE)
        return (file_select.result);

    if (in->up || in->down || in->confirm || in->cancel)
        file_select.device_failed = false;

    if (in->up)
        move_cursor(-1);
    if (in->down)
        move_cursor(1);

    if (in->cancel) {
        switch (file_select.mode) {
            case FILE_SELECT_OPEN_CONFIRM:
                /* B is Quit. Back to the list, nothing opened. */
                file_select.mode = FILE_SELECT_CHOOSING;
                break;
            case FILE_SELECT_ERASE_CONFIRM:
                file_select.mode = FILE_SELECT_ERASE_PICK;
                break;
            case FILE_SELECT_ERASE_PICK:
                file_select.mode = FILE_SELECT_CHOOSING;
                file_select.cursor = FILE_SELECT_ROW_ERASE;
                break;
            default:
                file_select.result = FILE_SELECT_BACK;
                break;
        }
        return (file_select.result);
    }

    if (in->confirm) {
        switch (file_select.mode) {
            case FILE_SELECT_CHOOSING:      confirm_choosing(); break;
            case FILE_SELECT_OPEN_CONFIRM:  confirm_open(); break;
            case FILE_SELECT_ERASE_PICK:    confirm_erase_pick(); break;
            default:                        confirm_erase(); break;
        }
    }
    return (file_select.result);
}

const char         *file_select_row_label(unsigned int row)
{
    switch (row) {
        case 0:  return "FILE 1";
        case 1:  return "FILE 2";
        case 2:  return "FILE 3";
        case FILE_SELECT_ROW_ERASE: return "ERASE FILE";
        case FILE_SELECT_ROW_DEBUG: return "Level Select (Debug Mode)";
        default: return "";
    }
}

const char         *file_select_row_detail(unsigned int row)
{
    const save_file_summary *summary;
    char                    *at = detail;

    if (row >= SAVE_FILE_SLOTS)
        return ("");
    if (file_select.status[row] != SAVE_FILE_OK)
        return (save_file_status_text(file_select.status[row]));
    summary = &file_select.summary[row];
    at = put_number(at, summary->hearts_full);
    at = put_text(at, "/");
    at = put_number(at, summary->hearts);
    at = put_text(at, " HEARTS  ");
    at = put_number(at, summary->rupees);
    at = put_text(at, " RUPEES");
    if (summary->has_emerald)
        at = put_text(at, "  EMERALD");
    *at = '\0';
    return (detail);
}
const char *file_select_row_location(unsigned int row)
{
    return row<SAVE_FILE_SLOTS && file_select.status[row]==SAVE_FILE_OK ?
        save_scene_name(file_select.summary[row].scene_id):"";
}

const char         *file_select_open_label(unsigned int row)
{
    switch (row) {
        case FILE_SELECT_OPEN_YES:  return "YES";
        case FILE_SELECT_OPEN_QUIT: return "QUIT";
        default:                    return "";
    }
}

unsigned int        file_select_open_slot(void)
{
    return (file_select.slot);
}

bool                file_select_copy_supported(void)
{
    return (false);
}

/*
** END OF FILE
*/
