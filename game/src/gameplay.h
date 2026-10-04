#ifndef DOSEI_GAMEPLAY_H
#define DOSEI_GAMEPLAY_H
#include <stdbool.h>
#include <stdint.h>

#define GAMEPLAY_SARIA_CUE_CHANNEL 1

/*
** Forest gameplay state: inventory, gear pickups, Z-targeting, the sword swing
** and its active hit window, the shield, and which grass has been cut.
**
** Deliberately platform free, like player_input.c: no jo, no SGL, integers
** only. demo.c owns the fixed step and the audio; this file owns the rules, so
** the host tests drive the same code the Saturn runs.
**
** Placement comes from build/generated/kokiri_actors.h. Grass and NPCs are the
** original US 1.2 actor lists (En_Kusa, En_Ko/En_Md/En_Sa). The Kokiri Sword
** comes from the maze chest (En_Box 0x04E0) and rupees from En_Item00 and
** En_Wonder_Item placements; nothing is authored on the ground.
*/

/* Bit positions in `owned` and `equipped`. */
#define GP_SWORD            (1u << 0)
#define GP_SHIELD           (1u << 1)
#define GP_GET_NUT         4u
#define GP_GET_STICK       8u
#define GP_GET_HEART       16u
#define GP_GET_CONTAINER   32u
#define GP_GET_CHEST_ITEM  64u

/* Feedback raised during one step. demo.c turns these into sound; nothing in
** here plays audio, so a test can assert the event without a sound driver. */
#define GP_EVENT_PICKUP     (1u << 0)   /* got an item: chest or purchase */
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
/* Ledge climbs (Player_Action_80845668 / func_808389E8). CLIMB_END = the
** step-up's landing frame: NA_SE_VO_LI_CLIMB_END. HOP_VOICE = the ledge
** hop's NA_SE_VO_LI_SWORD_N. */
#define GP_EVENT_CLIMB_END  (1u << 22)
#define GP_EVENT_HOP_VOICE  (1u << 23)
/* Mido stood aside (0x1033 closed): demo.c may play his walk-away. */
#define GP_EVENT_MIDO_ASIDE (1u << 24)
#define GP_EVENT_HURT       (1u << 25)   /* Link took damage */
#define GP_EVENT_KNOCKDOWN  (1u << 26)   /* knockback large: Link falls */
#define GP_EVENT_GUARD      (1u << 27)   /* shield bounced an attack */
#define GP_EVENT_WALL_HIT   (1u << 28)   /* blade struck a wall (NA_SE_IT_WALL_HIT_*) */
#define GP_EVENT_REBOUND    (1u << 29)   /* blade bounced off a hard collider */
#define GP_EVENT_NUT_BREAK  (1u << 30)
/* Pending world audio: survives the next gameplay step until the audio consumer. */
enum { GP_SFX_SCRUB_UP, GP_SFX_SCRUB_DOWN, GP_SFX_SCRUB_THROW, GP_SFX_SCRUB_WALK, GP_SFX_SCRUB_HIT, GP_SFX_SCRUB_FAINT, GP_SFX_FOOT_SWITCH, GP_SFX_DEKU_HIT, GP_SFX_DEKU_DEAD, GP_SFX_SKULL_HIT, GP_SFX_SKULL_DEAD, GP_SFX_LARVA_HIT, GP_SFX_LARVA_DEAD, GP_SFX_GOHMA_HIT, GP_SFX_GOHMA_DEAD, GP_SFX_CORRECT, GP_SFX_APPEAR, GP_SFX_DOOR_OPEN, GP_SFX_DOOR_CLOSE, GP_SFX_FREEZE, GP_SFX_BOX_ITEM, GP_SFX_COUNT };
/* gameplay.events2 */
#define GP2_EVENT_NAVI_HELLO    (1u << 0)   /* Interface_SetNaviCall 0x1D: NA_SE_VO_NA_HELLO_2 */
#define GP2_EVENT_NAVI_CALL     (1u << 1)   /* 0x1E: NA_SE_VO_NAVY_CALL */
#define GP2_EVENT_NAVI_TALK     (1u << 2)   /* C-Up accepted: NA_SE_VO_SK_LAUGH */
#define GP2_EVENT_ERROR         (1u << 3)   /* NA_SE_SY_ERROR */
#define GP2_EVENT_LOCK_HOSTILE  (1u << 4)   /* with TARGET_ON: NA_SE_SY_LOCK_ON */
/* M2e damage/death (z_player.c func_80837C0C, func_80843E64, func_80836448). */
#define GP2_EVENT_LAND_DAMAGE   (1u << 5)   /* NA_SE_PL_BODY_HIT + LAND_DAMAGE_S voice */
#define GP2_EVENT_DEATH         (1u << 6)   /* health 0 on the ground: death clip */
#define GP2_EVENT_VOID_DAMAGE   (1u << 7)   /* respawn heart (NA_SE_OC_REVENGE) */
#define GP2_EVENT_ALARM         (1u << 8)   /* NA_SE_SY_HITPOINT_ALARM */
#define GP2_EVENT_HIT_BACK      (1u << 9)   /* with HURT: hit from behind (back anim) */
#define GP2_EVENT_HIT_HEAVY     (1u << 10)  /* with HURT: damage >= 5 (hit, not shit) */
#define GP2_EVENT_HIT_ANIM      (1u << 11)  /* with HURT: play the hit clip */
#define GP2_EVENT_LABELS        (1u << 15)
#define GP2_EVENT_JUMP_BINDING  (1u << 16)
#define GP2_EVENT_RESET_PREFS   (1u << 17)
#define GP2_EVENT_HP_RECOVER    (1u << 18)  /* NA_SE_SY_HP_RECOVER */
#define GP2_EVENT_GET_ITEM      (1u << 19)  /* ordinary non-rupee collectible */
#define GP2_EVENT_LOAD_MENU     (1u << 13)
#define GP2_EVENT_RETURN_TITLE  (1u << 14)
#define GP2_EVENT_ABYSS         (1u << 12)  /* void out began (NA_SE_OC_ABYSS) */
#define GP2_EVENT_CHEST_OPEN (1u << 20)
#define GP2_EVENT_ITEM_FANFARE (1u << 21)
#define GP2_EVENT_SMALL_FANFARE (1u << 22)
/* En_Elf / QuestHint timing, source 20 Hz updates. */
#define GP_NAVI_HINT_FROM   600
#define GP_NAVI_HINT_TO     3000
#define GP_NAVI_READ        3001
#define GP_NAVI_TIMER_MAX   25800   /* nutsball broke (NA_SE_EN_OCTAROCK_ROCK) */
#define GP_DROP_DELAY      15

