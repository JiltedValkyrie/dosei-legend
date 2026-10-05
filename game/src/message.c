#pragma GCC optimize("Os") /* cold menu/save/script code: size over speed (work RAM) */
#pragma GCC optimize ("Os") /* Cold HUD/text updates; preserve high RAM. */
/*
** Cutscene message player. Contract in message.h.
*/

#include "message.h"
#include "text_pool.h"
#include "ui_preferences.h"
#include <string.h>
#ifdef __sh__
#include "ram_cart.h"
#endif

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
        message_state.choice = 0;
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
        if(message && message->next && message_start(message->next))return;
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

/* Cutscene tokens use the same saved labels as NPC dialogue, before wrapping.
 * Keep source colour per character while expanded labels cross source runs. */
#define MESSAGE_ROWS 16
typedef struct { char text[39]; unsigned char colour[38], indent; } message_row_t;
typedef struct {
    message_row_t row[MESSAGE_ROWS];
    char run[39], text[192], expanded[192];
    unsigned char colours[192];
} message_layout_t;
#ifdef __sh__
typedef char message_layout_fits[sizeof(message_layout_t) <= RAM_CART_MESSAGE_LAYOUT_BYTES ? 1 : -1];
#define layout (*(message_layout_t *)(RAM_CART_FIXED_ADDRESS + RAM_CART_MESSAGE_LAYOUT_OFFSET))
#else
static message_layout_t layout;
#endif
static const cutscene_page_t *layout_page;
static unsigned layout_revision, layout_count;
static bool layout_expanded;

static void prepare(void)
{
    const cutscene_page_t *page = current_page();
    unsigned revision = ui_text_revision(), i, j;
    if (page == layout_page && revision == layout_revision) return;
    layout_page = page; layout_revision = revision;
    layout_expanded = false; layout_count = 0;
    if (!page) return;
    for (i = 0; i < page->lines; ++i) {
        const cutscene_line_t *line = &cutscene_text_lines[page->first_line+i];
        for (j = 0; j < line->runs; ++j)
            if (strchr(text_pool_line(&cutscene_pool,line->first_run+j),'['))
                layout_expanded = true;
    }
    if (!layout_expanded) return;
    for (i = 0; i < page->lines; ++i) {
        const cutscene_line_t *line = &cutscene_text_lines[page->first_line+i];
        char *text = layout.text, *expanded = layout.expanded;
        unsigned char *colours = layout.colours;
        unsigned used = 0, at = 0, indent = line->indent;
        for (j = 0; j < line->runs; ++j) {
            unsigned k, run = line->first_run+j;
            ui_text_expand(text_pool_line(&cutscene_pool,run),expanded,sizeof(layout.expanded));
            for (k = 0; expanded[k] && used < sizeof(layout.text)-1; ++k) {
                text[used] = expanded[k]; colours[used++] = cutscene_runs[run].colour;
            }
        }
        text[used] = 0;
        do {
            unsigned n = 0, split = 0, width = 38-indent;
            bool button = false;
            if (layout_count >= MESSAGE_ROWS) return;
            while (at+n < used && n < width) {
                if (text[at+n] == '[') button = true;
                if (text[at+n] == ']') button = false;
                if (text[at+n] == ' ' && !button) split = n;
                ++n;
            }
            if (at+n < used && split) n = split;
            message_row_t *row = &layout.row[layout_count++];
            memcpy(row->text,text+at,n); row->text[n] = 0;
            memcpy(row->colour,colours+at,n); row->indent = indent;
            at += n; while (text[at] == ' ') ++at;
            indent = 0;
        } while (at < used);
    }
}

unsigned int message_lines(void)
{
    prepare();
    return layout_expanded ? layout_count : layout_page ? layout_page->lines : 0;
}
static const cutscene_line_t *line_at(unsigned line)
{
    const cutscene_page_t *page = current_page();
    return page && line < page->lines ? &cutscene_text_lines[page->first_line+line] : 0;
}
static unsigned run_start(unsigned line, unsigned run)
{
    unsigned at = 0;
    const message_row_t *row = &layout.row[line];
    while (row->text[at] && run) {
        unsigned colour = row->colour[at++];
        while (row->text[at] && row->colour[at] == colour) ++at;
        --run;
    }
    return at;
}
unsigned int message_line_runs(unsigned line)
{
    unsigned at = 0, count = 0;
    prepare();
    if (!layout_expanded) { const cutscene_line_t *p = line_at(line); return p ? p->runs : 0; }
    if (line >= layout_count) return 0;
    while (layout.row[line].text[at]) {
        unsigned colour = layout.row[line].colour[at++]; ++count;
        while (layout.row[line].text[at] && layout.row[line].colour[at] == colour) ++at;
    }
    return count;
}
unsigned int message_line_indent(unsigned line)
{
    prepare();
    if (layout_expanded) return line < layout_count ? layout.row[line].indent : 0;
    const cutscene_line_t *p = line_at(line); return p ? p->indent : 0;
}
const char *message_run_text(unsigned line, unsigned run)
{
    prepare();
    if (run >= message_line_runs(line)) return "";
    if (!layout_expanded) return text_pool_line(&cutscene_pool,line_at(line)->first_run+run);
    unsigned start = run_start(line,run), end = run_start(line,run+1);
    memcpy(layout.run,layout.row[line].text+start,end-start);
    layout.run[end-start] = 0;
    return layout.run;
}
unsigned int message_run_colour(unsigned line, unsigned run)
{
    prepare();
    if (run >= message_line_runs(line)) return CUTSCENE_COLOUR_WHITE;
    return layout_expanded ? layout.row[line].colour[run_start(line,run)] :
        cutscene_runs[line_at(line)->first_run+run].colour;
}
static unsigned int page_length(void)
{
    unsigned total = 0, line, run;
    for (line = 0; line < message_lines(); ++line)
        for (run = 0; run < message_line_runs(line); ++run)
            total += strlen(message_run_text(line,run));
    return total;
}
unsigned int message_run_visible(unsigned line, unsigned run)
{
    unsigned before = 0, i, j;
    if (line >= message_lines() || run >= message_line_runs(line)) return 0;
    for (i = 0; i <= line; ++i)
        for (j = 0; j < (i == line ? run : message_line_runs(i)); ++j)
            before += strlen(message_run_text(i,j));
    return message_state.revealed > before ? message_state.revealed-before : 0;
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

unsigned message_choices(void) {
    const cutscene_message_t *m=current();
    return m && message_is_last_page() && !message_is_revealing() ? m->choices : 0;
}
unsigned message_choice(void) { return message_state.choice; }
void message_choose(int direction) {
    unsigned count=message_choices();
    if(count && direction) message_state.choice=(message_state.choice+count+(direction>0?1:-1))%count;
}
