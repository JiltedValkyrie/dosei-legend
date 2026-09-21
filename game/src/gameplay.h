#ifndef DOSEI_GAMEPLAY_H
#define DOSEI_GAMEPLAY_H
#include <stdbool.h>
#include <stdint.h>

/*
** Forest gameplay state: inventory, gear pickups, Z-targeting, the sword swing
** and its active hit window, the shield, and which grass has been cut.
**
** Deliberately platform free, like player_input.c: no jo, no SGL, integers
** only. demo.c owns the fixed step and the audio; this file owns the rules, so
** the host tests drive the same code the Saturn runs.
**
** Placement comes from build/generated/kokiri_actors.h. Grass and NPCs are the
** original US 1.2 actor lists (En_Kusa, En_Ko/En_Md/En_Sa). The two gear
** pickups are authored -- Kokiri Forest has no sword or shield on the ground in
** the original -- but their floor height is verified at build time, not
** guessed here.
*/

/* Bit positions in `owned` and `equipped`. */
#define GP_SWORD            (1u << 0)
#define GP_SHIELD           (1u << 1)

/* Feedback raised during one step. demo.c turns these into sound; nothing in
** here plays audio, so a test can assert the event without a sound driver. */
#define GP_EVENT_PICKUP     (1u << 0)
#define GP_EVENT_SWING      (1u << 1)
#define GP_EVENT_CUT        (1u << 2)
#define GP_EVENT_TARGET_ON  (1u << 3)
#define GP_EVENT_TARGET_OFF (1u << 4)
#define GP_EVENT_SHIELD_UP  (1u << 5)
#define GP_EVENT_DENIED     (1u << 6)   /* action asked for, gear not owned */
#define GP_EVENT_TALK_OPEN  (1u << 7)
#define GP_EVENT_TALK_PAGE  (1u << 8)
#define GP_EVENT_TALK_CLOSE (1u << 9)
#define GP_EVENT_MENU_OPEN  (1u << 10)
#define GP_EVENT_MENU_CLOSE (1u << 11)
#define GP_EVENT_EQUIP      (1u << 12)
#define GP_EVENT_MENU_MOVE  (1u << 13)
#define GP_EVENT_JUMP       (1u << 14)
#define GP_EVENT_ROLL       (1u << 15)
#define GP_EVENT_FOOTSTEP   (1u << 16)
#define GP_EVENT_ROLL_VOICE (1u << 17)
#define GP_EVENT_RUPEE      (1u << 18)
/* The player chose SAVE in the pause menu. demo.c owns the device write, so
** gameplay.c stays free of the SDK and the host tests can assert the intent
** without a backup cartridge. */
#define GP_EVENT_SAVE       (1u << 19)
#define GP_EVENT_SAVE_FAILED (1u << 20)
/* A short L tap with no lock taken: recentre the camera behind Link. Raised
** here rather than read straight off the pad in demo.c, because whether a
** press recentres depends on whether it became a lock-on. */
#define GP_EVENT_RECENTER   (1u << 21)
#define GP_WALLET_CAPACITY  99
#define GP_DROP_DELAY      15

/* Inventory slots, in menu order. These index the slot table, not the GP_*
** owned/equipped bits -- gp_slot_item() maps one to the other. */
#define GP_SLOT_SWORD       0
#define GP_SLOT_SHIELD      1
/* Not an item: choosing this row writes the quest state to the file the player
** picked on the file select. OoT saves from the pause screen too. */
#define GP_SLOT_SAVE        2
#define GP_SLOT_COUNT       3

/* Talk range. OoT gates a conversation on the actor's own talk radius; the
** slice uses one distance for every Kokiri, which is an approximation and
** stays labelled as one. The fairy marks the speaker, but the OWNER position
** is what counts, not the fairy's bob height. */
#define GP_TALK_RANGE       92
#define GP_TALK_HEIGHT      100

/* Sword swing timing, in 30 Hz steps. OoT's child one-handed slash runs about
** two thirds of a second with the blade live in the middle of it; the window
** here is the same shape, sampled at our step rate. It is NOT a frame-exact
** port of Player_MeleeAttack, and the comment stays until it is. */
#define GP_SWING_STEPS      14
#define GP_SWING_HIT_FIRST  4
#define GP_SWING_HIT_LAST   8

