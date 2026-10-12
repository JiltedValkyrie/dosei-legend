# Debug performance overlay (Debug image, 2026-10-09)

Combined Astra batch diagnostic fallbacks (2026-10-12): `dosei_sign_slow`
bit 0 disables sign view culling (default 0). Sliced meshes are retired by
human direction: hit signs now fade and disappear. `actor_resolve_slow=1`
forces the original validated full scan.
These are debugger-visible globals, not gameplay draw-removal masks.
`CART_ACTOR_POOL=1` is a build-time fallback to the reserved uncached cart
pool; default 0 uses high WRAM. Never flip pool ownership on a running game.
Job-order toggle now cycles M/P/C (see below). Compare whole frames and rows 9, 13, 16-20
in the same camera idle/moving; validate intact signs, hit fades and reloads.
Human now asks Astra to compare all modes; M being preferred earlier is not
a controlled result. The authorized `--perf-kokiri` test image bypasses menus
through the same child room-0 Play Test entry, retaining ordinary gameplay.
Testing now runs on a private background desktop with isolated keyboard
bindings. Never bring it forward while the human plays; normal config restored
on close. Startup can take minutes; loading screens are not timing samples.

Build: `./build.sh OOT_CORE=1` -> `build/game.cue` (Debug Mode in the
launcher). The Clean image only shows the bottom `VRAM / CPU~` line.
Code: `src/main.c` `diagnostic_overlay` (rows 0-2, 7-13; rows 3-6 sit under the heart/magic HUD) and the always-on heap
row 27. Refresh: 4 times a second (VDP2 keeps the text). L+R toggles the
older full debug page (`debug_visible`).

Rows 10-20 and 22 (2026-10-12) show the per-frame mean over the last refresh window
(~0.25 s), not one frame. All times are **0.1 ms** units (e.g. `mv250` = 25.0 ms). One 30 FPS frame is
333; 60 FPS is 167.

