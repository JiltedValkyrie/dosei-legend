# Feedback and audio source audit ? 2026-09-30

Implementation audit, not human listening/visual acceptance. Source root:
`D:/Workspace-Claude/game-decomps/n64/oot`, US ntsc-1.2. Current image:
`game/build/game-clean.cue`. No emulator launched by agent.

## Implemented in this pass

| Behavior | Original source | Port / verification |
|---|---|---|
| Enemy damage and stun visibility | `z_actor.c Actor_SetColorFilter`; `z_eff_ss_dead.c`; En_Dekubaba, En_St, En_Sw, En_Goma, En_Hintnuts | Per-actor red damage / blue stun timers, immutable VDP1 RGB-offset tables. Source durations converted 20->30 Hz; rejected hits do not tint. Baba pruning clears stale blue reaction. Shared mesh attributes restored after submission, including rejected submissions. |
| Link hurt visibility | `z_player.c Player_Draw`, positive invincibility timer, red fog driven by cosine | Red pulse after actual damage; rate increases near expiry, resets on scene reset/death. Falling uses its 40-frame hurt duration. No flash for unrelated intangible actions. |
| Chest opening | `z_en_box.c` big-chest opening branch, `NA_BGM_OPEN_TRE_BOX`; child `gPlayerAnim_clink_demo_Tbox_open` | Previously track existed but no runtime call. Large chests now align Link, run imported child opening pose and chest animation, hide reward text, play CHEST CD track, then queue major-item fanfare. World/streaming stop before CD starts; presentation uses independent 60 Hz clock. Small chest types 5/6/7/8 omit opening song. |
| Major chest / shop acquisition | `z_player.c` get-item branch; `EnOssan_GiveItemWithFanfare` | New named ITEM_GET sequence 34 / soundfont 35 track. Sword, map, compass, slingshot and successful shop fanfare transactions trigger it. Failed/repeat quick purchases do not. |
| First stick/nuts / Gold token | Player get-item; `z_en_si.c` | First ammo now uses ITEM_GET, correcting prior first-stick SMALL_ITEM substitution. Gold token uses existing SMALL_ITEM track. |
| Minor chest pickup | Player rupee/recovery-heart branch | `NA_SE_SY_GET_BOXITEM` source channel `CHAN_5CB9`; no major-item song. |
| Puzzle success / reveal | `ObjSwitch_SetOn/SetOff` | `CHAN_5833` correct chime and `CHAN_589F` appear cue alongside physical switch click. ONCE=0 / SYNC=4 use correct chime. |
| Shutter movement | `z_door_shutter.c` open/close | Source `CHAN_1A7E` / `CHAN_1B14` at lift start and closed endpoint. |
| Stun / landing impact | Enemy freeze channels; Player landing BODY_HIT | `CHAN_4C1B` freeze and now-renderable `CHAN_0753` body hit replace missing/stand-in cues. Offline renderer follows bounded layer calls, not just tail jumps. |
| Existing enemy sounds | Previous dungeon-bank repair | Scrub rise/burrow/spit/walk/hit/faint, Baba/Skulltula/larva/Gohma hit/death, shield reflect and nut break retained. Tree bank 2; boss bank 3 leaves room for new effects. |

## Required parity work still open

- Saturn RGB addition approximates original fog; enemy fade curve is quantized
  and linear. Gohma currently uses general red hurt tint rather than its full
  original eye/body material state. Hit sparks, finishing-blow hitstop,
  particles and outside Karebaba's complete death presentation remain.
- Chest camera is a bounded fixed-point adaptation of Camera_Demo3's opening
  orbit, not the complete original multi-stage camera. Chest light/rays and
  original held-up map/compass/slingshot models remain. Imported root motion
  stays in the posed mesh during the frozen scene; exact floor/hand alignment
  and transition need human review. Waiting for the complete CD track extends
  the final opening pose before item presentation.
- Web wobble/break/burn (notably looping `CHAN_2416`), torch ignition/fire loop,
  water/platform/ladder/block movement and mechanism attention-camera timing
  still need source audio and lifecycle integration.
- Boss walk/ceiling/cry/eye attack, full death loop, warp audio and Emerald /
  medallion story fanfare belong to unfinished boss/aftermath presentation.
  Do not mark them complete because hit/death one-shots now play.
- Ocarina/story/minigame/Meadow/Field fanfares remain tied to unfinished M6/M7
  actors and sequences. No fabricated triggers or progression bypasses added.
- Reduced offline SFX synthesis still omits complete glide/legato/vibrato,
  synthesis and reverb behavior. Rendered source notes are not audio identity.

## Budgets and evidence

Core ACTIONS 107,684 bytes; area capacity 88,924. Forest 50,298; Tree 78,510
(10,414 spare); boss 54,180. Tint tables add 256 VDP1 bytes, zero sprite slots.
Forest room 1 retains 34,432 bytes; boss room 1 retains 66,064 bytes. Actor pool
still fits its 8 KiB carve. Link animation appends clip 120, preserving IDs.

346 focused host checks pass; earlier 8 source prop-asset checks also pass.
Chest/CD queue, bounded pose frame, tint restoration, actual actor hurt/stun
contacts, Link reset, reward transaction events and source bank budgets covered.
Clean build/master passes: BSS end `0x06083f70`, 144 bytes below SGL; heap 51,200,
SGL 3,750 polygons / 3,200 vertices retained. Initialized fog lookup moved to
reserved low work RAM; cold loaders/UI/state bookkeeping use size optimization.
379 ISO files; boot, animation and all affected PCM banks match staging.
15 changed target objects contain no matched software-float helpers.
Logs: `feedback-build.log`, `feedback-final-tests.log`, `feedback-vram-check.log`,
`feedback-disassembly-check.log`, `feedback-artifact-check.log` under `game/build/`.

Human check: fresh unopened sword/Tree chest; opening pose/song, then item
song/text; buy shield; failed/quick purchase; token; red hit/blue stun and Link
pulse; switch/door effects; end of song restores bank and input. Listen to the
usual CUE with TRACK02?TRACK06 beside it. Save flags keep already-opened chests
open; they must not replay acquisition rewards on reload.
