#ifndef UI_PREFERENCES_H
#define UI_PREFERENCES_H
#include <stdbool.h>
#include <stdint.h>
enum { UI_LABEL_SATURN, UI_LABEL_XBOX, UI_LABEL_N64, UI_LABEL_GAMECUBE, UI_LABEL_PLAYSTATION, UI_LABEL_COUNT };
enum { UI_KEY_L, UI_KEY_R, UI_KEY_A, UI_KEY_B, UI_KEY_X, UI_KEY_Y, UI_KEY_C, UI_KEY_Z, UI_KEY_START, UI_KEY_DPAD };
#define UI_JUMP_COUNT 8
#define UI_PREF_BYTES 8
unsigned ui_labels(void);
unsigned ui_jump_binding(void);
void ui_preferences_cycle(bool jump);
void ui_preferences_reset(void);
void ui_preferences_pack(uint8_t out[UI_PREF_BYTES]);
bool ui_preferences_unpack(const uint8_t *data, unsigned bytes);
const char *ui_label_name(void);
/* Physical Saturn-C binding used by pause, independent of analog routing. */
const char *ui_assign_modifier_label(void);
const char *ui_button_label(unsigned key, bool analog);
unsigned ui_jump_key(void);
uint16_t ui_jump_mask(void);
/* Expand OoT action tokens before dialogue wrapping, using current bindings. */
void ui_text_set_analog(bool analog);
unsigned ui_text_revision(void);
void ui_text_expand(const char *source, char *out, unsigned capacity);
#endif
