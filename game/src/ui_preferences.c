#pragma GCC optimize("Os") /* Cold text/load paths: scarce work RAM. */
#include <string.h>
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

const char *ui_assign_modifier_label(void)
{
    /* Label presets describe emulator wiring, not remapping. N64/GameCube
     * have no defined C modifier in the preset: name the Saturn binding. */
    if (labels == UI_LABEL_XBOX) return "LB";
    if (labels == UI_LABEL_PLAYSTATION) return "L1";
    if (labels == UI_LABEL_SATURN) return "C";
    return "Sat C";
}


static bool text_analog;
void ui_text_set_analog(bool analog) { text_analog = analog; }
unsigned ui_text_revision(void)
{
    return (labels * UI_JUMP_COUNT + jump_binding) * 2 + text_analog;
}

/* Tokens name actions in the source, not similarly named Saturn buttons.
 * Source B attacks (Saturn X), Z targets, and C-Up enters view/Navi. */
static const char *text_button(const char *token, char label[32])
{
    unsigned key = 10;
    bool menu = false;
    const char *value;
    if (!strcmp(token, "AssignModifier")) return ui_assign_modifier_label();
    if (!strcmp(token, "AssignDirections")) {
        strcpy(label, ui_button_label(UI_KEY_DPAD, text_analog));
        strcat(label, " Down/Left/Right");
        return label;
    }
    if (!strcmp(token, "MenuPrev")) { key = UI_KEY_L; menu = true; }
    if (!strcmp(token, "MenuNext")) { key = UI_KEY_R; menu = true; }
    if (!strcmp(token, "Confirm")) { key = UI_KEY_A; menu = true; }
    if (!strcmp(token, "Cancel")) { key = UI_KEY_B; menu = true; }
    if (!strcmp(token, "A")) key = UI_KEY_A;
    else if (!strcmp(token, "B")) key = UI_KEY_X;
    else if (!strcmp(token, "Z")) key = UI_KEY_Z;
    else if (!strcmp(token, "R")) key = UI_KEY_R;
    else if (!strcmp(token, "L")) key = UI_KEY_L;
    else if (!strcmp(token, "Jump")) key = ui_jump_key();
    else if (!strcmp(token, "Start")) key = UI_KEY_START;
    if (key < 10) {
        if (!menu && key == ui_jump_key() && strcmp(token, "Jump")) return "unbound";
        value = ui_button_label(key, text_analog);
        if (*value) return value;
        /* A preset may omit a Saturn binding, but an instruction may not. */
        strcpy(label, "Sat ");
        label[4] = "LRABXYCZ"[key < 8 ? key : 0]; label[5] = 0;
        return label;
    }
    if (!strcmp(token, "Control-Pad") || !strcmp(token, "Control-Stick"))
        return text_analog ? "Stick" : "D-Pad";
    if (token[0] == 'C' && (token[1] == '-' || !token[1])) {
        const char *dir = token[1] ? token + 2 : "D-Pad";
        if (text_analog && !token[1]) return ui_button_label(UI_KEY_DPAD, true);
        if (text_analog) {
            if (labels == UI_LABEL_N64 || labels == UI_LABEL_GAMECUBE) {
                strcpy(label, labels == UI_LABEL_N64 ? "C-" : "C-Stick ");
            } else strcpy(label, "D-Pad ");
        } else {
            if (ui_jump_key() == UI_KEY_C) return "unbound";
            strcpy(label, ui_assign_modifier_label()); strcat(label, "+");
        }
        strncat(label, dir, 12);
        return label;
    }
    return token;
}

void ui_text_expand(const char *source, char *out, unsigned capacity)
{
    unsigned n = 0;
    if (!capacity) return;
    while (source && *source && n + 1 < capacity) {
        if (*source == '[') {
            const char *end = strchr(source + 1, ']');
            if (end && end - source < 24) {
                char token[24], label[32];
                const char *value;
                unsigned len = (unsigned)(end - source - 1);
                memcpy(token, source + 1, len); token[len] = 0;
                value = text_button(token, label);
                out[n++] = '[';
                while (*value && n + 1 < capacity) out[n++] = *value++;
                if (n + 1 < capacity) out[n++] = ']';
                source = end + 1;
                continue;
            }
        }
        out[n++] = *source++;
    }
    out[n] = 0;
}