/* Inventory slots, in menu order. These index the slot table, not the GP_*
** owned/equipped bits -- gp_slot_item() maps one to the other. */
#include "pause_window_state.h"

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
/* Sword timeline (z_player.c func_80837948 / Player_Action_808502D0).
** Attack clips play at PLAYER_ANIM_ADJUSTED_SPEED: 2/3 frame a step, kept
** in thirds (+2). Recovery (D_80854190 unk_04) plays at 1.0: +3. unk_844 = 8
** frames (12 steps) keeps the same-attack count alive; the third in a row
** plays the combo row (+2). Attack phases: 0 none, 1 attack, 2 recovery. */
#define GP_ATTACK_THIRDS_STEP   2
#define GP_RECOVER_THIRDS_STEP  3
#define GP_COMBO_WINDOW_STEPS   12
/* Player_Action_808502D0: a forward-stick attack (PLAYER_STATE2_30) lunges
** at speedXZ 15 on clip frame 0, stepping down 5 a frame: 10 a step, -20/9. */
#define GP_LUNGE_SPEED_Q16      655360
#define GP_LUNGE_DECEL_Q16      145636
/* Charged spin (func_808377DC, Player_Action_80844E68, func_80844BE4):
** unk_858 +0.02 a frame (Q16 874 a step); 0.1 commits, 0.85 is the big
** spin. The charge-start clip plays from frame 8. Release: Player_Set-
** Invulnerability(-8), 8 frames. Phases 3 start, 4 wait, 5 cancel end. */
#define GP_CHARGE_STEP_Q16      874
#define GP_CHARGE_COMMIT_Q16    6554
#define GP_CHARGE_BIG_Q16       55706
#define GP_CHARGE_START_FRAME   8
#define GP_SPIN_INVULN_STEPS    12
/* func_80842DF4 wall hit: speedXZ -14, the attack's Math_StepToF(0, 5):
** -9.33 a step, 20/9. func_80842D20 rebound and the guard recoil: -18 with
** Player_DecelerateToZero (R_DECELERATE_RATE 800: 8 a frame): -12, 32/9.
** Phases: 7 crouch stab, 8 sword rebound, 9 guard recoil. */
#define GP_WALL_PUSH_Q16        (-611669)
#define GP_REBOUND_PUSH_Q16     (-786432)
#define GP_REBOUND_DECEL_Q16    233017
#define GP_REBOUND_END_FRAME    6       /* Player_Action_808505DC curFrame >= 6 */
/* Blade line reaches 10 units behind the hilt (func_80842DF4 sp68). */
#define GP_BLADE_BACK           10
/* Swept blade capsules' radius: the source quads are flat; this stands in
** for their width after sampling the sweep at three edges. */
#define GP_BLADE_RADIUS         4
/* En_Nutsball: cylinder 13/13, AT 0xFFCFFFFF damage 8 (half a heart), AC
** 0xFFCFFFFF. speed 10 (6.67 a step, Q16 436907); timer 30 frames (45
** steps) then gravity -1 (-171 Q8); dies at -300 frames (-450 steps). */
#define GP_NUT_RADIUS           13
#define GP_NUT_HEIGHT           13
#define GP_NUT_DAMAGE           8
#define GP_NUT_SPEED_Q16        436907
#define GP_NUT_TIMER_STEPS      45
#define GP_NUT_LIFE_STEPS       450
/* Player_ActionHandler_10 (Z-targeted, outdoors): jump slash launches at
** speedXZ 5 / velocity.y 5; sidehop 8.5 / 3.5; backflip 6 / 5.8. Q8 source
** units, as demo.c's air code expects. Phase 6 = jump slash in the air. */
#define GP_JUMP_SLASH_SPEED_Q8  1280
#define GP_JUMP_SLASH_VY_Q8     1280
#define GP_SIDEHOP_SPEED_Q8     2176
#define GP_SIDEHOP_VY_Q8        896
#define GP_BACKFLIP_SPEED_Q8    1536
#define GP_BACKFLIP_VY_Q8       1485

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

