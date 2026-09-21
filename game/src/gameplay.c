#include "gameplay.h"
#include "kokiri_actors.h"
#include "kokiri_dialogue.h"
#include "save_state.h"

gameplay_t          gameplay;

#if KOKIRI_GRASS_COUNT > 16 || KOKIRI_RUPEE_COUNT > 16
#error Expand collectible storage before adding actors
#endif

static uint32_t drop_random(void)
{
    gameplay.drop_rng ^= gameplay.drop_rng << 13;
    gameplay.drop_rng ^= gameplay.drop_rng >> 17;
    gameplay.drop_rng ^= gameplay.drop_rng << 5;
    return gameplay.drop_rng;
}

/* Squared planar distance. Coordinates stay inside +/-5000 world units, so the
** products fit a 32-bit int with room to spare and no 64-bit math is needed on
** the SH-2. */
static int32_t      planar_squared(int32_t ax, int32_t az, int32_t bx, int32_t bz)
{
    int32_t dx = ax - bx, dz = az - bz;
    return dx * dx + dz * dz;
}

/* Signed shortest turn between two binang headings, -32768..32767. */
static int32_t      yaw_delta(uint16_t from, uint16_t to)
{
    return (int32_t)(int16_t)(uint16_t)(to - from);
}

static void         sync_gear_to_save(void);
static void         sync_gear_from_save(void);

void                gameplay_reset(void)
{
    unsigned int i;
    gameplay.owned = 0;
    gameplay.equipped = 0;
    gameplay.shielding = false;
    gameplay.target = -1;
    gameplay.target_hold = 0;
    gameplay.swing = 0;
    gameplay.swing_hit = 0;
    gameplay.grass_cut = 0;
    gameplay.pickup_taken = 0;
    gameplay.events = 0;
    gameplay.face_yaw = 0;
    gameplay.face_locked = false;
    gameplay.cut_count = 0;
    gameplay.swing_count = 0;
    gameplay.speaker = -1;
    gameplay.prompt = -1;
    gameplay.rule = -1;
    gameplay.page = 0;
    gameplay.talking = false;
    gameplay.paused = false;
    gameplay.cursor = GP_SLOT_SWORD;
    gameplay.rupees = 0;
    gameplay.rupee_taken = 0;
    gameplay.drop_rng = 0x12345678u;
    /* owned/equipped/rupees/pickup_taken/rupee_taken are restored from the
    ** save by sync_gear_from_save() at the end of this function. */
    for (i = 0; i < 16; ++i) {
        gameplay.grass_rupee[i] = 0;
        gameplay.grass_age[i] = 0;
    }
    /* Reset means "entering a scene", and it runs AFTER the file select has
    ** either started a new game or loaded a save. So gear, rupees and taken
    ** pickups are read FROM the save here. Writing to it instead is what made
    ** loading a file wipe the sword and shield it had just restored. */
    sync_gear_from_save();
}

bool                gameplay_grass_cut(unsigned int index)
{
    return index < KOKIRI_GRASS_COUNT &&
           (gameplay.grass_cut & (1u << index)) != 0;
}

bool                gameplay_pickup_taken(unsigned int index)
{
    return index < KOKIRI_PICKUP_COUNT &&
           (gameplay.pickup_taken & (1u << index)) != 0;
}

/* Session-only wallet and collectible flags. Child wallet: z_inventory.c. */
bool gameplay_rupee_taken(unsigned int index)
{
    return index < KOKIRI_RUPEE_COUNT && (gameplay.rupee_taken & (1u << index));
}

static bool rupee_near(const gameplay_input_t *in, int x, int y, int z, int room)
{
    int dy = in->y - y;
    return in->room == room && dy >= -40 && dy <= 40 &&
           planar_squared(in->x, in->z, x, z) <= 30 * 30;
}

static void grant_rupee(unsigned int value)
{
    unsigned int total = gameplay.rupees + value;
    gameplay.rupees = total > GP_WALLET_CAPACITY ? GP_WALLET_CAPACITY : total;
    /* The wallet is saved state: the Deku Shield costs 40 rupees, so losing
    ** the count on a reload would undo real progress. */
    save_state.rupees = gameplay.rupees;
    gameplay.events |= GP_EVENT_RUPEE;
}