| Row | Fields | Meaning |
| --- | --- | --- |
| 0 | `fr wk sy` | `fr` whole frame = `wk` CPU work in the frame callback + `sy` wait for VDP1/VBlank. `sy` near 0 with `wk` high = CPU bound; `sy` high = VDP1 fill bound. |
| 1 | `mv sk sc lk ot` | Host phases (`frame_timer.h`): `mv` gameplay step (input, `gameplay_step`, **the core update**, camera, doors), `sk` Link skinning (`link_anim_pose*`), `sc` scene cull/submit, `lk` Link submit, `ot` everything not named (NPC sprites, HUD, text, audio). |
| 2 | `cu a/b/c/d pd` | Core, per 20 Hz update (`oot_core_update_us`): `cu` total; then `gOotCorePhaseUs` collision checks (CollisionCheck_AT/OC/Damage) / actor updates (Actor_UpdateAll incl. the real Player) / messages+environment / draw shim (Actor_DrawAll capture); `pd` real Player anchor draw pass (Player_Draw pose split, `oot_core_draw.cpp`). |
| 7 | `top id x n ...` | The 3 actors with the most update time last step: actor id (hex) x 0.1 ms (`OotCore_ProfiledUpdate`). Player = `0`. Replaced by tool text while a Link tool actor is live (`OotCore_ToolDebug`). |
| 8 | `bgq rb a p/n/e/pr/m s` | `bgq` host `bg_*` collision queries since the last refresh (CORE_COLLISION shim), `rb` proxy DynaPoly rebuilds (`DynaPoly_UpdateContext` from C prop moves), `a` core actor counts player/NPC/enemy/prop/misc (ACTORCAT 2/4/5/6/8), `s` runtime scene index, `fd` 1 while static scene collision is read from the optional Work-RAM copy. Current main only queries `bg_core_fast_data(-1)`; no automatic Debug alternation or Clean enable. |
| 9 | `gs co cm st n` | PLAYER_SOURCE host step split, summed over the last frame's catch-up steps: `gs` gameplay_step (C gameplay, pause, C actors' contacts), `co` core frame (`oot_core_frame`: input, save mirror, **core update**, player read, room/sprite refresh), `cm` camera update (core line/floor tests), `st` whole step loop, `n` steps this frame (capped 4: a slow frame does more steps). `st - gs - co - cm` = everything else in the step. |
| 10 | `nc wp en at bb tk it rc` | `gameplay_step` split (`src/perf_sub.h`, summed over the frame's steps): `nc` exit blocker + NPC sync, `wp` world props + rupees + wonders, `en` boulder/nut/Mido, `at` target + attention + Navi, `bb` Deku Babas, `tk` chest/prop interact/talk, `it` items/sword/shield, `rc` contacts. |
| 11 | `pr po ac dp nv` | PLAYER_SOURCE step outside gameplay_step/core/camera: `pr` before gameplay_step (dyna step, webs, doors, Gohma notice), `po` story/tree mouth/first-person/events, `ac` C puzzles + `actor_sys_update`, `dp` prop/door/Mido/boulder push of Link, `nv` Navi hover. |
| 12 | `ks dg da ui ru` | Frame (main.c): `ks` `kokiri_scene_update` (room portals), `dg` grass/rupee/boulder draw, `da` nut/baba/NPC/story/item/fairy draw, `ui` fade, dialogue, text, menus, HUD, reticle, minimap, `ru` whole `recomp_update` (contains `st` and `sk`). |
| 13 | `nb np wc wp wr pl fy` | Inside `da`: `nb` nut + Deku Babas, `np` `npc_draw` (contains `wc` + `wp` + `wr` + `pl`), `wc` `oot_core_meshes_draw` (core sprites, tools, effects, meshes), `wp` C world props (pots, rocks, bushes, stones), `wr` the rest of world_props_draw (drops, signs, bosses, Gohma, babas, chests), `pl` npc_draw's shopkeeper/NPC sprite loop, `fy` Kokiri fairies. |
| 14 | `r0 r1 pd dw` | `recomp_update` outside the step loop: `r0` before it (input, modes), `r1` after skinning (owl camera, sky gradient, layers); inside `pr`: `pd` webs/puzzles sync; inside `dp`: `dw` world_props_displace + push move. |
| 15 | `as k ov jw cv bv dr` | Async core (slave SH-2): `k` updates in the last job, `ov` master time between kick and join (0.1 ms), `jw` master wait at the join, `cv` master core entries while busy (must be 0), `bv` C collision queries refused while busy (shadow misses are deferred, not refused), `dr` master wait for SGL's slave queue to drain before the forest submit (0.1 ms). |
| 16 | `fps vb W pr sk jn dr` | `fps` displayed frames per second and `vb` VBlanks per frame, both from the 60 Hz VBlank clock (no FRT), averaged over the last refresh. Then master time spent waiting for the slave last frame: `pr` scene prepare (`prep_wait`), `sk` Link skin (`link_anim_sync`), `jn` core join, `dr` SGL queue drain. |
| 17 | `S pr cu sk %` | Slave job times last frame: `pr` scene prepare, `cu` core update, `sk` Link skin, then their share of the frame. SGL's own slave polygon transforms are not counted. |
| 18 | `pd pp pf ft cel K sb` | `sb` (end) = forest submission on the master, including the master's own transform when SGL keeps it off a busy slave. Scene prepare phases last frame (either CPU): `pd` depth, `pp` cull/partition/sort, `pf` fog; `ft` fog tiles rewritten (16 VDP1 palette writes each); `cel` NPC/prop sprite cel copies into VDP1 VRAM (`npc_sprite_bind_sample`, 0.1 ms) and their size in KB. |
| 19 | `spr n sh put rs` | Sprite actors last frame: `n` drawn, `sh` shadow lookup + shadow submit, `put` slPutSprite, `rs` shadow floor queries resolved after the core join (`kokiri_shadow_resolve`). |
| 27 | `heap w c f sp` | Work-RAM zone live/peak bytes, cart zones peak KB, failed allocations, sprite peak. |

Row 21 (source Player): `pHHHH iHH/HH/HH gHHHH cHH/HH fHHHHHHHH`.
Hex values: `p` retains the last delivered source press; `i` is live held item,
held action and current item action; `c` is C-left item/status; `f` is live
stateFlags1. `g` is an item-gate blocker bitmap: bits 0 CanUpdateItems false,
1 category, 2 changing item, 3 action mismatch without shielding, 4 health,
5 scripted cutscene, 6 Player cutscene action, 7 gallery, 8 non-main camera,
9 transition, 10 stopped timer, 11 carrying/STATE1_29, 12 missing hookshot child,
13 disabled/empty C-left, 14 STATE1_0/dead, 15 swimming. Zero means these gates
allow selection; it does not prove the current action called UpdateItems.
A press is 8000, X 4000, C left/down/right 2/4/1. Live reads occur after joining
the core. No Player tick instrumentation or gameplay changes. Dialogue refresh
remains unchanged; values on a frozen dialogue overlay are not live.

Row 22 `hud q hp vis a b v`: prompt/state queries, health/magic draw, and map/button/
pause visibility, all in 0.1 ms. These cover minimap_layer_flags inside row 14
`r1`; sky/layer work outside that function remains in `r1` only.
`a`/`b` are the joined host Player aim-mode/item-button fields; `v` is the host
first-person predicate. These are states, not times. Row 15 `cvN@line` adds
the last unsafe core ENTRY call's source line in oot_core_host.c; inspect that
call site before attributing a nonzero count to a race. The count resets at
refresh, so the line only has meaning when the count is nonzero.
Row-1 phase timers retain their previous sample when a phase is skipped.
In particular, nonzero `lk` during first person does not prove Link was drawn.

Row 20 `geo vUSED/TOTAL pk mp`: submitted forest vertex prefix versus full
bank, vertex packing time, and master scene-prepare time (0.1 ms). Packing
preserves hidden geometry and reuses dead depth/side scratch, allocating no
  extra vertex bank. `forest_pack_enabled=0` restores full-vertex transforms.
Latest default is `forest_pack_enabled=2`: gather up to 512 visible vertices
into a 6 KiB high-RAM draw cache; larger sets gather into the full-capacity
Low RAM cache (24 KiB formerly unused directory reservation tail).
Row 20 `g`: 0 full/unpacked, 1 in-place, 2 high-RAM gather, 3 Low RAM gather,
4 unexpected capacity fallback, 5 empty view. g2/g3 may legitimately use all
vertices if all are referenced; vTOTAL alone did not establish fallback in
older screenshots. Every legal loaded bank now fits the gather capacity.
Kokiri candidate reuse retains a conservative superset within 64 units of L1
camera travel and 256 binang of yaw/pitch. Row 20 `ec` is candidate face count;
`r1` means that list was reused (including an identical camera), `r0` a rebuild.
Moving refits still cull, sort and fog at the actual camera; candidate vertices
can exceed currently visible vertices. All mapped candidate indices, including
temporarily hidden ones, are restored before rebuild. Bank/LOD/FOV/roll/mode
changes invalidate reuse. `forest_envelope_enabled=0` restores exact-camera
full-bank preparation. Other scenes retain that path.
`1` retains the old in-place method. Restore time counts in depth/mp; compare
whole-frame time and mp as well as pk. Source points stay fixed in mode 2.
`npc_sprite_cpu_copy=1` restores CPU cel copies; default is joined DMA.
Resident cel hits are reserved before eviction and misses rotate through
unused slots to retain recent animation frames. No animation ticks removed.
Human confirms diagnostic rows freeze during dialogue; only bottom VRAM/M/S
continues. Do not interpret frozen chat FPS/timings as live samples. Human
explicitly declined fixing dialogue overlay refresh; it remains unchanged.

Mednafen reading (2026-10-12). Earlier Mednafen timings were invalid (word
FRC reads, BUILD.md 108); this build also sets the slave FRT to /128 (SGL left
it at /8, wrapping every 18 ms) and lets the core profile on the slave, so
rows 2 and 7 report again while the core runs there. To split emulator speed
from game speed, show Mednafen's counter (Shift+F1: virtual/rendered/blitted
FPS) beside rows 0 and 16:
- Mednafen virtual FPS well below 60: the PC cannot emulate full speed; the
  game's own numbers (`fr`, `fps`) are still Saturn time, just slowed.