/* EnMd_BlockPath (z_en_md.c): Mido keeps 60 units from home on Link's side.
** His OC cylinder is radius 36 (sCylinderInit), Link's 12 (z_player.c). He
** walks path 1 at speed 1.5 per 20 Hz frame, one unit per 30 Hz step. */
/* Kokiri Shop. EnOssan's talk reach is the slice's (counter between them);
** the Deku Shield's price is EnGirlA's basePrice (z_en_girla.c). */
#define GP_SHOP_TALK_RANGE   150
/* EnOssan stateFlag subset for the Kokiri Shop. */
typedef enum {
    GP_SHOP_NONE, GP_SHOP_HELLO, GP_SHOP_FACING, GP_SHOP_OWNER, GP_SHOP_TURN,
    GP_SHOP_BROWSE, GP_SHOP_SELECTED, GP_SHOP_RESULT, GP_SHOP_QUICK,
    GP_SHOP_GET, GP_SHOP_CONTINUE
}   gp_shop_state_t;
/* The pivot (browsing) view: the whole exchange except an item held up. */
#define GP_SHOP_BROWSING(s) ((s) != GP_SHOP_NONE && (s) != GP_SHOP_GET && \
                             (s) != GP_SHOP_CONTINUE)
#define GP_SHIELD_PRICE      40
/* En_Goroiwa, maze boulder (z_en_goroiwa.c), converted from 20 Hz frames to
** 30 Hz steps: speeds x2/3, accelerations x4/9, timers x3/2. Q16 where noted.
** Kokiri speed 9.2, step 0.3; gravity -0.86, floor velocity -15; hop 5 and
** speed x0.15 when it hits Link; waits 20/6 frames by rot_z & 1; 50 frames
** with no collision after a hit when rot_z & 1. Sphere r58 at y+59.5, live
** within 300 of Link. AT damage 4 (a quarter heart); Link's shield quad
** (AC 0xDFCFFFFF) cannot take the boulder's 0x20000000, so guarding never
** blocks it. Knockback large: 2.0 away from the boulder, 20 frames intangible. */
#define GP_BOULDER_SPEED_Q16    401954
#define GP_BOULDER_ACCEL_Q16    8738
#define GP_BOULDER_GRAVITY_Q16  (-25049)
#define GP_BOULDER_MIN_VY_Q16   (-655360)
#define GP_BOULDER_HOP_Q16      218453
#define GP_BOULDER_RADIUS       58
#define GP_BOULDER_CENTER_Y     60      /* 59.5 */
#define GP_BOULDER_LIVE_RANGE   300
#define GP_BOULDER_DAMAGE       4
#define GP_LINK_BODY_RADIUS     12      /* player cylinder */
#define GP_LINK_BODY_HEIGHT     50      /* feet to head + 10: child stand-in */
#define GP_KNOCKBACK_SPEED_Q16  87381   /* 2.0 a frame */
#define GP_INTANGIBLE_STEPS     30
/* Player_Action_Roll: Player_SetInvulnerability(-10) on anim frame 8. */
#define GP_ROLL_INVULN_FRAME    8
#define GP_ROLL_INVULN_STEPS    15      /* 10 source frames at 20 Hz */
/* Human playtest rule (not OoT): the jump attack is untouchable while airborne
** and for one second after it ends. */
#define GP_JUMP_ATTACK_GUARD_STEPS 30
/* Player damage response NONE (func_80837C0C from the AC_HIT branch):
** pushed 4.0 a frame away from the attacker. */
#define GP_HIT_SPEED_Q16        174763
/* Link's shield stand-in (the source is a quad on the left forearm): a
** cylinder this far in front of him while guarding. */
#define GP_SHIELD_FORWARD       16
#define GP_SHIELD_RADIUS        14
#define GP_SHIELD_HEIGHT        40
#define GP_MIDO_BLOCK_OFFSET 60
#define GP_MIDO_PUSH_RADIUS  (36 + 12)