static void collect_rupees(const gameplay_input_t *in)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_RUPEE_COUNT; ++i) {
        const kokiri_rupee_t *r = &kokiri_rupees[i];
        if (!gameplay_rupee_taken(i) && rupee_near(in, r->x, r->y, r->z, r->room)) {
            gameplay.rupee_taken |= (uint16_t)(1u << i);
            /* Per-scene collectible flag, where OoT keeps them, so a rupee
            ** already picked up does not reappear after a save and reload. */
            save_set_collectible(save_state.scene_id, i);
            grant_rupee(r->value);
        }
    }
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *g = &kokiri_grass[i];
        if (!gameplay.grass_rupee[i] || in->room != g->room) continue;
        if (gameplay.grass_age[i] < GP_DROP_DELAY) {
            ++gameplay.grass_age[i];
            continue; /* visible pop before Link can collect it */
        }
        if (rupee_near(in, g->x, g->y, g->z, g->room)) {
            grant_rupee(gameplay.grass_rupee[i]);
            gameplay.grass_rupee[i] = 0;
        }
    }
}

/* Gear, rupees and one-off pickups live in the SAVE. gameplay_t holds them as
** GP_* bits and a small wallet only because the per-step actions read them
** constantly and a bitmask is cheaper than four accessor calls.
**
** The save is the owner; these two functions keep the cache agreeing with it.
** Direction matters and getting it wrong is how a loaded file lost its sword
** and shield: gameplay_reset() runs when entering a scene, which is AFTER a
** file has been loaded, so it must read FROM the save. Only the places where
** gear actually changes -- a pickup, or equipping in the menu -- write TO it.
**
** Mido's gate is decided by save_cur_equip_value(), so the two must not drift
** in either direction. */
static void         sync_gear_to_save(void)
{
    save_give_equip(EQUIP_TYPE_SWORD,
                    (gameplay.owned & GP_SWORD) ? EQUIP_VALUE_SWORD_KOKIRI : 0);
    save_give_equip(EQUIP_TYPE_SHIELD,
                    (gameplay.owned & GP_SHIELD) ? EQUIP_VALUE_SHIELD_DEKU : 0);
    save_set_equip(EQUIP_TYPE_SWORD,
                   (gameplay.equipped & GP_SWORD) ? EQUIP_VALUE_SWORD_KOKIRI : 0);
    save_set_equip(EQUIP_TYPE_SHIELD,
                   (gameplay.equipped & GP_SHIELD) ? EQUIP_VALUE_SHIELD_DEKU : 0);
    save_state.rupees = gameplay.rupees;
}

static void         sync_gear_from_save(void)
{
    unsigned int    i;

    gameplay.owned = 0;
    gameplay.equipped = 0;
    if (save_all_equip_value(EQUIP_TYPE_SWORD) == EQUIP_VALUE_SWORD_KOKIRI)
        gameplay.owned |= GP_SWORD;
    if (save_all_equip_value(EQUIP_TYPE_SHIELD) == EQUIP_VALUE_SHIELD_DEKU)
        gameplay.owned |= GP_SHIELD;
    if (save_cur_equip_value(EQUIP_TYPE_SWORD) == EQUIP_VALUE_SWORD_KOKIRI)
        gameplay.equipped |= GP_SWORD;
    if (save_cur_equip_value(EQUIP_TYPE_SHIELD) == EQUIP_VALUE_SHIELD_DEKU)
        gameplay.equipped |= GP_SHIELD;
    gameplay.rupees = (uint8_t)(save_state.rupees > GP_WALLET_CAPACITY
                                ? GP_WALLET_CAPACITY : save_state.rupees);
    /* A pickup already taken must not reappear on the floor after a reload. */
    gameplay.pickup_taken = 0;
    if (save_get_item_get_inf(ITEMGETINF_GROUND_SWORD))
        gameplay.pickup_taken |= 1u;
    if (save_get_item_get_inf(ITEMGETINF_GROUND_SHIELD))
        gameplay.pickup_taken |= 2u;
    /* Room rupees are per-scene collectible flags, exactly as OoT stores them,
    ** so a collected rupee stays collected across a save. Cut grass is NOT
    ** persisted: OoT keeps grass in the temp half of the scene flags, which it
    ** deliberately never saves, so regrowing is the original's behaviour. */
    gameplay.rupee_taken = 0;
    for (i = 0; i < KOKIRI_RUPEE_COUNT && i < 16; ++i)
        if (save_get_collectible(save_state.scene_id, i))
            gameplay.rupee_taken |= (uint16_t)(1u << i);
}

