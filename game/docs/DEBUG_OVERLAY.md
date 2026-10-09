# Debug performance overlay (Debug image, 2026-10-09)

Build: `./build.sh OOT_CORE=1` -> `build/game.cue` (Debug Mode in the
launcher). The Clean image only shows the bottom `VRAM / CPU~` line.
Code: `src/main.c` `diagnostic_overlay` (rows 0-2, 7-13; rows 3-6 sit under the heart/magic HUD) and the always-on heap
row 27. Refresh: 4 times a second (VDP2 keeps the text). L+R toggles the
older full debug page (`debug_visible`).

All times are **0.1 ms** units (e.g. `mv250` = 25.0 ms). One 30 FPS frame is
333; 60 FPS is 167.

| Row | Fields | Meaning |
| --- | --- | --- |
| 0 | `fr wk sy` | `fr` whole frame = `wk` CPU work in the frame callback + `sy` wait for VDP1/VBlank. `sy` near 0 with `wk` high = CPU bound; `sy` high = VDP1 fill bound. |
| 1 | `mv sk sc lk ot` | Host phases (`frame_timer.h`): `mv` gameplay step (input, `gameplay_step`, **the core update**, camera, doors), `sk` Link skinning (`link_anim_pose*`), `sc` scene cull/submit, `lk` Link submit, `ot` everything not named (NPC sprites, HUD, text, audio). |
| 2 | `cu a/b/c/d pd` | Core, per 20 Hz update (`oot_core_update_us`): `cu` total; then `gOotCorePhaseUs` collision checks (CollisionCheck_AT/OC/Damage) / actor updates (Actor_UpdateAll incl. the real Player) / messages+environment / draw shim (Actor_DrawAll capture); `pd` real Player anchor draw pass (Player_Draw pose split, `oot_core_draw.cpp`). |
| 7 | `top id x n ...` | The 3 actors with the most update time last step: actor id (hex) x 0.1 ms (`OotCore_ProfiledUpdate`). Player = `0`. Replaced by tool text while a Link tool actor is live (`OotCore_ToolDebug`). |
| 8 | `bgq rb a p/n/e/pr/m s` | `bgq` host `bg_*` collision queries since the last refresh (CORE_COLLISION shim), `rb` proxy DynaPoly rebuilds (`DynaPoly_UpdateContext` from C prop moves), `a` core actor counts player/NPC/enemy/prop/misc (ACTORCAT 2/4/5/6/8), `s` runtime scene index, `fd` 1 while static scene collision is read from the Work-RAM copy (`bg_core_fast_data`; Debug alternates 0/1 every 8 s, Clean always 1). |
| 9 | `gs co cm st n` | PLAYER_SOURCE host step split, summed over the last frame's catch-up steps: `gs` gameplay_step (C gameplay, pause, C actors' contacts), `co` core frame (`oot_core_frame`: input, save mirror, **core update**, player read, room/sprite refresh), `cm` camera update (core line/floor tests), `st` whole step loop, `n` steps this frame (capped 4: a slow frame does more steps). `st - gs - co - cm` = everything else in the step. |
| 10 | `nc wp en at bb tk it rc` | `gameplay_step` split (`src/perf_sub.h`, summed over the frame's steps): `nc` exit blocker + NPC sync, `wp` world props + rupees + wonders, `en` boulder/nut/Mido, `at` target + attention + Navi, `bb` Deku Babas, `tk` chest/prop interact/talk, `it` items/sword/shield, `rc` contacts. |
| 11 | `pr po ac dp nv` | PLAYER_SOURCE step outside gameplay_step/core/camera: `pr` before gameplay_step (dyna step, webs, doors, Gohma notice), `po` story/tree mouth/first-person/events, `ac` C puzzles + `actor_sys_update`, `dp` prop/door/Mido/boulder push of Link, `nv` Navi hover. |
| 12 | `ks dg da ui ru` | Frame (main.c): `ks` `kokiri_scene_update` (room portals), `dg` grass/rupee/boulder draw, `da` nut/baba/NPC/story/item/fairy draw, `ui` fade, dialogue, text, menus, HUD, reticle, minimap, `ru` whole `recomp_update` (contains `st` and `sk`). |
| 13 | `nb np wc wp fy` | Inside `da`: `nb` nut + Deku Babas, `np` `npc_draw` (contains `wc` + `wp`), `wc` `oot_core_meshes_draw` (core sprites, tools, effects, meshes), `wp` C world props (pots, rocks, bushes, stones), `fy` Kokiri fairies. |
| 14 | `r0 r1 pd dw` | `recomp_update` outside the step loop: `r0` before it (input, modes), `r1` after skinning (owl camera, sky gradient, layers); inside `pr`: `pd` webs/puzzles sync; inside `dp`: `dw` world_props_displace + push move. |
| 15 | `as k ov jw cv bv dr` | Async core (slave SH-2): `k` updates in the last job, `ov` master time between kick and join (0.1 ms), `jw` master wait at the join, `cv` master core entries while busy (must be 0), `bv` C collision queries refused while busy (shadow misses are deferred, not refused), `dr` master wait for SGL's slave queue to drain before the forest submit (0.1 ms). |
| 27 | `heap w c f sp` | Work-RAM zone live/peak bytes, cart zones peak KB, failed allocations, sprite peak. |

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