/* Reach, in world units. Child Link's sword sweeps a little under a body
** width; grass is cut when its base falls inside that arc. */
#define GP_SWORD_REACH      66
#define GP_SWORD_HEIGHT     60          /* vertical tolerance either way */
/* Z-target acquisition. OoT keeps lock-on well past talking range, so the
** camera can hold an actor Link is backing away from. */
#define GP_TARGET_RANGE     320
#define GP_TARGET_DROP      420
/* HOLD targeting, which is OoT's own alternative to Switch: the lock lasts
** only while L is held and releasing drops it (z_player.c:3896 keeps the
** lock alive on zButtonHeld, and sets LOCK_ON_WITH_SWITCH only in Switch
** mode). A press shorter than this many 30 Hz steps is treated as a tap and
** recentres the camera instead of locking, so walking past a Kokiri with L
** brushed does not grab them.
**
** The threshold itself is THIS SLICE'S CHOICE. OoT has no tap/hold split --
** in Hold mode a press with no target starts Parallel immediately -- so this
** number is tuned for feel, not ported. Roughly 0.17 s. */
#define GP_TARGET_HOLD_STEPS 5
#define GP_PICKUP_RANGE     44
#define GP_PICKUP_HEIGHT    70

typedef struct
{
    int32_t     x, y, z;        /* Link's feet */
    uint16_t    yaw;            /* facing, binang */
    bool        attack;         /* X pressed this step */
    bool        shield;         /* R held */
    /* L HELD this step, not a press edge: hold targeting needs the button's
    ** state every step to know when to release. */
    bool        target_held;
    bool        interact;       /* A pressed this step */
    bool        cancel;         /* B pressed this step: closes a text box */
    bool        pause;          /* Start pressed this step */
    int8_t      menu_step;      /* D-pad: -1 up/left, +1 down/right, 0 none */
    bool        grounded;
    uint8_t     room;
}               gameplay_input_t;

typedef struct
{
    uint8_t     rupees;
    uint16_t    rupee_taken;
    uint8_t     grass_rupee[16], grass_age[16];
    uint32_t    drop_rng;
    uint8_t     owned;
    uint8_t     equipped;
    bool        shielding;
    int16_t     target;         /* kokiri_npcs index, -1 for none */
    /* Consecutive steps L has been held, capped. Distinguishes a tap (which
    ** recentres) from a hold (which locks on). */
    uint8_t     target_hold;
    uint8_t     swing;          /* steps remaining, 0 when idle */
    uint8_t     swing_hit;      /* this swing already cut something */
    uint16_t    grass_cut;      /* one bit per kokiri_grass entry */
    uint8_t     pickup_taken;   /* one bit per kokiri_pickups entry */
    uint32_t    events;         /* raised this step only */
    uint16_t    face_yaw;       /* heading to hold while locked on */
    bool        face_locked;
    uint16_t    cut_count;
    uint16_t    swing_count;
    /* Dialogue. `speaker` is the kokiri_npcs index being talked to, -1 when no
    ** box is open; `prompt` is the npc index an A press would talk to now. */
    int16_t     speaker;
    int16_t     prompt;
    /* dialogue_rules index, -1 none. A rule, not a conversation: each speaker
    ** owns an ordered rule list and the first rule whose quest conditions hold
    ** is the line they actually say, exactly as the original's text-id
    ** function works. See build_dialogue.py. */
    int16_t     rule;
    uint8_t     page;           /* page within that conversation */
    bool        talking;
    /* Pause inventory. */
    bool        paused;
    uint8_t     cursor;         /* GP_SLOT_* under the D-pad */
}               gameplay_t;

extern gameplay_t   gameplay;

/* Heading of a delta in the movement basis, atan2(dx, dz). Supplied by the
** platform: the Saturn build routes it to SGL's slAtan, the host tests to
** libm. Declared here so this file needs no SDK header. */
uint16_t            gameplay_facing(int32_t dx, int32_t dz);

/* True while a text box owns the input: demo.c must suppress movement, jump,
** attack, guard and the walk/run toggle for as long as this holds. */
bool                gameplay_is_talking(void);
/* Current page's line count and one line, for the box renderer. */
unsigned int        gameplay_page_lines(void);
const char         *gameplay_page_line(unsigned int line);
const char         *gameplay_speaker_name(void);

/* Pause inventory. While paused the world is frozen: demo.c must not step
** locomotion, camera easing, gravity or any action. */
bool                gameplay_is_paused(void);
/* True when either the pause menu or a text box owns the pad. */
bool                gameplay_blocks_world(void);
/* GP_SWORD / GP_SHIELD for a slot, its name, and how it is used. */
uint8_t             gameplay_slot_item(unsigned int slot);
const char         *gameplay_slot_name(unsigned int slot);
const char         *gameplay_slot_use(unsigned int slot);

bool                gameplay_rupee_taken(unsigned int index);
void                gameplay_reset(void);
void                gameplay_update_facing(int32_t x, int32_t z);
void                gameplay_step(const gameplay_input_t *in);
bool                gameplay_grass_cut(unsigned int index);
bool                gameplay_pickup_taken(unsigned int index);
/* True while the sword is live this step, for tests and diagnostics. */
bool                gameplay_sword_active(void);

#endif
