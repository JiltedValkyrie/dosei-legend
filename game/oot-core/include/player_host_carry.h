#ifndef OOT_PLAYER_HOST_CARRY_H
#define OOT_PLAYER_HOST_CARRY_H

/* An Actor identity for a host-owned rock/pot, not a second Player. Source
 * Player owns admission, putting away equipment, pickup/throw animations,
 * hand attachment and release velocity. Host keeps prop physics and drops.
 * Only copy values across CPUs; never expose a host actor pointer. */
static Actor sCarryActor;
static unsigned int sCarryHandle;
static bool sCarryAttached;
static void OotCore_CarryAlive(Actor*, PlayState*) {} /* Player lifetime guard */

static void OotCore_CarryReset(void) {
    sCarryActor = {};
    sCarryHandle = 0;
    sCarryAttached = false;
}

static bool OotCore_CarryEngaged(Player* player) {
    return player->heldActor == &sCarryActor ||
        ((player->stateFlags1 & PLAYER_STATE1_CARRYING_ACTOR) &&
         player->interactRangeActor == &sCarryActor);
}

/* The offer branch of EnIshi_Wait / ObjTsubo_Idle. Host candidates are a
 * superset; these ranges and Player's own facing test decide admission. */
static void OotCore_CarryOffer(PlayState* play) {
    Player* player = GET_PLAYER(play);
    if (!sCarryHandle || sCarryAttached || OotCore_CarryEngaged(player)) return;
    sCarryActor.xzDistToPlayer = Actor_WorldDistXZToActor(&sCarryActor, &player->actor);
    sCarryActor.yDistToPlayer = player->actor.world.pos.y - sCarryActor.world.pos.y;
    sCarryActor.yawTowardsPlayer = Actor_WorldYawTowardActor(&sCarryActor, &player->actor);
    if (sCarryActor.id == ACTOR_OBJ_TSUBO) {
        s16 turn = sCarryActor.yawTowardsPlayer - player->actor.world.rot.y;
        if (sCarryActor.xzDistToPlayer < FXL(100.0f) && ABS(turn) >= 0x5556)
            Actor_OfferGetItem(&sCarryActor, play, GI_NONE, FXL(30.0f), FXL(30.0f));
    } else if (sCarryActor.xzDistToPlayer < FXL(90.0f)) {
        if (sCarryActor.params & 1) /* ROCK_LARGE; Player gates strength */
            Actor_OfferGetItem(&sCarryActor, play, GI_NONE, FXL(80.0f), FXL(20.0f));
        else
            Actor_OfferGetItem(&sCarryActor, play, GI_NONE, FXL(50.0f), FXL(10.0f));
    }
}

/* Called after each source draw, including both updates in a catch-up batch. */
void OotCore_CarryAfter(PlayState* play) {
    if (sCarryHandle && sCarryActor.parent == &GET_PLAYER(play)->actor)
        sCarryAttached = true;
}

int OotCore_CarryCommand(PlayState* play, unsigned int command, int* io) {
    Player* player = GET_PLAYER(play);
    if (command == OOT_CORE_TOOL_CARRY_CANCEL) {
        if (player->heldActor == &sCarryActor) player->heldActor = NULL;
        if (player->actor.child == &sCarryActor) player->actor.child = NULL;
        if (player->interactRangeActor == &sCarryActor) {
            player->interactRangeActor = NULL;
            player->stateFlags1 &= ~PLAYER_STATE1_CARRYING_ACTOR;
        }
        OotCore_CarryReset();
        return 1;
    }
    if (command == OOT_CORE_TOOL_CARRY_OFFER) {
        if (sCarryAttached || OotCore_CarryEngaged(player)) return 0;
        if (player->interactRangeActor == &sCarryActor) player->interactRangeActor = NULL;
        OotCore_CarryReset();
        sCarryHandle = (unsigned int)io[0];
        if (!sCarryHandle) return 0;
        sCarryActor.id = io[1];
        sCarryActor.world.pos.x = io[2];
        sCarryActor.world.pos.y = io[3];
        sCarryActor.world.pos.z = io[4];
        sCarryActor.world.rot.y = sCarryActor.shape.rot.y = io[5];
        sCarryActor.params = io[6];
        sCarryActor.category = ACTORCAT_PROP;
        sCarryActor.update = OotCore_CarryAlive;
        return 1;
    }
    if (command != OOT_CORE_TOOL_CARRY_READ || !sCarryHandle) return 0;
    int state = sCarryAttached ? (sCarryActor.parent ? 2 : 3) :
                OotCore_CarryEngaged(player) ? 1 : 0;
    io[0] = (int)sCarryHandle;
    io[1] = (int)sCarryActor.world.pos.x;
    io[2] = (int)sCarryActor.world.pos.y;
    io[3] = (int)sCarryActor.world.pos.z;
    io[4] = sCarryActor.world.rot.y;
    io[5] = (int)(sCarryActor.speed * FXL(256.0f));
    io[6] = (int)(sCarryActor.velocity.y * FXL(256.0f));
    if (state == 3) OotCore_CarryReset(); /* one release; host owns flight */
    return state;
}
#endif
