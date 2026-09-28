#ifndef DOSEI_KAREBABA_H
#define DOSEI_KAREBABA_H
#include <stdbool.h>
#include <stdint.h>
#include "actor_sys.h"
#include "collide.h"

/*
** En_Karebaba (withered Deku Baba), z_en_karebaba.c, in integers.
**
** Each baba is a registry actor (Z-target, Navi, lock-on sound) plus this
** module's state and two colliders. The state machine runs at the source
** 20 Hz: two of every three 30 Hz steps. Positions are Q8 world units;
** scale is actor scale x 20000 (0.01 = 200).
**
** Source quirk kept: Collider_UpdateCylinder runs only in Init, so the head
** AT and body AC cylinders stay at the spawn point for life, while the head
** swings around it.
**
** Drop (bible rule, traced in M2D_PLAN.md): DeadItemDrop offers exactly one
** GI_DEKU_STICKS_1 for 200 updates (blinking the last 40). Link takes it
** with no button once within 50 xz / 10 y; the first stick ever plays the
** get-item text, later ones are quiet. A full bag still takes it (Item_Give
** clamps). Then Dead 200, Regrow 20, Idle: forever.
*/

#define KAREBABA_MAX        8

typedef enum {
    KAREBABA_GROW, KAREBABA_IDLE, KAREBABA_AWAKEN, KAREBABA_UPRIGHT,
    KAREBABA_SPIN, KAREBABA_DYING, KAREBABA_DROP, KAREBABA_RETRACT,
    KAREBABA_DEAD, KAREBABA_REGROW
} karebaba_action_t;

typedef struct {
    actor_handle_t  handle;
    uint8_t         action, phase, picked, spawn;
    int16_t         timer;              /* actor.params */
    int16_t         scale;              /* x 20000 */
    int32_t         home[3];
    int32_t         pos_q8[3];
    int32_t         vel_y_q8, speed_q8;
    uint16_t        rot_x, rot_y, move_yaw;
    int16_t         frame_q8, frame_speed_q8;   /* gDekuBabaFastChompAnim */
    bool            ground, wall;
    bool            hit;                /* AC_HIT latched until the next tick */
    collider_t      head, body;
} karebaba_t;

/* State storage (cart on Saturn, like the actor pool): KAREBABA_MAX slots.
** Without it nothing spawns. */
unsigned int karebaba_bytes(void);
bool    karebaba_init(void *storage, unsigned int bytes);
/* Spawn/sync the forest babas (room 1 live, killed elsewhere). */
void    karebaba_sync(bool in_scene, unsigned int room);
void    karebaba_reset(void);
/* One gameplay step: reads last run's collider results first. */
void    karebaba_update(int32_t link_x, int32_t link_y, int32_t link_z, bool can_take);
/* Inside gameplay's collide_begin..collide_run. */
void    karebaba_register(void);
/* Right after collide_run: latch body AC hits. The collision pass runs
** every 30 Hz step, the actor only on 20 Hz ticks. */
void    karebaba_collect(void);
unsigned int        karebaba_count(void);
const karebaba_t   *karebaba_at(unsigned int i);

/* Platform hook: Actor_MoveXZGravity + UpdateBgCheckInfo(10, 15, 10): move
** feet `pos` (world) by d; report ground and wall touches. */
bool    karebaba_bg_move(int32_t pos[3], const int32_t d[3], bool *ground, bool *wall);

/* Events for audio/gameplay, cleared each karebaba_update. */
#define KAREBABA_EV_AWAKEN      (1u << 0)   /* NA_SE_EN_DUMMY482 */
#define KAREBABA_EV_MOUTH       (1u << 1)   /* NA_SE_EN_DEKU_JR_MOUTH */
#define KAREBABA_EV_DEAD        (1u << 2)   /* NA_SE_EN_DEKU_JR_DEAD */
#define KAREBABA_EV_LAST_DAMAGE (1u << 3)   /* Enemy_StartFinishingBlow */
#define KAREBABA_EV_GROUND      (1u << 4)   /* NA_SE_EN_DODO_M_GND */
#define KAREBABA_EV_STICK_FIRST (1u << 5)   /* first stick: get-item text 0x37 */
#define KAREBABA_EV_STICK       (1u << 6)   /* NA_SE_SY_GET_ITEM */
uint32_t karebaba_events(void);

#endif
