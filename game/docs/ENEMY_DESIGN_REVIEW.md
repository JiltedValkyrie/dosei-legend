# Enemy groundwork source review, 2026-10-08

This records source/design evidence, not actor imports or runtime acceptance.

## Q1: fixed-address packs

Use a two-pass fixed link at the top of the existing scene carve. First link
measures aligned text/data/BSS; the final link uses carve_end minus that size
and rejects growth. Use the same SH-2 GCC 9.3 flags and raw C++ symbols as the
resident core, with `--just-symbols` plus object symbols. Bind packs to the
exact core binary CRC taken before core constructors change its data. A stale
core or wrong base fails before registration. No inferred two-base relocation.

Keep `.init_array`/`.ctors`, zero BSS and run constructors before publishing
profiles. The current core map contains mangled functions, `_GLOBAL__sub_I_*`
constructors and local `.data._ZL14sDoorLocksInfo`; `-fdata-sections` does not
make those statics safe to duplicate. Reject blanket weakened engine objects.
Pack-only TUs must explicitly declare exports; stateful engine helpers stay
resident. A future copied helper needs a relocation audit proving no engine
static dependency. W0a imports no actors and retains no extra engine helper.

## Q2: registration and lifetime

Register validated pack profiles as internal overlay entries, with NULL
vramStart/loadedRamAddr. The original spawn branch then uses their profiles
without allocating/freeing fixed cart memory. Range/null guards apply before
table access; internal actor `numLoaded` increments/decrements symmetrically.
The count is signed 8-bit in source: unloading also scans actual live actors
and may not rely on that count alone.

Stop core consumers before replacing scene/object/code memory. Destroy actors
while their destroy functions and objects still exist, delete each live
EffectSs row, then clear EffectSs and hard effects, reset tool/collision/view
owners and unregister profiles. Source `EffectSs_ClearAll` nulls its table
before its delete loop, so calling it alone misses cleanup. Reject unload with
live pack actors/effects. Failed loads remain in an explicit safe loading
error state; never continue gameplay through stale pointers. Old-state reload
is an allowed future rollback path, not a claim that W0a restores it.

## Q3: semantic Update-side anchors

Reject the draft Draw/limb-matrix replay. It violates the permanent ban on
runtime skeleton evaluation, pose-track loads and head tracking for sprite
actors. Derive small 32-bit gameplay points/radii/quads from offline FK, keyed
by gameplay clip clocks. Patch each imported actor's Update-side anchor work
and retain source cull predicates and once-per-core-step timing. No hierarchy,
limb transforms or visual pose tracks in runtime objects.

Required pilot audit examples: En_St Draw performs stick/body tests and its
PostLimbDraw updates spheres (`z_en_st.c:1108,1114`). En_Test PostLimbDraw sets
sword/shield/feet/ice anchors, while Draw changes colour/ice clocks
(`z_en_test.c:1887-1981`). En_Wf PostLimbDraw sets spheres/tail and Draw changes
fire/colour clocks (`z_en_wf.c:1395-1478`). Their head overrides stay disabled.
List and test every moved gameplay side effect per actor; simply suppressing
Draw is not an enemy conversion.

## Q4: BodyBreak completion

The five sprite actors waiting on `BodyBreak_SpawnParts` are:

| Actor | Source call lines | Gameplay after completion |
| --- | --- | --- |
| En_Bb | z_en_bb.c:509 | Random table 13 drop, death |
| En_Sb | z_en_sb.c:471 | Table 8 or Wind Arrow ammo drop, kill |
| En_Skb | z_en_skb.c:407,443 | Nonlethal head-break flag progression; size-dependent drops and kill |
| En_Test | z_en_test.c:1522,1648 | Reassemble/revive or table 13 drop, parent counter, kill |
| En_Tite | z_en_tite.c:787 | Blue table 14/red table 4 drop, kill |

Paths are `src/overlays/actors/ovl_<actor>/` in the local OoT source.
Boss-category `En_Ik` also calls it (`z_en_ik.c:673`) for armor; preserve its
mesh/BodyBreak behavior under the boss exemption.

`z_actor.c:3650-3759` allocates matrices, display-list pointers and object slots;
Draw's `BodyBreak_SetInfo` makes the state ready. Suppressing Draw alone hangs
these waits. Sprite imports must use an allocation-free completion shim with
bounded puff/debris views and an explicit state transition.

