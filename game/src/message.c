/*
** Cutscene message player. Contract in message.h.
*/

#include "message.h"

message_state_t     message_state;

/* How long a FADE page takes to dim once its delay has run out. The original
** fades the whole screen over the following frames; here the text dims over
** this many cutscene ticks, so the line is gone by the time the shot cuts. */
#define MESSAGE_FADE_TICKS  10

static const cutscene_message_t *current(void)
{
    if (!message_state.active)
        return ((const cutscene_message_t *)0);
    return (&cutscene_messages[message_state.message]);
}

static const cutscene_page_t *current_page(void)
{
    const cutscene_message_t *message = current();

    if (!message || message_state.page >= message->pages)
        return ((const cutscene_page_t *)0);
    return (&cutscene_pages[message->first_page + message_state.page]);
}

bool                message_start(uint16_t text_id)
{
    unsigned int    i;

    for (i = 0; i < CUTSCENE_MESSAGE_COUNT; ++i) {
        if (cutscene_messages[i].id != text_id)
            continue;
        message_state.active = true;
        message_state.message = (unsigned short)i;
        message_state.page = 0;
        message_state.page_ticks = 0;
        message_state.finished = false;
        message_state.fade = 0;
        return (true);
    }
    /* Not one of the opening's messages. Show nothing rather than the wrong
    ** line: silence is visible as a bug, the wrong words are not. */
    message_stop();
    return (false);
}

void                message_stop(void)
{
    message_state.active = false;
    message_state.finished = false;
    message_state.page = 0;
    message_state.page_ticks = 0;
    message_state.fade = 0;
}

/* Move to the next page, or end the message. */
static void         advance(void)
{
    const cutscene_message_t *message = current();

    message_state.page_ticks = 0;
    message_state.fade = 0;
    if (!message || message_state.page + 1 >= message->pages) {
        message_state.active = false;
        message_state.finished = true;
        return;
    }
    ++message_state.page;
}

bool                message_step(bool confirm)
{
    const cutscene_page_t *page;

    message_state.finished = false;
    page = current_page();
    if (!page)
        return (false);

    ++message_state.page_ticks;
    switch (page->advance) {
        case CUTSCENE_ADVANCE_DELAY:
            if (message_state.page_ticks >= page->delay && confirm)
                advance();
            break;
        case CUTSCENE_ADVANCE_FADE:
            if (message_state.page_ticks >= page->delay) {
                unsigned int gone = message_state.page_ticks - page->delay;
                if (gone >= MESSAGE_FADE_TICKS)
                    advance();
                else
                    message_state.fade =
                        (unsigned char)(gone * 255 / MESSAGE_FADE_TICKS);
            }
            break;
        default:
            if (confirm)
                advance();
            break;
    }
    return (message_state.active);
}

bool                message_is_active(void)
{
    return (message_state.active);
}

bool                message_finished(void)
{
    return (message_state.finished);
}

unsigned int        message_lines(void)
{
    const cutscene_page_t *page = current_page();

    return (page ? page->lines : 0);
}

static const cutscene_line_t *line_at(unsigned int line)
{
    const cutscene_page_t *page = current_page();

    if (!page || line >= page->lines)
        return ((const cutscene_line_t *)0);
    return (&cutscene_text_lines[page->first_line + line]);
}

unsigned int        message_line_runs(unsigned int line)
{
    const cutscene_line_t *entry = line_at(line);

    return (entry ? entry->runs : 0);
}

unsigned int        message_line_indent(unsigned int line)
{
    const cutscene_line_t *entry = line_at(line);

    return (entry ? entry->indent : 0);
}

static const cutscene_run_t *run_at(unsigned int line, unsigned int run)
{
    const cutscene_line_t *entry = line_at(line);

    if (!entry || run >= entry->runs)
        return ((const cutscene_run_t *)0);
    return (&cutscene_runs[entry->first_run + run]);
}

const char         *message_run_text(unsigned int line, unsigned int run)
{
    const cutscene_run_t *entry = run_at(line, run);

    return (entry ? entry->text : "");
}

unsigned int        message_run_colour(unsigned int line, unsigned int run)
{
    const cutscene_run_t *entry = run_at(line, run);

    return (entry ? entry->colour : CUTSCENE_COLOUR_WHITE);
}

unsigned int        message_box(void)
{
    const cutscene_message_t *message = current();

    return (message ? message->box : CUTSCENE_BOX_BLACK);
}

unsigned int        message_position(void)
{
    const cutscene_message_t *message = current();

    return (message ? message->position : CUTSCENE_POS_BOTTOM);
}

bool                message_waits_for_button(void)
{
    const cutscene_page_t *page = current_page();

    return (page && (page->advance == CUTSCENE_ADVANCE_BUTTON ||
           (page->advance == CUTSCENE_ADVANCE_DELAY &&
            message_state.page_ticks >= page->delay)));
}

/*
** END OF FILE
*/