typedef struct
{
    int32_t     x, y, z;        /* Link's feet */
    uint16_t    yaw;            /* facing, binang */
    bool        attack;         /* X pressed this step */
    bool        attack_held;    /* X held this step (charge) */
    bool        shield;         /* R held */
    /* L HELD this step, not a press edge: hold targeting needs the button's
    ** state every step to know when to release. */
    bool        target_held;
    bool        interact;       /* A pressed this step */
    bool        cancel;         /* B pressed this step: closes a text box */
    bool        pause;          /* Start pressed this step */
    int8_t      menu_dx, menu_dy, menu_page;
    int8_t      menu_step;      /* D-pad: -1 up/left, +1 down/right, 0 none */
    int8_t      menu_hold_x, menu_hold_y;   /* player_input_t, stick scale */
    /* controlStickDirections relative to Link's facing: -1 none, 0 forward,
    ** 1 left, 2 back, 3 right. `moving` = stick outside its dead zone. */
    int8_t      stick_dir;
    bool        moving;
    bool        grounded;
    bool        climbing;
    uint8_t     room;
    int32_t     focus[3];       /* Link focus.pos (head point), world */
    uint8_t     c_assign;       /* 1=down, 2=left, 3=right; pause only */
    bool        c_up;           /* C-Up pressed this step (talk to Navi) */
    uint8_t     c_use;          /* 1 down, 2 left, 3 right; world input only */
    int16_t     item_pitch;
    /* First-person aim: the seed leaves from the camera eye along the view
     * ray, so the centre cursor is where it goes. Off for quick shots. */
    bool        item_from_eye;
    int32_t     item_eye[3];
}               gameplay_input_t;

