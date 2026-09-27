/*
** Cutscene message player. Contract in message.h.
*/

#include "message.h"
#include "text_pool.h"

/* Run text: CUTTEXT.TXT, line = run index (BUG-037). */
static text_pool_t      cutscene_pool;

bool                cutscene_text_bind(const uint8_t *blob, uint32_t bytes)
{
    return (text_pool_bind(&cutscene_pool, "KCST", blob, bytes,
                           CUTSCENE_RUN_COUNT, CUTSCENE_TEXT_BYTES));
}

message_state_t     message_state;

/* How long a FADE page takes to dim once its delay has run out. The original
** fades the whole screen over the following frames; here the text dims over
** this many cutscene ticks, so the line is gone by the time the shot cuts. */
#define MESSAGE_FADE_TICKS  10

/* Characters typed per cutscene tick. At 20 Hz this is close to the rate the
** original draws at, and it is what makes a page readable: the page's own
** timer does not start until the last character is on screen. */
#define MESSAGE_REVEAL_RATE 2

static unsigned int page_length(void);

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
        message_state.revealed = 0;
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
    message_state.revealed = 0;
    message_state.fade = 0;
}

/* Move to the next page, or end the message. */
static void         advance(void)
{
    const cutscene_message_t *message = current();

    message_state.page_ticks = 0;
    message_state.revealed = 0;
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

    /*
    ** Type the page out first, and only then start its timer.
    **
    ** A page whose timer ran from the moment it appeared could be gone before
    ** it had finished drawing, which is how whole lines were being missed. A
    ** press during the reveal finishes it rather than turning the page, so one
    ** press cannot skip a page unread.
    */
    if (message_state.revealed < page_length()) {
        if (confirm)
            message_state.revealed = (unsigned short)page_length();
        else
            message_state.revealed = (unsigned short)
                (message_state.revealed + MESSAGE_REVEAL_RATE);
        if (message_state.revealed > page_length())
            message_state.revealed = (unsigned short)page_length();
        return (true);
    }

    if (message_state.page_ticks < 65535)
        ++message_state.page_ticks;
    switch (page->advance) {
        case CUTSCENE_ADVANCE_DELAY:
            if (message_state.page_ticks >= page->delay && confirm)
                advance();
            break;
        case CUTSCENE_ADVANCE_FADE:
            /* The source delay starts after reveal. Do not add a second,
             * length-based reading hold after the player has read along. */
            if (message_state.page_ticks >= page->delay) {
                unsigned int delay = page->delay;
                unsigned int gone = message_state.page_ticks - delay;
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

    return (entry ? text_pool_line(&cutscene_pool,
                                   (unsigned int)(entry - cutscene_runs)) : "");
}

unsigned int        message_run_colour(unsigned int line, unsigned int run)
{
    const cutscene_run_t *entry = run_at(line, run);

    return (entry ? entry->colour : CUTSCENE_COLOUR_WHITE);
}

/* Characters on the current page, counted across its lines and runs. */
static unsigned int page_length(void)
{
    const cutscene_page_t *page = current_page();
    unsigned int           total = 0;
    unsigned int           line, run;

    if (!page)
        return (0);
    for (line = 0; line < page->lines; ++line) {
        const cutscene_line_t *entry =
            &cutscene_text_lines[page->first_line + line];

        for (run = 0; run < entry->runs; ++run) {
            const char *text = text_pool_line(&cutscene_pool, entry->first_run + run);

            while (*text++)
                ++total;
        }
    }
    return (total);
}

unsigned int        message_run_visible(unsigned int line, unsigned int run)
{
    const cutscene_page_t *page = current_page();
    unsigned int           before = 0;
    unsigned int           i, j;

    if (!page || line >= page->lines)
        return (0);
    /* Count the characters ahead of this run in reading order; whatever is
    ** left of the reveal belongs to it. */
    for (i = 0; i <= line; ++i) {
        const cutscene_line_t *entry =
            &cutscene_text_lines[page->first_line + i];
        unsigned int last = (i == line) ? run : entry->runs;

        if (i == line && run >= entry->runs)
            return (0);
        for (j = 0; j < last; ++j) {
            const char *text = text_pool_line(&cutscene_pool, entry->first_run + j);

            while (*text++)
                ++before;
        }
    }
    if (message_state.revealed <= before)
        return (0);
    return (message_state.revealed - before);
}

bool                message_is_revealing(void)
{
    return (message_state.active && message_state.revealed < page_length());
}

bool                message_is_last_page(void)
{
    const cutscene_message_t *message = current();

    return (!message || message_state.page + 1 >= message->pages);
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

    /* Never while the page is still typing itself out: the press would finish
    ** the reveal, not turn the page, so offering it would be a lie. */
    if (!page || message_is_revealing())
        return (false);
    return (page->advance == CUTSCENE_ADVANCE_BUTTON ||
            (page->advance == CUTSCENE_ADVANCE_DELAY &&
             message_state.page_ticks >= page->delay));
}

/*
** END OF FILE
*/
