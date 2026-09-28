#ifndef DOSEI_DIALOGUE_TEXT_H
#define DOSEI_DIALOGUE_TEXT_H
#include <stdbool.h>
#include <stdint.h>

/*
** Dialogue line text, kept off work RAM (BUG-033). build_dialogue.py writes
** DIALOG.TXT: "KDLG", u16 BE line count, u16 BE offsets into the string area,
** then NUL-terminated strings. The page/rule tables stay in the program.
** Target: loaded once at boot into a fixed cart carve. Host tests bind the
** same file.
*/

/* Validate a blob and use it in place (it must outlive all line reads).
** False leaves text unbound: every line then reads "". */
bool         dialogue_text_bind(const uint8_t *blob, uint32_t bytes);

/* Line i of the pool, "" when unbound or out of range. */
const char  *dialogue_line(unsigned int index);

/* Expanded, wrapped rows of one source page. Choices remain together on its
 * final displayed page. Returned rows persist until the next prepare. */
unsigned dialogue_prepare(unsigned first, unsigned count, unsigned choices);
const char *dialogue_row(unsigned row);
#endif