typedef struct
{
    uint16_t    rupees;
    uint16_t    rupee_taken;
    uint8_t     grass_rupee[16], grass_age[16];
    uint32_t    drop_rng;
    uint8_t     owned;
    uint8_t     equipped;
    bool        shielding;
    uint32_t    target;         /* actor_handle_t of the lock, 0 none */
    uint32_t    arrow;          /* arrow-hover actor handle (Navi), 0 none */
    /* Second event word (the first is full): GP2_EVENT_*. */
    uint32_t    events2;
    uint32_t    world_sfx;
    uint32_t    baba_events; /* Events from this gameplay step only. */
    uint16_t    navi_text;      /* player->naviTextId: pending quest hint */
    bool        navi_calling;   /* interfaceCtx->naviCalling latch */
    bool        navi_read;      /* En_Elf fairyFlags 0x80: hint was read */
    uint8_t     navi_phase;     /* 20 Hz update phase for the timer */
    uint8_t     alarm_steps;    /* HealthMeter beat: alarm every 30 steps */
    bool        dead;           /* PLAYER_STATE1_DEAD (until continue/title) */
    /* Consecutive steps L has been held, capped. Distinguishes a tap (which
    ** recentres) from a hold (which locks on). */
    uint8_t     target_hold;
    uint8_t     swing;          /* 1 while the attack clip plays (locks walk) */
    uint8_t     attack_id;      /* PLAYER_MWA_* (player_attack.h) */
    uint8_t     attack_phase;   /* 0 none, 1 attack, 2 recovery */
    uint16_t    attack_thirds;  /* clip time in thirds of a frame */
    uint8_t     combo_count, combo_timer;   /* unk_845, unk_844 in steps */
    bool        lunge_pending;  /* PLAYER_STATE2_30 until clip frame 0 runs */
    bool        charge_ok;      /* X held since the attack began (unk_844>0) */
    bool        charge_committed;   /* actionVar2 = 1: release spins */
    uint8_t     charge_from;    /* attack that led into the charge */
    uint16_t    charge_q16;     /* unk_858 */
    int32_t     lunge_q16;      /* forward speed a step, for demo.c */
    int32_t     lunge_decel_q16;    /* its step toward zero */
    bool        blade_bounced;  /* AT_BOUNCED on the blade this pass */
    bool        guard_pending;  /* shield AC_BOUNCED, read next step */
    uint8_t     wall_material;  /* SurfaceType material of the last wall hit */
    /* En_Nutsball projectile state; automatic debug emitter removed in M3d.
    ** nut_state 0 none, 1 flying; nut_reflected: AT_TYPE_PLAYER now. */
    uint8_t     nut_state, nut_reflected;
    int16_t     nut_timer;
    uint16_t    nut_yaw, nut_cooldown;
    int32_t     nut_x, nut_y, nut_z, nut_vy_q8, nut_fall_q8;
    uint8_t     swing_hit;      /* this swing already cut something */
    uint16_t    grass_cut;      /* one bit per kokiri_grass entry */
    /* En_Wonder_Item session state, one entry per kokiri_wonders[] row. A
    ** paid-out or failed trigger stays done until its room reloads, unless
    ** its switch flag keeps it done (z_en_wonder_item.c Init). */
    uint16_t    wonder_done;
    uint8_t     wonder_tags[16], wonder_next[16], wonder_timer[16];
    uint8_t     wonder_drop[16], wonder_age[16];   /* mode 3 ground rupee */
    uint8_t     room;           /* last room stepped, for room reloads */
    int16_t     chest_prompt;   /* kokiri_chests index A would open, -1 */
    uint8_t     opened_chest; /* index + 1 for this acquisition */
    uint16_t    get_item_age;
    uint8_t     get_item;       /* GP_* held up while its text shows, 0 none */
    /* Mido (EnMd). state: 0 blocking, 1 walking path 1, 2 moved. */
    uint8_t     mido_state;
    int32_t     mido_x, mido_z;
    /* Shop exchange: 0 none, 1 greeting, 2 item text, 3 buy choice,
    ** 4 result. `choice` is the TWO_CHOICE cursor, 0 = Buy. */
    /* En_Goroiwa. state 0 roll, 1 hop after a hit, 2 wait. Q16 position. */
    uint8_t     boulder_state, boulder_wait, boulder_nohit;
    bool        boulder_hit, boulder_in_way, boulder_live;
    int8_t      boulder_cur, boulder_next, boulder_dir;
    uint16_t    boulder_rot;
    int32_t     boulder_x, boulder_y, boulder_z, boulder_speed, boulder_vy;
    /* Link hurt: steps of intangibility left; knockback heading/speed Q16
    ** for demo.c to apply (speed decays there). */
    uint16_t    hurt_flash_phase;
    uint8_t     hurt_flash_timer;
    uint8_t     intangible;
    /* Player_SetInvulnerability: steps a hit still knocks Link back but
    ** deals no damage (the roll's dodge frames). */
    uint8_t     invulnerable;
    uint16_t    knock_yaw;
    int32_t     knock_speed;
    bool        knock_down;
    /* Link's body AC hit from the last contact pass, read by the next step
    ** (Player_UpdateDamage reads the previous frame's cylinder AC_HIT). */
    uint8_t     hurt_pending, hurt_damage;
    uint16_t    hurt_yaw;
    uint8_t     shop_state;     /* gp_shop_state_t (EnOssan stateFlag) */
    uint8_t     shop_cursor;    /* shelf slot 0-7 */
    int8_t      shop_face, shop_target;  /* cameraFaceAngle, degrees */
    int16_t     shop_accum_x, shop_accum_y;  /* stickAccumX/Y */
    bool        shop_move_x;    /* moveHorizontal */
    uint8_t     choice;
    bool        shop_prompt;    /* A would talk to the shopkeeper */
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
    uint8_t     page;           /* source page within that conversation */
    uint8_t     page_part;      /* expanded-label continuation within page */
    bool        talking;
    /* Pause inventory. */
    pause_window_state_t pause_window;
    bool        paused;
    uint8_t     cursor;         /* GP_SLOT_* under the D-pad */
}               gameplay_t;