bool                gameplay_sword_active(void)
{
    unsigned int elapsed;
    if (!gameplay.swing)
        return false;
    elapsed = GP_SWING_STEPS - gameplay.swing;
    return elapsed >= GP_SWING_HIT_FIRST && elapsed <= GP_SWING_HIT_LAST;
}

/* Collect any gear Link is standing on. Each pickup is granted once and
** equipped immediately, which is what the slice asks for: no menu exists yet,
** so an unequipped item would be an item the player cannot use. */
static void         collect_pickups(const gameplay_input_t *in)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_PICKUP_COUNT; ++i) {
        const kokiri_pickup_t *pickup = &kokiri_pickups[i];
        int32_t dy;
        if (gameplay.pickup_taken & (1u << i))
            continue;
        dy = in->y - pickup->y;
        if (dy < 0) dy = -dy;
        if (dy > GP_PICKUP_HEIGHT)
            continue;
        if (planar_squared(in->x, in->z, pickup->x, pickup->z) >
            (int32_t)GP_PICKUP_RANGE * GP_PICKUP_RANGE)
            continue;
        gameplay.pickup_taken |= (uint8_t)(1u << i);
        gameplay.owned |= pickup->item;
        gameplay.equipped |= pickup->item;
        /* Record the pickup itself, not just the gear: otherwise a reloaded
        ** file puts the sword back on the floor to be collected again. */
        save_set_item_get_inf(i == 0 ? ITEMGETINF_GROUND_SWORD
                                     : ITEMGETINF_GROUND_SHIELD);
        sync_gear_to_save();
        gameplay.events |= GP_EVENT_PICKUP;
    }
}

/* Nearest NPC inside acquisition range and roughly in front of Link.
**
** OoT's real rule scores actors by a projected screen position and a per-actor
** lock-on radius. This is the slice's approximation: nearest by planar
** distance, inside a 90 degree cone around the facing. Written down as an
** approximation rather than presented as Z-target parity. */
static int16_t      find_target(const gameplay_input_t *in)
{
    int32_t best = (int32_t)GP_TARGET_RANGE * GP_TARGET_RANGE + 1;
    int16_t found = -1;
    unsigned int i;
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        const kokiri_npc_t *npc = &kokiri_npcs[i];
        int32_t distance = planar_squared(in->x, in->z, npc->x, npc->z);
        int32_t turn;
        if (distance >= best)
            continue;
        turn = yaw_delta(in->yaw, gameplay_facing(npc->x - in->x,
                                                  npc->z - in->z));
        if (turn < 0) turn = -turn;
        if (turn > 16384)          /* outside +/-90 degrees */
            continue;
        best = distance;
        found = (int16_t)i;
    }
    return found;
}

void gameplay_update_facing(int32_t x, int32_t z)
{
    if (gameplay.face_locked && gameplay.target >= 0 && gameplay.target < KOKIRI_NPC_COUNT) {
        const kokiri_npc_t *npc = &kokiri_npcs[gameplay.target];
        gameplay.face_yaw = gameplay_facing(npc->x - x, npc->z - z);
    }
}

/* L presses toggle the lock. OoT supports Switch and Hold; this slice uses
** a simple Switch-style toggle. L is also the recenter button, and
** demo.c only recenters when no lock was taken or dropped. */
static void         drop_target(void)
{
    if (gameplay.target >= 0)
        gameplay.events |= GP_EVENT_TARGET_OFF;
    gameplay.target = -1;
    gameplay.face_locked = false;
}