- Virtual near 60 but `fps` low: the game is slow inside the Saturn. Then
  `sy` high = VDP1/VBlank bound; `wk` high = master CPU bound (rows 1-15);
  row 16 `W` high = master idle waiting for the slave (row 17 says which job).
- `vb` is VBlanks per frame: 2.0 = 30 FPS, 3.0 = 20 FPS, 4.0 = 15 FPS.
Report rows 0, 1, 2, 9, 15, 16, 17 and the Shift+F1 line, same spot/angle.

Row 23 `env vN b bt xp xa xo` (2026-10-12): candidate envelope variant
(Debug L+R+Right cycles 1..5; default 3 = led, 128 units), percent of frames
that rebuilt candidates, build-pass time (0.1 ms, frame mean), and percent of
frames leaving the old envelope by camera position / yaw-pitch / other.
Variant 5 forces the draw-point spill (g3) for scratch-placement A/B.

Job order (Debug only, 2026-10-12): L+R+Left cycles M -> P -> C -> M.
Default M runs scene preparation on the master concurrently with core updates
on the slave, then queues a slave cache purge before any later forest transform.
P keeps the previously tested slave prepare-first order; C is slave core-first.
Master preparation in M is reported as mp/phase rows and falls outside sc;
do not interpret a smaller sc alone as a gain. Judge whole-frame fr/fps/vb.