An unconditional immediate-success shim is insufficient for Stalfos. In
`func_80862E6C` (`z_en_test.c:1516`), the actor copies `bodyBreak.count` into
`home.rot.x`, then sets a child handshake after spawning parts. En_Part types
12/13 wait 60/460 ticks and return to the source position, decrementing the
parent counter (`z_en_part.c:64-73,228-254`). The parent revives only once this
counter reaches zero; type 5 also checks whether another live Stalfos remains.
Preserve this delay/counter/room-clear gameplay with an explicit bounded clock
and parent lifetime handling. Do not retain character limb models or make the
room clear instantly. Require tests for type 4/5 revival, simultaneous defeat,
parent deletion and exactly-once drops, plus Stalchild nonlethal head-break.

## Q5: ZeldaArena and THA admission

Retain existing capacities: ZeldaArena `0x20000` (131072 B), THA `0x30000`
(196608 B), from `oot_core_api.h:28-29`. No automatic growth or claim that the
full enemy set fits. Source room lists already exceed the 64-entry staging
array: Goron City cutscene 89, Kokiri 78, Field 73, Zora's River 66, Fire Temple
room 10 62. These are placement counts, not simultaneous live actor peaks.

`BgCheck_Allocate` (`z_bgcheck.c:1550-1669`) reserves scene-specific static
lookup/node storage and dynamic collision storage. Largest default source
budget is `0x1CC00` (117760 B), with the CollisionContext already inside
PlayState subtracted in the formula. Add the 85-element EffectSs table
(`oot_core_api.cpp:289`, `z_effect_soft_sprite.c:31`) and allocation alignment.
Source arithmetic is compatible with the 192 KiB carve, but target `sizeof`
and actual allocation/high-water reports must certify each scene. Existing
host bgcheck probe uses a 1 MiB THA, so its success is not a 192 KiB fit test.

Dynamic collision has separate ceilings: 512 polygons, 512 vertices, 1000
nodes (shop/fixed-camera branch 256/256/500). Admission must check these too.
THA allocation routines only move pointers and can return an out-of-carve
address before any caller notices; `THA_IsCrash` alone after initialization is
too late. Add checked allocation/admission before enabling content.

ZeldaArena needs target compiled actor sizes, allocator header and 16-byte
rounding, resident Player/tools, collider allocations, spawned children,
drop bursts and retained/adjacent-room actors. BodyBreak matrices must not be
charged to sprite actors after replacement, but boss allocations remain.
Unknown dynamic multiplicity or missing compiled size is an unresolved
budget, never zero. Roster admission must fail until those values and the
largest-free-block requirement fit. Static roster generation may emit the
unresolved evidence; it must not publish a ready scene from that inventory.

## W0a roster/audio evidence

Coverage is regenerated from overlay-table identity rather than a profile's
sometimes deliberately different declared id. All 429 profiles resolve;
26 source profiles are imported in the existing tree. Enemy inventory has 98
scoped actors, exactly 20 ACTORCAT_BOSS profiles, and 65 conservative scene
candidates (1089 effective room/layer rows). Includes support props, boss
dependencies and dynamic spawn candidates, not a claim of 65 enemy scenes.
The human-approved 20 registration prefixes are recorded separately.
`spot15` (Hyrule Castle) is one additional nonboss candidate through gold
Skulltulas/Cucco revenge; registration there has not been added to this task.
Boss-only `bdan_boss`/`moribossroom` and cutscene `hiral_demo` are the other
unregistered candidate rows outside those 20. No scene is marked ready.

Source helpers resolve En_Encount1's finite `spawnId` assignments to both
Stalchild/Wolfos. Unknown expressions and unmeasured dynamic peaks remain
explicit. `--require-ready` fails when spawn identities, actor sizes/peaks,
THA use or runtime acceptance are unresolved. SPR2 inventory accounts for
object+skeleton archives and their largest live cel.

The H generator renders source channels at 5512.5 Hz into scene ESF1 libraries
and emits per-room id/slot/cart-to-sound-RAM copy maps. It counts sample guards,
alignment, headers and retained non-enemy area sounds. Missing/unsupported
sounds or byte overages prevent publishing any requested library. The
runtime enemy library load/copy/dispatch remains unimplemented; these generated
maps alone do not complete H.

Actual local-source probe:
`python game/tools/build_enemy_audio.py --scene spot03 --cart-budget 262144`.
All selected source channels rendered, but River room 0 layer 0 needs 208892 B
against SFX_AREA_LIMIT 79462 B, including conservative retained area 78510 B.
Even removing that reservation leaves 130382 B; the source candidate union
cannot be admitted as-is. Per-layer/params reachability, shorter source tails
and/or lower-rate individual assets need measured resolution during content
rollout. No sound was silently dropped and no bank published.

Seven focused audio tests pass in WSL, including compiled actual C dispatch
against the generated nine-entry resident mapping. The replacement preserves
all original known-id behavior and ignores unknown ids. Nine roster tests and
eight coverage tests pass. No runtime acceptance follows from these
host checks; no enemy actor source was imported by these tools.