/* HOLD targeting, the setting OoT itself offers as the alternative to Switch.
**
** L held past GP_TARGET_HOLD_STEPS locks onto the nearest actor in front and
** keeps the lock only while it stays held; releasing drops it. A press shorter
** than that is a tap and recentres the camera instead, so brushing L while
** running past a Kokiri no longer grabs them -- which is what made Switch-style
** toggling annoying in the forest.
**
** The lock also drops once the actor is past GP_TARGET_DROP, as before. */
static void         update_target(const gameplay_input_t *in)
{
    if (!in->target_held) {
        /* Released. A short press that never became a lock is the recentre
        ** gesture; one that did lock just ends, with no recentre, or the view
        ** would swing away from the actor the player was just looking at. */
        if (gameplay.target_hold > 0 &&
            gameplay.target_hold < GP_TARGET_HOLD_STEPS &&
            gameplay.target < 0)
            gameplay.events |= GP_EVENT_RECENTER;
        gameplay.target_hold = 0;
        drop_target();
        return;
    }

    if (gameplay.target_hold < GP_TARGET_HOLD_STEPS)
        ++gameplay.target_hold;

    if (gameplay.target_hold < GP_TARGET_HOLD_STEPS) {
        /* Still inside the tap window: nothing is locked yet, so Link keeps
        ** facing wherever he is travelling. */
        gameplay.face_locked = false;
        return;
    }

    if (gameplay.target >= 0) {
        const kokiri_npc_t *npc = &kokiri_npcs[gameplay.target];
        if (planar_squared(in->x, in->z, npc->x, npc->z) >
            (int32_t)GP_TARGET_DROP * GP_TARGET_DROP) {
            drop_target();
            return;
        }
        gameplay.face_yaw = gameplay_facing(npc->x - in->x, npc->z - in->z);
        gameplay.face_locked = true;
        return;
    }

    /* Held long enough and nothing locked yet: try to acquire. Retried every
    ** step while held, so holding L and turning toward an actor picks them up
    ** rather than requiring a fresh press. */
    gameplay.target = find_target(in);
    if (gameplay.target >= 0) {
        const kokiri_npc_t *npc = &kokiri_npcs[gameplay.target];
        /* Turn on the acquiring step, not the one after it: a frame of Link
         * still facing his travel heading reads as the lock being ignored. */
        gameplay.face_yaw = gameplay_facing(npc->x - in->x, npc->z - in->z);
        gameplay.face_locked = true;
        gameplay.events |= GP_EVENT_TARGET_ON;
    } else {
        gameplay.face_locked = false;
    }
}

/* Cut every uncut tuft inside the live blade's arc. One swing can clear a
** cluster, which is what the original does, but a tuft is only ever cut once
** and a held X cannot re-cut the same one without a new swing. */
static void         cut_grass(const gameplay_input_t *in)
{
    unsigned int i;
    for (i = 0; i < KOKIRI_GRASS_COUNT; ++i) {
        const kokiri_prop_t *tuft = &kokiri_grass[i];
        int32_t dy, turn;
        if (in->room != tuft->room || (gameplay.grass_cut & (1u << i)))
            continue;
        dy = in->y - tuft->y;
        if (dy < 0) dy = -dy;
        if (dy > GP_SWORD_HEIGHT)
            continue;
        if (planar_squared(in->x, in->z, tuft->x, tuft->z) >
            (int32_t)GP_SWORD_REACH * GP_SWORD_REACH)
            continue;
        turn = yaw_delta(in->yaw, gameplay_facing(tuft->x - in->x,
                                                  tuft->z - in->z));
        if (turn < 0) turn = -turn;
        if (turn > 16384)
            continue;
        gameplay.grass_cut |= (uint16_t)(1u << i);
        /* One source-table roll per tuft, never rerolled by standing/swinging.
         * Tiny slice RNG; source odds, not the original global random stream. */
        gameplay.grass_rupee[i] = kokiri_grass_rupees[i][drop_random() & 15];
        gameplay.grass_age[i] = 0;
        gameplay.swing_hit = 1;
        ++gameplay.cut_count;
        gameplay.events |= GP_EVENT_CUT;
    }
}

