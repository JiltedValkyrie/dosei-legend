#include "dialogue_text.h"
#include "text_pool.h"
#include "kokiri_dialogue.h"

static text_pool_t      dialogue_pool;

bool            dialogue_text_bind(const uint8_t *blob, uint32_t bytes)
{
    return (text_pool_bind(&dialogue_pool, "KDLG", blob, bytes,
                           DIALOGUE_LINE_COUNT, DIALOGUE_TEXT_BYTES));
}

const char     *dialogue_line(unsigned int index)
{
    return (text_pool_line(&dialogue_pool, index));
}
