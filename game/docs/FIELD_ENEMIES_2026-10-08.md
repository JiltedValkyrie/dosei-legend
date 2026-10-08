# Hyrule Field enemy implementation

Human now requests Hyrule Field decomp enemies ahead of the earlier scene-wave
order. This changes implementation order, not the fixed-point, source-gameplay,
sprite, reward or capacity requirements. Mandatory Player migration remains open.
User explicitly requires era/time-correct spawning. Retail Field layers 0/1
contain seven Peahat parents and one Stalchild spawner; layers 2/3 contain ten
Poe placement points. Cutscene layers contain none of these actors. Source
Stalchild night/Bunny Hood/terrain checks and Peahat day/night actions stay live.
After Field, the user queued Water Temple enemies, obstacles and puzzle actors.

Source scope: En_Encount1 (Field parameters select Stalchildren), En_Skb,
En_Peehat (grounded/flying parents and dynamic larvae), En_Po_Field (adult
Poes and their soul/bottle flow). Other En_Encount1 modes are not Field spawns.
Use a scene-owned OAP and the existing clock-only SPR2 path. No enemy mesh
rendering, skeletal evaluation or joint/morph allocation at runtime.

Current status: source/backend implementation and target integration in progress. The focused source
probe passes Stalchild spawn gates, Peahat day/night transitions and Stalchild
drop completion. Four actor translation units and the sprite/pack helpers compile
with the WSL SH-2 toolchain; 14 offline anchor clips were generated. This is not a
complete playable-image acceptance. The actor/effect pack now links and its SH-2
audit passes (119 permitted hardware multiply sites, zero forbidden helpers).
Pack memory is 40,256 bytes; Field OOC + six OOBs + pack is 136,336 bytes,
leaving 125,808 bytes in the unchanged scene carve. Child/adult enemy audio banks
use 34,318/46,462 bytes of the existing 57,986-byte sound area, at 2,756.25 Hz;
complete one-shot tails and one pass of held loops are retained. Source channel
tails are expanded offline; synthesis remains the existing approximate renderer.
Poe flame views, soul billboard facing and scaled enemy bounds are implemented.
Views/cel slots now accommodate 32 entries inside existing memory/texture carves;
the target compile checks the low-RAM draw structure. Full population/runtime
heap acceptance is still open. Nine renderer checks and the 59-case focused
regression batch pass. Broad legacy discovery is not green (1,495 tests, two
failures, 352 errors, 643 skips); its stale harness/assets are not acceptance.
Human runtime evidence: user says "Looks good" and shows adult Field with
"You defeated Poe the ghost!" source dialogue, VRAM 51%, CPU~82%. This accepts
the shown Poe defeat/soul-dialogue presentation; child spawn cases, capture,
horseback Big Poes and full population/load-time acceptance remain unverified.
The usual Clean test disc now contains Field:
84,131,840 bytes, 1,461 mastered files matching staging, API25 and one OAP.
SHA256 `b62a08869df52cc08072962baa4bff6c0efeb3451e5903099d2461d6d8428eda`.
Both live binaries pass the math audit (main 599/core 1,400 allowed hardware
multiply sites, zero forbidden sites); pack audit also passes. .bss ends at
0x06083400, leaving 3,072 bytes below SGL after redistributing the unchanged
48,128-byte non-cart heap between high and low WRAM. Field sprite archives use
479,243 heap bytes including terminators, before allocator overhead. Human was
asked to check child night/day and adult Field, attack visibility, drops and
missing sprites. Final focused batch: 72 cases pass. Source probe passes; five targeted Field host cases cover
retail layers, bank bounds, source channel tails, bottles and scaled culling.

Follow-up found after this image: Field sound selection compared runtime
save-scene 10 to source scene 81. Code now uses SCENE_SPOT00; the fix awaits the
next target/disc rebuild. Kronos is running, so do not replace its mounted image.

Required source draw side effects: Stalchild body/attack spheres and bounded
head/death break completion; Peahat weak-point sphere, blade tips and blade
quad; Poe lantern anchor at death frame 27. Preserve original damage tables,
spawn/despawn conditions, parent counters, drops and soul rewards. Audit audio,
effects, targeting, full scene/era populations and resource budgets before staging.
Big Poe capture additionally depends on the unfinished Player/bottle integration;
do not claim full Field completion while that path is missing. Stalchild part
collection uses a bounded two-update completion gate rather than runtime limb
matrices; detached mesh debris is not reproduced. Peahat blade anchors use cheap
rotated bounds; weak-point and Poe lantern anchors use offline source frames.

Next requested integration test: Water Temple. Inventory original room actor
lists and object dependencies before importing enemies, moving obstacles and
puzzle actors. Test water levels, switches, locked doors, keys, room-clear
conditions and item-dependent traversal together. Keep non-boss enemies on the
sprite backend; bosses retain the existing model/hitbox exemption. Record code,
host tests, target build and human playthrough separately. Water Temple work
has not started; adding its actors alone will not establish a playable dungeon.