static void         update_sword(const gameplay_input_t *in)
{
    if (gameplay.swing) {
        --gameplay.swing;
        if (gameplay_sword_active())
            cut_grass(in);
        return;
    }
    if (!in->attack)
        return;
    if (!(gameplay.equipped & GP_SWORD)) {
        /* No sword means no attack, not a substitute action. */
        gameplay.events |= GP_EVENT_DENIED;
        return;
    }
    gameplay.swing = GP_SWING_STEPS;
    gameplay.swing_hit = 0;
    ++gameplay.swing_count;
    gameplay.events |= GP_EVENT_SWING;
}

static void         update_shield(const gameplay_input_t *in)
{
    bool up = in->shield && (gameplay.equipped & GP_SHIELD) != 0 &&
              in->grounded && !gameplay.swing;
    if (in->shield && !(gameplay.equipped & GP_SHIELD))
        gameplay.events |= GP_EVENT_DENIED;
    if (up && !gameplay.shielding)
        gameplay.events |= GP_EVENT_SHIELD_UP;
    gameplay.shielding = up;
}

/* Slot table. Kept beside the menu rather than in the generated actor header:
** these are the slice's two equipment slots, not placement data. */
static const struct { uint8_t item; const char *name; const char *use; }
                    slot_table[GP_SLOT_COUNT] = {
    { GP_SWORD,  "Kokiri Sword", "X: swing" },
    { GP_SHIELD, "Deku Shield",  "Hold R: guard" },
    /* item 0: there is nothing to equip on this row. */
    { 0,         "Save",         "A: save to your file" },
};

uint8_t             gameplay_slot_item(unsigned int slot)
{
    return slot < GP_SLOT_COUNT ? slot_table[slot].item : 0;
}

const char         *gameplay_slot_name(unsigned int slot)
{
    return slot < GP_SLOT_COUNT ? slot_table[slot].name : "";
}

const char         *gameplay_slot_use(unsigned int slot)
{
    return slot < GP_SLOT_COUNT ? slot_table[slot].use : "";
}

bool                gameplay_is_paused(void)
{
    return gameplay.paused;
}

bool                gameplay_blocks_world(void)
{
    return gameplay.paused || gameplay.talking;
}

/* Pause inventory.
**
** Start opens and closes it. D-pad moves the cursor over every slot, owned or
** not, so a missing item can still be read and explained. A equips the slot
** under the cursor when it is owned; equipping something not owned is refused
** rather than silently ignored. B returns to the game. */
static void         update_menu(const gameplay_input_t *in)
{
    if (in->pause) {
        gameplay.paused = !gameplay.paused;
        gameplay.events |= gameplay.paused ? GP_EVENT_MENU_OPEN
                                           : GP_EVENT_MENU_CLOSE;
        return;
    }
    if (!gameplay.paused)
        return;
    if (in->cancel) {
        gameplay.paused = false;
        gameplay.events |= GP_EVENT_MENU_CLOSE;
        return;
    }
    if (in->menu_step) {
        int cursor = (int)gameplay.cursor + in->menu_step;
        if (cursor < 0)
            cursor = GP_SLOT_COUNT - 1;
        else if (cursor >= GP_SLOT_COUNT)
            cursor = 0;
        gameplay.cursor = (uint8_t)cursor;
        gameplay.events |= GP_EVENT_MENU_MOVE;
    }
    if (in->interact) {
        uint8_t item = gameplay_slot_item(gameplay.cursor);
        if (gameplay.cursor == GP_SLOT_SAVE) {
            /* Only the request is raised here. demo.c performs the device
            ** write and reports a failure back, because a save that silently
            ** did nothing is the worst outcome for the player. */
            gameplay.events |= GP_EVENT_SAVE;
        } else if (gameplay.owned & item) {
            gameplay.equipped |= item;
            sync_gear_to_save();
            gameplay.events |= GP_EVENT_EQUIP;
        } else {
            /* Nothing to equip: say so rather than pretending it worked. */
            gameplay.events |= GP_EVENT_DENIED;
        }
    }
}

