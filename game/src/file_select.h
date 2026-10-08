#ifndef DOSEI_FILE_SELECT_H
#define DOSEI_FILE_SELECT_H
#include <stdbool.h>
#include <stdint.h>
#include "save_file.h"

/*
** The N64-style file select: three files, pick one to start or continue, or
** erase one.
**
** Platform free. It talks to storage only through save_device.h, so the host
** tests link a fake device and drive the real screen logic -- including the
** cases a real cartridge makes awkward to produce, like a damaged slot or a
** device that refuses to write.
**
** Not modelled, and not faked either: the original's COPY option. There is no
** second-slot picker here, and file_select_copy_supported() says so, so the
** renderer can leave the row out rather than draw a button that does nothing.
*/

/* Cursor rows: three files, erase, then the debug level selector. */
#define FILE_SELECT_ROW_ERASE   SAVE_FILE_SLOTS
#define FILE_SELECT_ROW_DEBUG   (SAVE_FILE_SLOTS + 1)
#define FILE_SELECT_ROWS        (SAVE_FILE_SLOTS + 2)

typedef enum
{
    FILE_SELECT_CHOOSING = 0,   /* picking a file to play */
    FILE_SELECT_OPEN_CONFIRM,   /* "Open this file?" -- Yes / Quit */
    FILE_SELECT_ERASE_PICK,     /* picking a file to erase */
    FILE_SELECT_ERASE_CONFIRM   /* "are you sure" on one file */
}               file_select_mode;

/* Rows on the "Open this file?" panel, in the original's order. */
typedef enum
{
    FILE_SELECT_OPEN_YES = 0,
    FILE_SELECT_OPEN_QUIT,
    FILE_SELECT_OPEN_ROWS
}               file_select_open_row;

typedef enum
{
    FILE_SELECT_NONE = 0,       /* still on the screen */
    FILE_SELECT_START_NEW,      /* begin a new game in `slot` */
    FILE_SELECT_START_LOAD,     /* continue the file in `slot` */
    FILE_SELECT_BACK,           /* cancelled: return to the title */
    FILE_SELECT_DEBUG
}               file_select_result;

typedef struct
{
    bool        up, down;       /* pressed this step, edge already latched */
    bool        confirm;        /* A */
    bool        cancel;         /* B */
}               file_select_input;

typedef struct
{
    file_select_mode    mode;
    uint8_t             cursor;         /* 0..FILE_SELECT_ROWS-1 */
    /* Which button the "Open this file?" panel is on. Separate from `cursor`
    ** so backing out of the panel returns to the file the player was on
    ** rather than to whichever button they left highlighted. */
    uint8_t             open_row;
    uint8_t             erase_slot;     /* slot awaiting confirmation */
    file_select_result  result;
    uint8_t             slot;           /* which slot `result` refers to */
    /* Cached so the renderer does not re-read the device every frame, and so a
    ** damaged slot reports the same reason every frame instead of flickering. */
    save_file_summary   summary[SAVE_FILE_SLOTS];
    save_file_status    status[SAVE_FILE_SLOTS];
    /* Set when a device operation failed, for a message the player can act on
    ** rather than a silent no-op. Cleared on the next input. */
    bool                device_failed;
}               file_select_t;

extern file_select_t    file_select;

/* Enter the screen: reset the cursor and re-read all three slot summaries. */
void                file_select_open(void);

/* One step. Returns the same value as file_select.result. */
file_select_result  file_select_step(const file_select_input *in);

/* Re-read the summaries from the device. Called by open() and after an erase. */
void                file_select_refresh(void);

/* Row text helpers for the renderer. Never NULL. */
const char         *file_select_row_label(unsigned int row);
/* A short description of a file row: hearts and rupees, "NEW FILE", or why the
** slot could not be read. */
const char         *file_select_row_detail(unsigned int row);
const char         *file_select_row_location(unsigned int row);

/* Button label on the "Open this file?" panel. Never NULL. */
const char         *file_select_open_label(unsigned int row);

/* Which slot the "Open this file?" panel is asking about. Only meaningful in
** FILE_SELECT_OPEN_CONFIRM; the renderer shows that file's summary. */
unsigned int        file_select_open_slot(void);

/* False: the original's COPY option is not implemented. Exposed so the screen
** does not advertise it. */
bool                file_select_copy_supported(void);

#endif
