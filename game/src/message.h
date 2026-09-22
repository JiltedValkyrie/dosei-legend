#ifndef DOSEI_MESSAGE_H
#define DOSEI_MESSAGE_H
#include <stdbool.h>
#include <stdint.h>
#include "cutscenes.h"

/*
** The cutscene message player: OoT's text boxes, driven by frames rather than
** by a talk state.
**
** This is not the NPC dialogue box (main.c dialogue_box / gameplay.c). That one
** is a conversation the player drives; this one is a message the cutscene
** shows, and it has to honour three ways of leaving a page, because the
** opening narration uses all three:
**
**   BOX_BREAK              wait for A               (most pages)
**   BOX_BREAK_DELAYED(n)   advance itself after n   ("In the vast, deep
**                                                     forest of Hyrule...")
**   FADE(n)                fade out after n         (the last narration page)
**
** A line is a list of coloured runs rather than a string, because COLOR()
** changes colour partway through a line -- "I'm Navi the fairy!" has Navi in
** red inside a blue line. See tools/oot_messages.py.
**
** Platform free: it decides what should be on screen and in what colour, and
** the renderer in main.c draws it. Stepped at the cutscene's own tick rate.
*/

typedef struct
{
    bool            active;
    unsigned short  message;        /* index into cutscene_messages */
    unsigned char   page;           /* page within that message */
    unsigned short  page_ticks;     /* ticks the current page has been up */
    /* Set for the frame the message finishes, so the caller can react once. */
    bool            finished;
    /* 0..255 while a FADE page is fading out; 255 is fully faded. The
    ** renderer dims the text with it rather than cutting it off. */
    unsigned char   fade;
}               message_state_t;

extern message_state_t  message_state;

/* Show the message with this original text id (0x109D and friends). False if
** the opening has no such message, in which case nothing is shown -- a missing
** line must be visible as silence, not as another message's text. */
bool            message_start(uint16_t text_id);

/* Stop immediately, showing nothing. */
void            message_stop(void);

/* One cutscene tick. `confirm` is the A button edge. Returns true while a
** message is still on screen. */
bool            message_step(bool confirm);

/* True while a message is on screen and the cutscene should hold. */
bool            message_is_active(void);

/* True on the tick the last page of a message ended. */
bool            message_finished(void);

/* ---- what the renderer asks -------------------------------------------- */

/* The current page's line count, and one line's runs. */
unsigned int    message_lines(void);
unsigned int    message_line_runs(unsigned int line);
/* Column the line starts at: the original's SHIFT, which is how the narration
** is centred. Zero for an ordinary left-aligned line. */
unsigned int    message_line_indent(unsigned int line);
const char     *message_run_text(unsigned int line, unsigned int run);
/* Jo text palette index for a run. */
unsigned int    message_run_colour(unsigned int line, unsigned int run);

/* Box style and screen position of the current message, from the original. */
unsigned int    message_box(void);
unsigned int    message_position(void);

/* True when the page waits for A, so the renderer can show the prompt. The
** opening's pages are UNSKIPPABLE, so this is the only way past them. */
bool            message_waits_for_button(void);

#endif