Speed changes 2026-10-09 (second Debug build): catch-up capped at 3 steps (2 slowed Link at 10 FPS)
under PLAYER_SOURCE (`RECOMP_MAX_CATCHUP`, recomp.c; below 15 FPS the world
slows instead of spiralling), follow-camera floor/line constraint applied once
per frame to the drawn eye (`player_camera_defer_constrain`), z_bgcheck
integer fast paths (`bgcheck_bounds.h`: `OotCore_BgFloorClass` in
CheckYIntersect, `OotCore_BgLineSameSide` in LineVsPoly; host probe output
bit-identical with `-DOOT_CORE_BG_NOFAST=1`; host floor 3349 -> 1232 cycles,
line 4201 -> 3752).

Notes for agents:
- `mv` contains `cu` on steps where the core updates (2 of 3 host steps), so
  compare `cu` against `mv` before blaming host code.
- `bgq` counts every host query (camera lines, shadows, C actors). A large
  `rb` means C props mark proxies dirty every frame.
- Numbers are smoothed timer readings, one observation per screenshot: compare
  the same scene, camera position and angle (CLAUDE.md "stop breaking
  working behavior").
- Removed 2026-10-09 (C Link era): music swap stats, C Link pose/landing
  rows, evade gates, mesh/warp probes, Fx micro-benchmarks. Recover them from
  git history if needed.

First reading (2026-10-09, Kokiri, real Player, before the anchor gate):
`fr1650 wk1569 sy81`, `mv1225`, `cu186 0/73/0/110`, `pd110`: CPU bound, the
Player anchor draw pass was 11 ms per core update. Now gated (oot_core_draw.cpp:
every update only while a weapon/shield/held/aimed anchor is needed, else
every 4th).

Second reading (2026-10-09, Kokiri, after cap/camera/fast paths): `fr948`
(10.5 FPS), `mv480 sk72 sc78 lk91 ot191`, `cu45`, `pd78`, Player 3.0 ms,
`gs60 co48 cm0 st222 n2`, `da125`. ~17 ms of `mv` outside `st`/`sk`/`ks`
unexplained -> row 12 `ru`. Third build: props view-culled, Z recenter on
PLAYER_STATE1_PARALLEL, cap 3.

Third reading (2026-10-09): `fr979` (~10 FPS), `cu119 0/49/0/68` (anchor
pass on that update), `co168 st403 n3`, `ru591` (~12 ms of recomp_update
outside `st`/`sk`), `da101` = `np88` (own sprites ~6 ms + `wp23`) + `fy12`.
Fourth build: Link skinning inline (exact 32-bit mul.l, was 9 slMulFX calls
per vertex), anchor pass every 8th idle update, collision data A/B (`fd`).
Compare `fr`/`cu`/`co` between `fd0` and `fd1` at the same spot.

Fourth reading (fd0 only): `fr897`, `sk34` (skinning inline halved it),
`np133` (npc_draw ~10 ms own: shadow floor queries), `ru626` (~24 ms outside
`st`/`sk`, row 14 now splits it). Cart vs Work RAM collision A/B dropped
(human: Astra measured cart RAM no slower). Fifth build: Navi decomp,
fairy shadows off, shadow cache on 16-unit cells.

Fifth reading (Navi build): `fr875`, `st371 n3`, `r1118` (sky + slScrAutoDisp
every frame), `np100`. Sixth build: core update on the slave SH-2 (row 15),
r1 caches. Row 2 `cu` phases read 0 now (profiling ticks are master-only);
`cu` shows the join wait instead.

Sixth reading (async core): `fr834` (12 FPS), `st162 n2` (was 371), `as k2
jw0 cv0 bv0` (slave fully hidden), `r1175` unchanged. Cause found:
`health_hud_draw` rebuilt all hearts with read-modify-writes in VDP2 VRAM on
every pulse step (~11 ms). Seventh build: hearts/magic composed once in work
RAM, only the pulsing heart redrawn, one copy to VRAM; follow camera
"moving" held 3 steps (Link moves once per frame now); bottom line shows
`M` master callback share and `S` slave core-job share (slave FRT, read
only; SGL's own slave polygon work not counted).

Seventh reading: `fr667` (15 FPS), `M 83% S 7%`, `sc152` (scene prepare,
master), `r121`. Eighth build: Link skin + scene prepare moved to the slave
(`sk`, most of `sc` leave the master; `S` now counts those jobs too).

Ninth build (autonomous, not run): SGL-aware schedule (PLAYER_MIGRATION.md
"SGL-aware slave scheduling"). Expect `sc` near 1 ms with `dr` small; `sk`
is now the master pose only; `S` counts core + prepare jobs (Link's skin
runs during the steps and is not in `S`).
Tenth build: + side-frustum cull in the scene prepare (`subm` on the old
debug page drops when looking along a wall of the forest; fewer polygons for
SGL on the slave and the master).