extern gameplay_t   gameplay;
void gameplay_drop_message(unsigned int item);
bool gameplay_token_message(void);
bool gameplay_boss_heart(void);
bool gameplay_actor_message(uint16_t text_id);

/* Heading of a delta in the movement basis, atan2(dx, dz). Supplied by the
** platform: the Saturn build routes it to SGL's slAtan, the host tests to
** libm. Declared here so this file needs no SDK header. */
uint16_t            gameplay_facing(int32_t dx, int32_t dz);

/* True while a text box owns the input: demo.c must suppress movement, jump,
** attack, guard and the walk/run toggle for as long as this holds. */
bool                gameplay_is_talking(void);
/* Current page's line count and one line, for the box renderer. */
unsigned int        gameplay_page_lines(void);
bool gameplay_page_more(void);
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
/* Contact collider storage (fixed cart carve on Saturn). Unbound: no cuts. */
unsigned int        gameplay_contacts_bytes(void);
bool                gameplay_contacts_init(void *storage, unsigned int bytes);
void                gameplay_update_facing(int32_t x, int32_t z);
void                gameplay_step(const gameplay_input_t *in);
/* M2e: landing after a fall of `fell` world units (func_80843E64: 400..799
** half a heart, 800+ a heart, intangible 40 frames; none when the landing
** rolled). Void out: the respawn heart (func_808382DC, -16, no reaction). */
void                gameplay_land(int32_t fell, bool rolled);
void                gameplay_void_out(void);
void                gameplay_void_respawned(void);
/* The death clip ended (demo.c): the Game Over menu may start. */
void                gameplay_death_anim_done(void);
/* kokiri_npcs index of the locked actor, -1 when none or not an NPC. */
int                 gameplay_target_npc(void);
bool                gameplay_grass_cut(unsigned int index);
/* Platform hooks for the held weapon (demo.c on Saturn; stubs in host tests).
** Base/tip in world units, y = Link's feet frame, from the last posed left
** hand.  A Deku Stick uses its own source attachment, not the sword line.
** False: no pose; the sector stand-in is used.
** Wall: nearest wall crossing on the line from `from` to `to` (BgCheck_
** EntityLineTest1 walls, entity-ignored polys skipped, floor type 6 not
** counted), *material = SurfaceType material. */
bool                gameplay_blade_points(int32_t base[3], int32_t tip[3]);
bool                gameplay_blade_wall(const int32_t from[3], const int32_t to[3],
                                        unsigned int *material);
