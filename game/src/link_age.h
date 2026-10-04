#ifndef LINK_AGE_H
#define LINK_AGE_H
#include <stdbool.h>
#include <stdint.h>
#include "link_clips.h"

/* ADULTSKN.BIN, native big endian on SH-2. One replaceable skin/gear layout;
 * the same POINT, POLYGON, ATTR and VDP1 banks serve both Link ages. */
typedef struct {
    uint32_t magic, bytes, vertices, polygons, tiles, pixels, digest, frames;
    int16_t shift[3];
    uint16_t visible;
    uint16_t gear[9][2];
    link_limb_t limbs[LINK_LIMB_COUNT];
} link_age_model_t;
#ifdef LINK_FRAMES_FROM_DISC
extern const link_age_model_t *link_age_model;
static inline bool link_anim_is_adult(void) { return link_age_model != 0; }
static inline int link_anim_shift(unsigned axis) {
    static const int child[3] = {LINK_ANIM_SHIFT_X,LINK_ANIM_SHIFT_Y,LINK_ANIM_SHIFT_Z};
    return link_age_model ? link_age_model->shift[axis] : child[axis];
}
static inline int link_anim_pinned_root(unsigned axis) {
    static const int roots[2][3] = {
        {LINK_PINNED_ROOT_X,LINK_PINNED_ROOT_Y,LINK_PINNED_ROOT_Z},
        {LINK_BASE_ROOT_X,LINK_BASE_ROOT_Y,LINK_BASE_ROOT_Z}};
    return roots[link_anim_is_adult()][axis];
}
#else
#define link_age_model ((const link_age_model_t *)0)
static inline bool link_anim_is_adult(void) { return false; }
static inline int link_anim_shift(unsigned axis) {
    const int child[3]={LINK_ANIM_SHIFT_X,LINK_ANIM_SHIFT_Y,LINK_ANIM_SHIFT_Z};return child[axis];
}
static inline int link_anim_pinned_root(unsigned axis) {
    const int child[3]={LINK_PINNED_ROOT_X,LINK_PINNED_ROOT_Y,LINK_PINNED_ROOT_Z};return child[axis];
}
#endif
bool link_anim_set_age(bool adult);
/* Loader transaction: prepare keeps the live pose/frames unchanged. */
bool link_anim_prepare_age(bool adult);
void link_anim_commit_age(void);
void link_anim_cancel_age(void);
#endif
