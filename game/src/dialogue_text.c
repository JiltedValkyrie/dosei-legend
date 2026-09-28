#pragma GCC optimize("Os") /* Cold text/load paths: scarce work RAM. */
#include "dialogue_text.h"
#include "text_pool.h"
#include "kokiri_dialogue.h"
#include "ui_preferences.h"
#include <string.h>
#ifdef __sh__
#include "ram_cart.h"
#endif

static text_pool_t      dialogue_pool;
static unsigned cached_first = ~0u;

bool            dialogue_text_bind(const uint8_t *blob, uint32_t bytes)
{
    cached_first = ~0u;
    return (text_pool_bind(&dialogue_pool, "KDLG", blob, bytes,
                           DIALOGUE_LINE_COUNT, DIALOGUE_TEXT_BYTES));
}

const char     *dialogue_line(unsigned int index)
{
    return (text_pool_line(&dialogue_pool, index));
}


#define TEXT_ROWS 32
#ifdef __sh__
typedef char text_layout_fits[TEXT_ROWS * 39 <= RAM_CART_TEXT_LAYOUT_BYTES ? 1 : -1];
#define rows ((char (*)[39])(RAM_CART_FIXED_ADDRESS + RAM_CART_TEXT_LAYOUT_OFFSET))
#else
static char rows[TEXT_ROWS][39];
#endif
static unsigned cached_count, cached_choices, cached_revision;
static unsigned row_count;

unsigned dialogue_prepare(unsigned first, unsigned count, unsigned choices)
{
    unsigned i, revision = ui_text_revision();
    if (first == cached_first && count == cached_count && choices == cached_choices &&
        revision == cached_revision) return row_count;
    cached_first = first; cached_count = count; cached_choices = choices;
    cached_revision = revision; row_count = 0;
    for (i = 0; i < count && row_count < TEXT_ROWS; ++i) {
        char expanded[512];
        const char *p;
        /* Never split the answer group across displayed pages. */
        if (choices && i == count - choices && row_count % 4 + choices > 4)
            while (row_count % 4) rows[row_count++][0] = 0;
        ui_text_expand(dialogue_line(first + i), expanded, sizeof(expanded));
        p = expanded;
        while (*p && row_count < TEXT_ROWS) {
            unsigned n = 0, split = 0;
            unsigned width = choices && i >= count - choices ? 36 : 38;
            bool button = false;
            while (p[n] && n < width) {
                if (p[n] == '[') button = true;
                if (p[n] == ']') button = false;
                if (p[n] == ' ' && !button) split = n;
                ++n;
            }
            if (p[n] && split) n = split;
            memcpy(rows[row_count], p, n); rows[row_count++][n] = 0;
            p += n;
            while (*p == ' ') ++p;
        }
    }
    return row_count;
}
const char *dialogue_row(unsigned row) { return row < row_count ? rows[row] : ""; }