bool                gameplay_is_talking(void)
{
    return gameplay.talking;
}

/* Which conversation a speaker owns. Children are matched on ENKO_TYPE -- the
** low 8 bits of the spawn param, exactly as EnKo_GetTextIdChild() reads it --
** so the line each child says is the one the original gives that child. */
static int16_t      convo_for(unsigned int npc)
{
    const kokiri_npc_t *person = &kokiri_npcs[npc];
    unsigned int kind = person->param & 0xFF;
    unsigned int i;
    for (i = 0; i < DIALOGUE_CONVO_COUNT; ++i) {
        if (dialogue_convos[i].speaker != person->kind)
            continue;
        if (person->kind != KOKIRI_NPC_CHILD ||
            dialogue_convos[i].kind == kind)
            return (int16_t)i;
    }
    return -1;
}

/* One extracted guard, evaluated against the save. */
static bool         cond_holds(const dialogue_cond_t *cond)
{
    bool held;

    switch (cond->kind) {
        case DIALOGUE_COND_EVENT:
            held = save_get_event_chk_inf(cond->flag);
            break;
        case DIALOGUE_COND_INFTABLE:
            held = save_get_inf_table(cond->flag);
            break;
        case DIALOGUE_COND_ITEMGET:
            held = save_get_item_get_inf(cond->flag);
            break;
        case DIALOGUE_COND_QUEST:
            held = save_check_quest_item(cond->flag);
            break;
        case DIALOGUE_COND_EQUIP:
            /* CUR_EQUIP_VALUE, not ALL_EQUIP_VALUE: Mido's gate turns on what
            ** is equipped, not what is merely owned. */
            held = (save_cur_equip_value(cond->flag) == cond->value);
            break;
        default:
            return false;
    }
    return (cond->expect ? held : !held);
}

/* The line a speaker actually says right now: the FIRST rule whose conditions
** all hold. That ordering is the whole point -- it is what the original's
** ladder of early returns does, so a later-quest line can never win on a fresh
** file. Returns a dialogue_rules index, or -1 when the speaker has nothing. */
static int16_t      rule_for(unsigned int npc)
{
    int16_t convo = convo_for(npc);
    const dialogue_convo_t *entry;
    unsigned int i, c;

    if (convo < 0)
        return -1;
    entry = &dialogue_convos[convo];
    for (i = 0; i < entry->rules; ++i) {
        const dialogue_rule_t *rule = &dialogue_rules[entry->first_rule + i];
        bool matched = true;
        for (c = 0; c < rule->conds; ++c) {
            if (!cond_holds(&dialogue_conds[rule->first_cond + c])) {
                matched = false;
                break;
            }
        }
        if (matched)
            return (int16_t)(entry->first_rule + i);
    }
    /* Every speaker's list ends in an unconditional rule, so falling out here
    ** means the extracted table is malformed rather than the quest being in an
    ** unexpected state. Say nothing rather than show a wrong line. */
    return -1;
}

unsigned int        gameplay_page_lines(void)
{
    const dialogue_rule_t *rule;
    if (!gameplay.talking || gameplay.rule < 0)
        return 0;
    rule = &dialogue_rules[gameplay.rule];
    if (gameplay.page >= rule->pages)
        return 0;
    return dialogue_pages[rule->first_page + gameplay.page].lines;
}

const char         *gameplay_page_line(unsigned int line)
{
    const dialogue_rule_t *rule;
    const dialogue_page_t *page;
    if (line >= gameplay_page_lines())
        return 0;
    rule = &dialogue_rules[gameplay.rule];
    page = &dialogue_pages[rule->first_page + gameplay.page];
    return dialogue_lines[page->first_line + line];
}

const char         *gameplay_speaker_name(void)
{
    if (!gameplay.talking || gameplay.speaker < 0)
        return 0;
    return dialogue_speaker_names[kokiri_npcs[gameplay.speaker].kind];
}

