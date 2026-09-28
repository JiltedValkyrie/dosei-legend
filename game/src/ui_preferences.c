#include "ui_preferences.h"
#include "kokiri_camera.h"
static uint8_t labels, jump_binding;
static const uint8_t jump_keys[UI_JUMP_COUNT] = {
    UI_KEY_Y, UI_KEY_A, UI_KEY_B, UI_KEY_X, UI_KEY_C, UI_KEY_Z, UI_KEY_L, UI_KEY_R
};
static const uint16_t jump_masks[UI_JUMP_COUNT] = {
    CAMERA_Y, CAMERA_A, CAMERA_B, CAMERA_X, CAMERA_C, CAMERA_Z, CAMERA_L, CAMERA_R
};
unsigned ui_labels(void) { return labels; }
unsigned ui_jump_binding(void) { return jump_binding; }
unsigned ui_jump_key(void) { return jump_keys[jump_binding]; }
uint16_t ui_jump_mask(void) { return jump_masks[jump_binding]; }
void ui_preferences_reset(void) { labels = jump_binding = 0; }
void ui_preferences_cycle(bool jump)
{
    if (jump) jump_binding = (jump_binding + 1) % UI_JUMP_COUNT;
    else labels = (labels + 1) % UI_LABEL_COUNT;
}
void ui_preferences_pack(uint8_t out[UI_PREF_BYTES])
{
    unsigned i;
    out[0]='D'; out[1]='U'; out[2]='I'; out[3]=1;
    out[4]=labels; out[5]=jump_binding; out[6]=0; out[7]=0;
    for (i=0; i<7; ++i) out[7] ^= out[i];
}
bool ui_preferences_unpack(const uint8_t *data, unsigned bytes)
{
    unsigned i, check=0;
    if (!data || bytes != UI_PREF_BYTES || data[0]!='D' || data[1]!='U' ||
        data[2]!='I' || data[3]!=1 || data[4]>=UI_LABEL_COUNT ||
        data[5]>=UI_JUMP_COUNT || data[6]) return false;
    for (i=0; i<8; ++i) check ^= data[i];
    if (check) return false;
    labels=data[4]; jump_binding=data[5];
    return true;
}
const char *ui_label_name(void)
{
    static const char *const names[] = {"Saturn (Auto)","Xbox","N64","GameCube","PlayStation"};
    return names[labels];
}
const char *ui_button_label(unsigned key, bool analog)
{
    static const char *const names[5][10] = {
        {"L","R","A","B","X","Y","C+DPad","Z","Start","D-Pad"},
        {"LT","RT","A","B","X","Y","C+DPad","RB","Menu","D-Pad"},
        {"L","R","A","","B","","","Z","Start","C-Buttons"},
        {"L","R","A","","B","Y","","Z","Start","C-Stick"},
        {"L2","R2","Cross","Circle","Square","Triangle","L1+DPad","R1","Options","D-Pad"}
    };
    if (key >= 10) return "";
    if (labels == UI_LABEL_SATURN && analog && key < 2) return key ? "RT" : "LT";
    if (analog && key == UI_KEY_C) return "";
    return names[labels][key];
}
