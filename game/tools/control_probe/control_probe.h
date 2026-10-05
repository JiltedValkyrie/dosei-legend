#ifndef DOSEI_CONTROL_PROBE_H
#define DOSEI_CONTROL_PROBE_H
#include <stdint.h>
#include <string.h>
#include "ram_low.h"

/* Diagnostic build only. Commands are published by writing request last.
 * All fields are 32-bit so the Windows host has one explicit wire layout. */
#define CONTROL_MAGIC 0x41535452u
#define CONTROL_OFFSET 0x1D800u
#define CONTROL_FACES 10
typedef struct {
    int32_t poly, slot, submitted, source, size, palette, attr, matches;
    int32_t world[4][3], view[4][3], command[16];
} control_face_t;
typedef struct {
    uint32_t frame, request, count, visible, total, accepted;
    int32_t camera[5], matrix[12];
    control_face_t face[CONTROL_FACES];
} control_trace_t;
typedef struct {
    uint32_t magic, version, bytes, request, ack, opcode, steps, buttons;
    int32_t axis_x, axis_y, pose[4], camera[5], legacy;
    uint32_t hud, error, frame, sim_steps, remaining;
    int32_t link_now[4], camera_now[5];
    uint32_t trace_seq;
    control_trace_t pending, completed;
} control_mailbox_t;
#define CONTROL ((volatile control_mailbox_t *)RAM_LOW(CONTROL_OFFSET))
typedef char control_after_gear[CONTROL_OFFSET >= RAM_LOW_LINK_GEAR_POINTS_OFFSET + RAM_LOW_LINK_GEAR_POINTS_BYTES ? 1 : -1];
typedef char control_before_save[CONTROL_OFFSET + sizeof(control_mailbox_t) <= RAM_LOW_SAVE_OFFSET ? 1 : -1];
void control_trace_finish(void);
void control_trace_prepare(int visible);
#endif