/* Nutsball move (Actor_MoveXZGravity + UpdateBgCheckInfo 10/13/13): moves
** pos by d, true when it touched a wall or the ground. */
bool                gameplay_ball_move(int32_t pos[3], int32_t dx, int32_t dy, int32_t dz);
/* Standard-build test encounter: spawn a nutsball at pos aimed at yaw. */
void                gameplay_nut_fire(int32_t x, int32_t y, int32_t z, uint16_t yaw);
/* The live nutsball's world position (draw). False when none. */
bool                gameplay_nut_body(int32_t *x, int32_t *y, int32_t *z);
/* Heading helper's partner: Q16 sine and cosine of a binang (platform). */
void                gameplay_sincos(uint16_t yaw, int32_t *sine, int32_t *cosine);
/* Runtime position of a speaker: Mido moves, everyone else is placement. */
/* Kokiri Forest NPCs exist only in that scene. */
bool                gameplay_npcs_present(void);
/* Placement `npc` exists in the current scene under its source spawn rule. */
bool                gameplay_npc_present(unsigned int npc);
int32_t             gameplay_npc_x(unsigned int npc);
int32_t             gameplay_npc_y(unsigned int npc);
int32_t             gameplay_npc_z(unsigned int npc);
uint16_t            gameplay_npc_yaw(unsigned int npc);
/* Source NPC_TRACKING_FULL_BODY body turn (npc_draw); reset on scene load. */
void                gameplay_npc_turn(unsigned int npc, uint16_t yaw);
void                gameplay_npc_turns_reset(void);
/* True while Saria's greeting cutscene owns her position, facing and
** pose. Her tracking, distance fade and clip all defer to it. */
bool                gameplay_saria_cutscene(void);
/* One gameplay step of the greeting: starts it when due, and closes it
** out the way EnSa_BecomeIdle does. Returns true while it is running. */
bool                gameplay_saria_greeting_step(void);
/* Decline the greeting for this scene without touching the save: the
** flag records that Saria HAS greeted Link, which is a different thing
** from a scene where the cutscene simply must not run. */
void                gameplay_saria_greeting_cancel(void);
void                gameplay_npc_focus(unsigned int npc, const int32_t offset[3]);
/* Mido's OC cylinder centre while he stands in `room`; false when gone. */
bool                gameplay_mido_body(unsigned int room, int32_t *x, int32_t *z);
/* Boulder sphere centre (whole units) while in `room`; false elsewhere. */
bool                gameplay_boulder_body(unsigned int room, int32_t *x, int32_t *y, int32_t *z);
bool                gameplay_chest_opened(unsigned int index);
/* Choice lines at the end of the current page (0 = none); the cursor is
** gameplay.choice. For the VDP2 box renderer. */
unsigned int        gameplay_choice_lines(void);
/* A mode-3 wonder rupee lying on the ground, ready to collect (for drawing). */
bool                gameplay_wonder_drop(unsigned int index);
/* True while the sword is live this step, for tests and diagnostics. */
bool                gameplay_sword_active(void);
/* Link's attack pose this step: LINK_CLIP_* and frame; false when none. */
bool                gameplay_attack_pose(unsigned int *clip, unsigned int *frame);
/* Same, with the clip time in thirds of a frame (root motion sampling). */
bool                gameplay_attack_time(unsigned int *clip, unsigned int *thirds);
/* Jump slash: start it in the air (func_8083BA90) / land it (func_80844AF4:
** JUMPSLASH_FINISH with unk_845 = 3). Start is false without a sword. */
bool                gameplay_jump_attack_start(void);
void                gameplay_jump_attack_land(void);
/* Damage-only dodge frames (keeps the longer of the current and `steps`). */
void                gameplay_set_invulnerable(unsigned steps);
/* End any attack at once (scene change, water entry). */
void                gameplay_attack_cancel(void);

#endif