/* Who an A press would talk to. A live lock wins, so pressing A while targeted
** always talks to the actor being looked at; otherwise the nearest speaker in
** front within talk range. The OWNER position decides, not the fairy's bob. */
static int16_t      find_speaker(const gameplay_input_t *in)
{
    int32_t best = (int32_t)GP_TALK_RANGE * GP_TALK_RANGE + 1;
    int16_t found = -1;
    unsigned int i;
    if (gameplay.target >= 0) {
        const kokiri_npc_t *npc = &kokiri_npcs[gameplay.target];
        int32_t dy = in->y - npc->y;
        if (dy < 0) dy = -dy;
        if (dy <= GP_TALK_HEIGHT &&
            planar_squared(in->x, in->z, npc->x, npc->z) <=
            (int32_t)GP_TALK_RANGE * GP_TALK_RANGE)
            return gameplay.target;
    }
    for (i = 0; i < KOKIRI_NPC_COUNT; ++i) {
        const kokiri_npc_t *npc = &kokiri_npcs[i];
        int32_t distance = planar_squared(in->x, in->z, npc->x, npc->z);
        int32_t dy = in->y - npc->y, turn;
        if (dy < 0) dy = -dy;
        if (dy > GP_TALK_HEIGHT || distance >= best)
            continue;
        turn = yaw_delta(in->yaw, gameplay_facing(npc->x - in->x,
                                                  npc->z - in->z));
        if (turn < 0) turn = -turn;
        if (turn > 16384)
            continue;
        best = distance;
        found = (int16_t)i;
    }
    return found;
}

/* One press does one thing. A opens, then advances, then closes on the last
** page; B closes early. The opening press is consumed by the open, so it
** cannot also skip page one, and every transition needs a fresh press edge. */
static void         update_talk(const gameplay_input_t *in)
{
    if (gameplay.talking) {
        const dialogue_rule_t *rule = &dialogue_rules[gameplay.rule];
        gameplay.prompt = -1;
        if (in->cancel) {
            gameplay.talking = false;
            gameplay.speaker = -1;
            gameplay.rule = -1;
            gameplay.events |= GP_EVENT_TALK_CLOSE;
            return;
        }
        if (!in->interact)
            return;
        if (gameplay.page + 1 < rule->pages) {
            ++gameplay.page;
            gameplay.events |= GP_EVENT_TALK_PAGE;
            return;
        }
        gameplay.talking = false;
        gameplay.speaker = -1;
        gameplay.rule = -1;
        gameplay.events |= GP_EVENT_TALK_CLOSE;
        return;
    }
    gameplay.prompt = find_speaker(in);
    if (!in->interact || gameplay.prompt < 0)
        return;
    gameplay.rule = rule_for((unsigned int)gameplay.prompt);
    if (gameplay.rule < 0)
        return;
    gameplay.speaker = gameplay.prompt;
    gameplay.page = 0;
    gameplay.talking = true;
    gameplay.events |= GP_EVENT_TALK_OPEN;
}

void                gameplay_step(const gameplay_input_t *in)
{
    gameplay.events = 0;
    /* Pause outranks everything, including an open text box: Start freezes the
    ** world wherever it is. Nothing below runs while the menu is up, so no
    ** menu press can reach a swing, a jump, a talk or the walk/run toggle. */
    if (gameplay.paused || in->pause) {
        update_menu(in);
        if (gameplay.paused) {
            gameplay.shielding = false;
            gameplay.prompt = -1;
            return;
        }
        /* Closed this step: the same press must not also act on the world. */
        return;
    }
    /* A conversation owns the input. Nothing else in the world advances from
    ** the pad while a box is open -- no pickup grab, no lock change, no swing,
    ** no guard -- so a held button cannot leak an action through the box. */
    if (gameplay.talking) {
        update_talk(in);
        gameplay.shielding = false;
        return;
    }
    collect_pickups(in);
    collect_rupees(in);
    update_target(in);
    update_talk(in);
    if (gameplay.talking) {
        /* Opened this step: drop anything the same frame would have started. */
        gameplay.shielding = false;
        return;
    }
    (void)drop_random(); /* vary outcomes with play timing, even before a cut */
    update_sword(in);
    update_shield(in);
}
