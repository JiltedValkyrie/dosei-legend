# Bug and feature log

## BUG-063: Dungeon route completion (2026-09-30)

P1, Codex/Astra, open. User requires a completely playable route by deadline.
All 12 Tree rooms, nine source-gated shutters and two breakable floor webs now
integrated; 245 focused checks and Clean build pass. Boss scene remains isolated.
Missing wall webs/fire, torches/switches/platforms, dungeon enemies and source
scrub sequence still prevent normal completion; no debug clear flags added.
Door controls are A while facing within reach. Opening camera/animation/SFX and
HUD prompt, web edge deformation and particles need follow-up. Foreground boot
observed; room-by-room controller traversal and full fresh-file clear unverified.
See the latest M5_M6_IMPLEMENTATION.md entry for files and evidence.

## BUG-062: Dungeon map reward opens world map (2026-09-30)

Owner: Codex/Astra. P1 feature gap; implementation repaired, runtime acceptance
pending. Report: Map reward directs the player to the menu and says visited
areas are blue, but the page always displayed Kokiri Forest. Added five source
Deku floor diagrams, directional floor selection and blue visited-room shading;
map ownership reveals unexplored rooms. Save v8 appends visit bits and migrates
v2-v7 with unknown visits clear; the current room is recorded during gameplay.
Clean build passes (BSS 0x06079cb0, 41,808 bytes below SGL).
229 focused gameplay/save/renderer tests pass, including floor selection,
visited/unknown colors, v7 migration and VDP2 restoration. Offline source-art
preview inspected. Compass markers and automatic current-floor selection remain
follow-ups. Full dungeon traversal is still BUG-055, not closed by this fix.

## M5/M6 live integration follow-up (2026-09-29)

Owner: Codex/Astra. Scope and verification: M5_M6_IMPLEMENTATION.md. No commits.

- **BUG-055, P1, still open:** full dungeon/boss/story and Woods encounter chain
  are not implemented. New ten-room Woods streaming, C-item core, treasure grants
  and source music are progress, not milestone closure. Required work remains
  listed in the checkpoint; no request for human implementation or debug grants.
- **BUG-057, repaired capacity blockers:** sprite metadata now lives in an
  explicitly zeroed, guarded low-RAM NOLOAD section. Music trigger data exceeded
  the old 24 KB cart carve (29,288 B); now in a checked 64 KB low-RAM carve.
  Woods/music/menu assets exceeded the 288-entry disc directory (293 entries);
  capacity is now 320 and pre-master guard retained. No heap/render-limit cuts.
  Foreground boot/title rendering passed. Full room-churn/performance acceptance
  remains pending; see the final build log for current boundary measurements.
- **BUG-058, P2 presentation / P1 puzzle dependency:** live sticks/seeds/nuts use
  compact flat geometry. Source hand models, slingshot reticle/auto-target aim,
  throw animation frame timing and acquisition presentation remain incomplete.
  Analog hold/aim/release is wired; digital C-chord aiming needs runtime review.
  Stick burn lifetime exists, but torch/web ignition, water extinction, wall
  break and source jump-stick damage still need integration. Do not close M4/M5.
- **BUG-059, P1 content / P2 transition presentation:** Woods geometry/exits/music
  are live, but enemies, pickups, minigames, owls and bridge/ocarina story are
  absent. Visible tunnels swap one bank near their plane; source dual-room
  prefetch/black-plane fade is not reproduced. Meadow/Goron/River/Field still
  have reported unsupported destinations; no invented barrier has been added.
- **BUG-060, P2 test infrastructure:** full discovery ran 1,023 tests, initially
  15 failures and five setup errors. Equipment and room assertions were updated
  and pass in the focused run. Remaining stale extraction fixtures:
  `test_forest_partition` lacks current renderer state/types;
  `test_opening_audio` lacks sound-eye/CD duck state;
  `test_title_flights` assumes resident path tables;
  `test_ui_preferences` lacks cdda_volume. These are not evidence that gameplay
  passed; retain the failed full-suite log `game/build/m5-m6-regression.log`.
- **BUG-061, P2 audio fidelity:** new seed/nut effects follow source samples but
  use the existing single-layer bake, without full portamento/envelope layering.
  Dungeon/Woods music passes sample/loop/trigger bounds; listening and the full
  source dynamic sequence behavior remain unverified. Review with other SFX.


## Boot asset failure after Saria / Deku entry additions (2026-09-28, P0)

Human reported the blue `DIALOG/CUTTEXT/MINIMAP/MUSICTRG/TITLEPTH` boot error.
The mastered Clean ISO contains 264 root directory records (262 files plus dot
entries). `TITLEPTH.BIN` is record 261, zero-based, beyond Jo's 256-entry directory
table. The staged text/music files match their generated counts and sizes.

Fix: project-local `fs_capacity.h` raises the SDK filesystem object's table to
288 entries without changing shared SDK files. `check_disc_directory.py` rejects
overflowing directories before mastering; two guard tests pass. Boot loader now
reports the exact failed filename and read versus validation failure.
Clean rebuild passes: BSS ends `0x06083840`, 1,984 bytes below SGL. Same
`game/build/game-clean.cue`. Runtime confirmation in Kronos remains pending.
Owner: Astra.

## Human rule - effective for future work, 2026-09-25

Prioritize getting the game playable. Fix severe current blockers immediately;
record small bugs, potential issues and optional features here, then continue the
assigned milestone. Do not turn every finding into a prerequisite or side project.
This rule applies going forward only: existing M1a review/fix requirements remain
unchanged. Do not reopen, downgrade or waive those findings under this rule.

### Triage

| Priority | Meaning | Action |
|---|---|---|
| P0 - severe | Crash/hang, save loss/corruption, memory corruption, cannot boot/build the required image, or required gameplay/progression cannot proceed | Fix now before dependent work; notify the current owner when their files are involved |
| P1 - important | Confirmed gameplay defect with a workable path, or a defect in a system not yet used by the current playable route | Log with impact and a concrete revisit trigger; fix in the relevant milestone, without blocking unrelated work |
| P2 - minor | Cosmetic defect, small behavior mismatch, maintainability issue or unconfirmed potential problem | Log evidence/uncertainty; defer until related work or polish |
| Feature | Optional improvement or new scope | Record benefit and dependencies; implement only when assigned or approved as part of the plan |

Priority follows actual impact and reachability, not how easy a problem is to
imagine. A suspected severe failure warrants a bounded check now; call it confirmed
only when evidence supports that. Escalate deferred issues when a new feature makes
them active, their impact increases, or they block a required route.

Existing required milestone features remain required; this log does not silently
make them optional or declare unfinished work complete. Link planned work to its
milestone instead of duplicating its full specification here. No extra permission
is needed for fixes already within assigned scope. Coordinate shared-file ownership
without editing another agent's active implementation behind them.

### Review and work discipline

- Review reports separate severe blockers from nonblocking follow-ups. A minor or
  potential issue alone does not hold the next milestone; record it and continue.
- Make one concise entry per issue. Include observed evidence or mark suspicion,
  player impact, priority, owner (or unassigned), status and revisit milestone/trigger.
- For bugs, include reproduction/expected versus actual behavior when known. For
  features, include intended benefit, scope and dependencies. Link detailed review
  notes instead of repeating them. Do not invent a repro or claim a test was run.
- Keep investigation proportional. Do not derail playable work for broad cleanup,
  speculative hardening, refactors or optional source-parity improvements.
- On fixing an entry, record verification and commit when available. Keep a short
  resolved record so another agent does not rediscover or silently reopen it.
- Follow existing clean-only build, VDP2-menu, source/drop and milestone review
  requirements. This rule changes triage, not technical constraints or ownership.

## Issue tracking format

Use GitHub-style issue records below. These are local records, not published
GitHub issues. If later moved to GitHub, link the real issue and use its number;
do not invent GitHub issue numbers or claim an issue was filed remotely.

Labels: `bug` or `enhancement`; `priority: P0`, `priority: P1` or `priority: P2`
for bugs; `needs-triage` for unconfirmed findings. Feature priority is assigned
when scoped. Track assignee and milestone separately, as on GitHub.
State is **Open** or **Closed**; resolution is **Completed**, **Not planned** or
**Duplicate**. Open does not imply blocked: severity and dependencies determine
whether work stops. Optional features stay in backlog until assigned.

### Issue index

| ID | Title | Labels | Assignee | Milestone / revisit trigger | State |
|---|---|---|---|---|---|

| BUG-001 | Wall line-hit precedence | `bug`, `priority: P2` | Unassigned | Before wall-damage contact use | Open |
| BUG-002 | Failed collision decode mutates live data | `bug`, `priority: P2` | Unassigned | Scene-load recovery / M8 | Open |
| BUG-003 | Locomotion tests match obsolete source text | `bug`, `priority: P2` | Unassigned | Next locomotion-test edit | Open |
| BUG-004 | Locomotion clip cadence 2/3 of source | `bug`, `priority: P2` | Unassigned | M8 polish / locomotion anim work | Open |
| BUG-005 | M1c wall/ledge subset gaps | `bug`, `priority: P2` | Unassigned | Wall-sensitive actions (M1e-M1h) | Open |
| BUG-006 | Talk claims A before ledge climb | `bug`, `priority: P2` | Astra | M3 NPC placement near ledges | Fixed in code; Kronos pending |
| BUG-007 | Floor jump/land SFX and second climb voice missing | `bug`, `priority: P2` | Unassigned | SFX bank rework / M8 | Open |
| BUG-008 | Source-snippet tests no longer compile | `bug`, `priority: P2` | Unassigned | Next edit of demo.c/cutscene.c/kokiri_sgl.c tests | Open |
| BUG-009 | Link drawn 1.45x source child vs source headroom | `bug`, `priority: P2`, `needs-triage` | Unassigned | Human visual check / M8 | Open |
| BUG-010 | 250 jump has no mid-air ledge grab | `bug`, `priority: P1` | M1d | M1d hang | Closed |
| BUG-011 | Released digital pad can interrupt climb early | `bug`, `priority: P2` | Unassigned | Next climb/input integration | Open |
| BUG-012 | 250-jump retained air speed cleared before launch | `bug`, `priority: P2` | Unassigned | Next air/grab integration | Closed |
| BUG-013 | Point-in-poly slack was 1 unit, source is detMax 300 | `bug`, `priority: P1` | Claude (M1e) | Fixed M1e; Kronos walk check | Closed |
| BUG-014 | Climb port subset gaps | `bug`, `priority: P2` | Unassigned | Vine-heavy scenes (M5) | Open |
| BUG-015 | House ladder descent from the porch unverified | `bug`, `priority: P2`, `needs-triage` | Unassigned | Human check vs real OoT | Open |
| BUG-016 | Grounded ceiling check missed the -7.5 dy | `bug`, `priority: P1` | Claude (M1f) | Fixed M1f | Closed: human play 2026-09-27 |
| BUG-017 | Crawl port subset gaps | `bug`, `priority: P2` | Unassigned | M1l camera / M8 | Open |
| BUG-018 | M1g turn/bonk source subset gaps | `bug`, `priority: P2` | Unassigned | M8 polish; M7 bonk actors | Open |
| BUG-019 | Bonk/hang voice sounds wrong to human | `bug`, `priority: P2` | Unassigned | Done | Closed |
| BUG-020 | Push-block live integration and source subset | `bug`, `priority: P2` | Unassigned | Before Deku Tree room 5 acceptance | Open |
| BUG-021 | Grass patch behaves like a raised floor | `bug`, `priority: P1` | Astra | Human pass 2026-09-26 | Closed |
| BUG-022 | Carry props and full reward integration pending | `bug`, `priority: P2` | Unassigned | M3 liftable props / M1i acceptance | Open |
| BUG-023 | Slope/fall runtime and M2 damage integration pending | `bug`, `priority: P2` | Unassigned | M1j runtime / M2 health | Open |
| BUG-024 | Grass overlap rustle effects and sound | `bug`, `priority: P2`, `needs-triage` | Unassigned | M3 grass / M8 feedback | Open |
| BUG-025 | Water traversal source subset and runtime acceptance | `bug`, `priority: P2` | Astra | M1k human check; M2/M5 integration | Open |
| BUG-026 | Dialogue special characters and missing dither backdrop | `bug`, `priority: P2` | Unassigned | Next dialogue/UI pass | Open |
| BUG-027 | Traversal camera source subset and runtime acceptance | `bug`, `priority: P2` | Astra | M1l human check / M8 | Open |
| BUG-028 | Registered colliders follow reused actor slots | `bug`, `priority: P2` | Claude | Before live actor contact integration, M2b | Closed |
| BUG-029 | Alternating attackers defeat once-per-attack memory | `bug`, `priority: P2` | Claude | Before multi-attacker damage integration, M2b | Closed |
| BUG-030 | Hit-history eviction and multiple hurtbox policy | `bug`, `priority: P2` | Claude | Live actor damage integration | Fixed |
| FEAT-001 | Real sword chest, shop shield and Mido equipment gate | `enhancement`, `priority: P1`, `required` | Claude | M2b.1, before M2c human testing | Human route passed; boulder pending |
| BUG-031 | M2b.1 presentation stand-ins: chest, shopkeeper, get-item | `bug`, `priority: P2` | Claude | M3 actor models / M8 | Open |
| BUG-032 | Maze rolling boulder (En_Goroiwa) not implemented | `bug`, `priority: P1`, `required` | Claude | Final M2 acceptance | Closed: human Kronos 2026-09-27 (see BUG-051) |
| BUG-033 | Work-RAM gap down to 5,488 B | `bug`, `priority: P1` | Claude | Before next large code/text addition | Fixed, Kronos text check pending |
| BUG-034 | kokiri_camera_facing uses toFIXED(variable) soft-float | `bug`, `priority: P2`, `performance` | Unassigned | Next SH-2 hot-path pass | Open |
| BUG-035 | Work-RAM heap arena at 99% peak (50,692 / 51,200 B) | `bug`, `priority: P2` | Claude | Later human batch playtest; sooner on allocation failure | Open: measurement deferred by human |
| BUG-036 | M2c combat gaps: SFX, charge glow, hostile-lock clips, blade pose lag | `bug`, `priority: P2` | Claude | M2d enemy / M2e audio bank | Open |
| BUG-037 | Standard work-RAM gap 5,504 B after M2c (Clean 8,896 B) | `bug`, `priority: P1` | Claude | Before next large code addition | Fixed: 7,168 / 10,368 B |
| BUG-038 | En_Elf fairy look gaps (colours, wing UVs, sparkle alpha, NPC sparkles) | `bug`, `priority: P3` | Claude | M3 Kokiri NPCs | Open |
| BUG-039 | Work-RAM gap was 2,352 B; Link mesh tables to cart (Clean 23,616 B) | `bug`, `priority: P1` | Claude | Done | Closed |
| BUG-040 | M2d.1 attention gaps (on-screen test, NPC range types, NPC focus, Navi voice) | `bug`, `priority: P3` | Claude | M3 Kokiri NPCs | Open |
| BUG-041 | Forest load rejected after attention glows: resident VRAM undercount | `bug`, `priority: P0` | Codex | Done | Closed: human Kronos check |
| BUG-042 | M2d.2 Deku Baba presentation gaps (effects, shadow, hit-stop, SFX layers) | `bug`, `priority: P3` | Claude | M5 enemy polish | Open |
| BUG-043 | Clean work RAM: 14,656 B below SGL after cart tables (was 288 B) | `bug`, `priority: P1` | Claude | Before next code addition | Open |
| BUG-044 | Navi/C-Up gaps: first-person view, colour blend, NPC ranges | `bug`, `priority: P3` | Claude | M4 C-items | Open |
| BUG-045 | M2e death/Game Over presentation gaps | `bug`, `priority: P3` | Claude | M5 dungeon continue / polish | Open |
| BUG-047 | All audio skipped after title-bank sample-rate reduction | `bug`, `priority: P1` | Codex | Human audio check | Closed: human listening 2026-09-27 |
| BUG-046 | Pause window visual parity remains incomplete | `bug`, `priority: P2` | Codex | Pause UI parity / human batch review | Open |
| BUG-048 | Death Save prompt cannot select No | `bug`, `priority: P1` | Claude | M2e regression | Fixed; human Kronos pending |
| BUG-049 | Continue Yes spawns Link in sky/nowhere and freezes | `bug`, `priority: P0` | Claude | M2e blocker | Fixed (probable cause); human Kronos pending |
| BUG-050 | Child Link death voice sounds like adult Link | `bug`, `priority: P3` | Claude | M8 audio polish / next death-audio work | Open: deferred by human |
| BUG-051 | Maze boulder slides as static mesh, no rolling spin | `bug`, `priority: P2` | Claude | M8 polish / En_Goroiwa visual | Open |
| BUG-052 | Loading a Game Over save starts Link dying | `bug`, `priority: P0` | Claude | M2e save/load regression; before further M3 expansion | Open |
| BUG-053 | Pause corruption after Continue with rebuilt mounted ISO | `bug`, `priority: P1` | Codex | Cold-boot Continue retest; keep mounted image unchanged | Open: live wrong-sector reads confirmed |
| BUG-054 | Fresh-boot title hangs in full-work-heap callback allocation | `bug`, `priority: P0` | Astra | Cold boot title | Code fixed; Clean build passes; runtime retest pending |
| BUG-055 | M5/M6 source rooms not yet connected to complete gameplay | `bug`, `priority: P1` | Codex/Astra | M5/M6 integration | Open |
| BUG-056 | Post-Emerald NPC presentation and early-close semantics | `bug`, `priority: P2` | Codex/Astra | M6 NPC/scene review | Open |
| BUG-057 | M5/M6 room-loader addition exceeded SGL by 128 bytes | `bug`, `priority: P0` | Codex/Astra | Runtime check of low-RAM metadata | Build fixed; runtime unverified |

### BUG-055: M5/M6 integration ledger

2026-09-29 source audit: ydan has nine Door_Shutter transitions plus two vertical
and one horizontal invisible En_Holl; Lost Woods has nine visible narrow tunnels.
The runtime only previously handled forest invisible tunnels. Source graph and
all 24 isolated banks now exist, but they do not constitute a playable dungeon.
Unsupported shutter/visible-tunnel exports fail instead of opening puzzle gates.
Only original room-0 dungeon shell remains enabled in the player build.

Required dependencies: M4 live stick/nut/slingshot, dungeon mechanism/actor/drop
ports, Gohma/reward/story chain, Woods actors/minigame/owls and bridge cutscene.
Meadow access is source-reachable, its explicit boundary remains unresolved;
Field handoff awaits M7. Current room budgets include Link/effects only, not the
new enemy/puzzle actors. Track completion against M5/M6 plans, not this issue
alone. [Implementation and evidence](M5_M6_IMPLEMENTATION.md).

### BUG-056: Post-Emerald NPC presentation/early-close follow-up

2026-09-29 code/source evidence: exit guard now uses the correct post-Emerald path
endpoint and Mido leaves only after talking and reaching his endpoint. Existing
Mido walking uses rounded integer steps rather than exact 1.5 source units/frame,
and existing NPC animation/turning does not reproduce every source walk/stop pose.
The generic dialogue cancel closes early and dispatches normal closing effects;
text 0x1045 currently shares that adaptation rather than source TEXT_STATE_EVENT
advance semantics. No milestone completion is claimed. Revisit with M6 NPC
presentation and dialogue acceptance; host tests verify normal completion only.

### BUG-057: Room metadata work-RAM relocation

Measured Clean .bss end 0x06084080, SGL base 0x06084000. Boundary guard rejected
and removed that image. Move generated room object-index and bounds arrays to
non-overlapping low-RAM carves 0x9800..0xB800; compile-time size/order guards
remain. Loader fills all used entries before rendering; no heap/sprite/SGL limit
was cut. Final Clean BSS 0x06083720, 2,272 B below SGL. Foreground boot/title/forest
render verified after launching on the interactive desktop outside the sandbox.
Room churn/gameplay acceptance remains open. OPUS_HANDOFF has the evidence paths.

### BUG-046: Pause window parity follow-up

Four original-art pages and the save window are wired on NBG2, owned items
only, with real gear/save actions. Current presentation is front-facing:
3D page flips and animated Link portrait are not implemented; item names use
the current VDP2 font. Current world-map coverage is Kokiri and its interiors;
other region clouds remain. Future dungeon/item/song functionality stays
unwired and never claims success. These remain required parity gaps, not
verified 1:1 behavior. Human batch graphical review pending. Details and
memory ownership: [PAUSE_HUD_UI.md](PAUSE_HUD_UI.md).
Live heart HUD is wired to save health; 7 focused pause/health checks pass,
153 gameplay checks pass, Clean build passes. No emulator verification.

### BUG-047: Stale title PCM size rejects sound initialization

Human reported silence in Clean. music_banks.c hardcoded 480,046 title PCM
bytes while the regenerated file is 240,048. With MUSIC_SAMPLE_LIMIT=0x3C000,
music_init returns false before SCSP initialization. main only initializes
action SFX after music succeeds, explaining why both are absent. Clean hides
the old music status overlay; this is not a Clean-only playback policy.

Fix: generate TITLE_PCM_BYTES beside the score and use it in the bank
descriptor. Export it in the current asset header too; preserve file-size and
RAM guards. Report startup music failure outside the diagnostic HUD.
Regression checks the generated byte count against the real PCM and memory
limit and prohibits the obsolete local override. It and 15 action-audio tests
pass. Human playback confirmation remains pending.

### BUG-041: Resident sprite budget omitted successful optional uploads

- Evidence: staged S1R0 needed 447,384 bytes against 445,432 available;
  S1R1 needed 447,512. Six attention glows add 3,072 bytes. Sprite slots
  fit (1,584 / 1,680 of 2,400); `room_load_bank()` rejected the VRAM total
  in its combined header/capacity guard. This is independent of the RAM move.
- Fix: `vdp1_budget.py` reserves all 40 runtime sprites (20,160 bytes),
  including glow steps, sparkle, message panel/marks and minimap markers.
  Sprite-slot validation now includes these residents and Jo slot zero.
  Per user preference for lower detail over load failures, the density
  allocator now leaves 32 KiB spare after the full reservation.
  Runtime capacity errors identify the bank and byte/slot totals and check
  the destination command layout before switching banks.
- Clean rebuild: S1R0 uses 411,928 bytes (33,504 spare), S1R1 410,648
  (34,784 spare). Geometry and glow assets retained; texture sizing spends
  less on forest tiles. No mirrored-tile reuse was introduced.
- Validation: budget regression reproduced both old bank failures; rebuilt
  staged-bank capacity checks and room-bank policy pass (4 tests). Clean
  image built. Human tested in Kronos on 2026-09-27 and reported no visible
  difference after the texture reduction. Scene-load blocker closed.

Original M1a blocking findings are resolved by the 2026-09-26 re-review in
[M1A_REVIEW.md](M1A_REVIEW.md). The following are nonblocking follow-ups.
Use local IDs `BUG-001`, `FEAT-001`, etc.; never reuse an ID. Add one index row and
one issue body per finding. Templates below are examples, not open issues.

## Open issues

### BUG-031: M2b.1 presentation stand-ins

**Labels:** `bug`, `priority: P2`. **Assignee:** Claude. **State:** Open.

Chest is a floating Kokiri Sword icon, no En_Box model, lid animation,
Demo_Tre_Lgt light or fanfare; opening is instant. Get-item holds the 16px icon
over Link, not link_demo_get_itemA. Kokiri shopkeeper has no model or fairy in
the prerendered shop; A: Talk prompt only. Shop talk reach is the slice's
(150). Only the Deku Shield is offered; eight-item browse is M3. Mido's
0x102F/0x1033 are UNSKIPPABLE in source; B still closes here. Mido walks a
straight line at one unit a step, no walk animation (NPC bodies absent).

### BUG-032: Maze rolling boulder

2026-09-26 repeated knockdown blocker: an unregistered boulder retained
COL_RES_AT_HIT while hopping/cooling down. The shared pass consumed that old
result again, restarting Link's 45-step control lock after 28 steps. Clear
the boulder's result before registration each pass; the prior hit is already
consumed by update_boulder. Regression failed at cooldown step 27 before the
fix; all 86 gameplay tests pass after it. No game build or Kronos run; escape
after a real hit still needs visual confirmation.

2026-09-26 user regression: stationary cube blocks the sword route. Heading
used Q8 deltas where the Saturn adapter expects world integers; the first
331-unit leg became 84736 and overflowed the adapter's signed Q16 conversion.
Corrected boulder_face to pass world deltas. Host heading adapter now asserts
the target input range; 85 gameplay tests pass. No game build requested/run.
Movement and sword access still need Kronos confirmation; cube remains the
documented visual placeholder. Do not mark this blocker visually resolved.

**Labels:** `bug`, `priority: P1`, `required`. **Assignee:** Claude. **State:** Implemented, Kronos check pending.

Done: build_actors extracts En_Goroiwa 0x0C02 (room 2, rot_z 1) and scene
path 2 (header 0x0D), refusing any other shape or a path off the flat floor.
gameplay.c: EnGoroiwa_Roll/MoveAndFall (Kokiri speed 9.2, step 0.3, gravity),
one-way loop with teleport at the ends, AT sphere r58 vs Link cylinder r12
(next-step AT_HIT), in-the-way reverse, hop x0.15, 6-frame wait, 50-frame no
collision, room reload restarts at point 0, frozen while talking/paused.
Damage 4 (quarter heart); shield cannot block (shield AC 0xDFCFFFFF lacks the
boulder's 0x20000000). demo.c: knockback 2.0 away, OC push (MASS_HEAVY).
Stand-ins (BUG-031): grey cube, no gRollingRockDL, no roll spin, dust, SFX;
no knock-down animation (input held 45 steps, speed eases out); Link cylinder
height 50 fixed; no death/game over at 0 health. Code cost ~3.9 KB: clean gap
now 9,184 B.

En_Goroiwa room 2 (-245,120,1870), params 0x0C02, path 2 loop
(spot04_scenePathList_00030C_020002EC). Not implemented: path, collision,
damage/knockback. Required before final M2 acceptance (M2b.1 item 6); early
chest/shop human test runs without it.

### BUG-033: Work-RAM gap 5,488 B

**Labels:** `bug`, `priority: P1`. **Assignee:** Claude. **State:** Fixed, Kronos text check pending.

Fix: line strings (8,466 B) and pointer table left the program.
build_dialogue.py writes build/cd/DIALOG.TXT (KDLG, u16 BE count/offsets,
NUL strings); main.c loads it at boot into cart carve 0x8000/0x3000
(RAM_CART_FIXED_BYTES 0xB000) and refuses to start on a missing/mismatched
file; src/dialogue_text.c validates and serves lines. Host tests bind the same
file. Clean gap now 13,120 B (build/bug033-clean.log). Next candidate if
needed: cutscene text pools (build_cutscenes.py), same pattern.

Clean .bss ends 5,488 B below the work area (13,344 before M2b.1). About 4 KB
is source-correct dialogue: TEXTID chains now followed (Mido refusal/allow,
NPC lines, 191 -> 310 lines). Move dialogue strings/pages to a cart file (or
disc) before the next large addition.

### BUG-035: Work-RAM heap arena nearly full

Human directive (2026-09-27): P2, defer new peak readings to later batch
playtesting. Not an M3a entry gate; proceed with feature work. Keep allocation
and capacity guards, preserve arena size, and place large buffers in cart.
A real allocation failure/crash escalates independently; deferral is not a
claim that current peaks were measured. The 50,692 B figure remains historical.


**Labels:** `bug`, `priority: P2`. **Assignee:** Claude. **State:** Open.

M2a live reading (human, standard build, maze room 2 near the chest, after
forest): zone 0 live 50,380 / peak 50,692 B of the 51,200 B arena
(JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC), cart zones peak 719 KB, 0 failed
allocations. Only 508 B headroom: larger jo_malloc blocks already spill to the
cart, so no failure, but never shrink this arena, and route new big buffers
to the cart explicitly. Readings from the shop and forest return still wanted.

### BUG-036: M2c combat gaps

**Labels:** `bug`, `priority: P2`. **Assignee:** Claude. **State:** Open.

M2c is in (see [M2C_REVIEW.md](M2C_REVIEW.md)); these parts are not:
- SFX in (forest area bank, 5512.5 Hz, slot 28): wall hit hard/soft
  (soft = same sample +17 semitones, no portamento), shield/sword bounce
  (NA_SE_IT_SHIELD_REFLECT_SW first layer only), nutsball break. To make
  room, core `shield` and `equip` are now stored at half rate (lower
  bandwidth). Still missing: NA_SE_IT_SWORD_CHARGE (FONTANY 8PULSE synth
  sweep), NA_SE_IT_ROLLING_CUT spin release (INST_39), wood-wall
  NA_SE_IT_REFLECTION_WOOD, voices on bounce. Sound RAM spare: 1,420 B.
- Fixed with it: climb-end/roll-bonk voice (half-rate sample) played an
  octave high; OCT now comes from each sample's stored rate.
- No charge glow or magic spin wave; no wall sparks (CollisionCheck_Spawn-
  ShieldParticles). Sword trail is Codex's ribbon.
- Hostile lock-on variants (_endR landings, rebound R clips, gravity -1.2 in
  Player_Action_8084411C) wait for an M2d hostile target: none exists yet.
- Blade capsules use the last drawn pose (up to one frame old), sampled at
  base/tip/mid edges with radius 4, not the exact swept quads.
- Nutsball: no OC push, grey sphere visual, reflection yaw = Link's facing
  (source: shield matrix yaw + 0x8000). Dyna-attached wall polys
  (func_8002F9EC) are not excluded from the wall check.
- Charge walk plays the walk clip forward for backward travel too.

### BUG-037: Standard work-RAM gap 5,504 B

**Labels:** `bug`, `priority: P1`. **Assignee:** Claude. **State:** Fixed.

Fix: cutscene run strings moved to build/cd/CUTTEXT.TXT ("KCST", same
layout as DIALOG.TXT) in cart carve 0x6800/0x1800; shared loader in
src/text_pool.c. Standard now 7,168 B free, Clean 10,368 B (after the M2c
sounds too).

After M2c (and Codex's trail) standard .bss ends 5,504 B below the work
area, Clean 8,896 B. Growth is code: gameplay.o +2 KB, demo.o +1.6 KB, four
clips. Next candidate to move out: cutscene text pools (build_cutscenes.py)
as BUG-033 did for dialogue. Contacts moved to cart carve 0xB000/0x2000
(RAM_CART_FIXED_BYTES 0xD000); 0x6800..0x8000 is free.

### BUG-038: En_Elf fairy look gaps

**Labels:** `bug`, `priority: P3`. **Assignee:** Claude. **State:** Open.

Fairy is now the posed gFairySkel wings + gGlowCircleSmallDL glow +
KiraKira sparkles (tools/build_fairy.py). Gaps:
- Kokiri fairies all use Navi's inner/outer (white/blue); source picks
  sColorFlags colours per fairy.
- Wing texture dropped 2026-09-27 (human: dither hid it); wings flat
  210,210,255 MESHon. Wing 3/4 UV skew gap moot by user choice.
- Glow L->SL cross-fade is 3 dither steps, not a continuous blend; alpha
  ramp is dither density with a solid SL core.
- Sparkle prim alpha fade (255 -> 200) not modelled; only Navi sparkles
  (Kokiri fairies spawn none yet).
- 2026-09-27 M2d.1: Navi colour now follows attention (NPC / enemy glow
  sets FAIRYN0-2, FAIRYE0-2). Swaps at end of source 4-frame fade, no
  blend. Sparkles stay white/blue. No green (other category) set.

### BUG-042: M2d.2 Deku Baba presentation gaps

**Labels:** `bug`, `priority: P3`. **Assignee:** Claude. **State:** Open.

En_Karebaba logic, colliders, drop and regrow follow z_en_karebaba.c
(src/karebaba.c). Not drawn or not exact:
- EffectSsHahen dirt bursts (Awaken/Retract/Dying) and the 4 + 1
  func_800286CC dust puffs: none drawn.
- ActorShadow circle (22) and the base gCircleShadowDL: none.
- Enemy_StartFinishingBlow freeze (freezeFlashTimer 5): sound only.
- func_80026230 black damage flash: none.
- SFX: DEKU_JR_DEAD vibrato and second layer (LAYER_4829) not rendered;
  portamento approximated as a linear glide on one sample run.
- Room sync: babas live only while room 1 is the current room (OoT keeps
  both rooms during a transition); leaving respawns them fresh (Idle).
- Stick get-item show: text 0x0037 opens; Link's hold-up pose, the
  GI_DEKU_STICKS model and the small-item fanfare are not played.
- Player-state gate for the offer reduced to grounded / not charging /
  not talking.

### BUG-043: Clean work RAM 2,384 B

**Labels:** `bug`, `priority: P1`. **Assignee:** Claude. **State:** Open.

After M2d (attention, Navi hint, Deku Baba: ~5.5 KB code, state moved to
the cart) and the concurrent gameplay HUD (minimap/hud_maps ~8 KB), Clean
.bss ends 4,576 B below the work area. M2e death/continue code needs room
first: candidates are hot-path-neutral cold tables to the cart, or the
jo_malloc arena (51,200; spills to the cart) after a live heap measurement.

Latest UI build: .bss ends 0x06082B60, 5,280 B below SGL. Button label maps
now live in VDP2 B0+0x12000 (5,344 bytes) instead of work RAM. This includes
saved controller/jump preferences and the richer pause map. Budget remains
tight; earlier measurements above are historical.

Full-RGB pause carousel follow-up: .bss 0x060836B0 leaves 2,384 B. Page/font
data and exact borrowed-VRAM backup use the cart, not work RAM. Fixed cart
carve grows to 0x70000; validate pause/open/close in the human forest/interior
batch before considering runtime memory behaviour verified.

### BUG-044: Navi / C-Up gaps

**Labels:** `bug`, `priority: P3`. **Assignee:** Claude. **State:** Open.

- C-Up with nothing to say is first-person view in the source; not built,
  so it does nothing (source beeps NA_SE_SY_ERROR only when that fails).
- En_Elf colour fade (4 source frames) swaps at the end, no blend.
- Quest hints cover the slice's two entries (0x0140, 0x0141); later ones
  need items/songs outside the slice.

### BUG-045: M2e death / Game Over gaps

**Labels:** `bug`, `priority: P3`. **Assignee:** Claude. **State:** Open.

Death, Game Over, save, continue follow func_80836448, GameOver_Update and
kaleido PAUSE_STATE_GAME_OVER_* (src/game_over.c). Not exact:
- The world freezes at death (source keeps actors updating during the
  derth_rebirth clip); no OnePointCutscene camera, letterbox or lights.
- Kaleido prompt windows (rotating panels, icons) are plain VDP2 text; the
  FINISH fade to black is not drawn (timing kept).
- Void out returns Link to his last safe spot (source: last entrance) and
  costs the respawn heart; NA_SE_OC_ABYSS / REVENGE not rendered.
- NA_SE_PL_BODY_HIT (fall damage) not rendered: PL_DAMAGE stands in.
- Floor types 6/9 (no fall damage) not checked; fall start = jump peak.
- Hurt reaction: flinch-only rule approximated with `moving` for speedXZ
  > 4; hit-clip knockback speed kept at the M2b 4.0 push.
- Fairy revival, magic, timers, trade items: outside the slice.
- Continue restores 3 hearts at the scene's current entrance; loading a
  saved file resumes in Link's house (Sram_OpenSave, now applied).
- CD-DA: Game Over and small-item fanfares play over the SCSP score's fade.

### BUG-040: M2d.1 attention gaps

**Labels:** `bug`, `priority: P3`. **Assignee:** Claude. **State:** Open.

Shared attention (src/attention.c) ports Attention_FindActorInCategory,
WeightedDistToPlayerSq, ShouldReleaseLockOn, Update/SetNaviState. Gaps:
- Attention_ActorOnScreen: DONE 2026-09-27 (demo.c attention_on_screen,
  live camera + screen distance, acquisition only).
- Kokiri NPCs use ATTN_RANGE_SLICE_NPC (320 acquire / 420 leash), not
  each En_Ko/En_Md/Saria source attentionRangeType. Mido = En_Md RANGE_6.
- NPC focus = feet + 40 stand-in, not head limb; arrow 20 (Actor_Init).
- attentionPriority, ACTOR_FLAG_LOCK_ON_DISABLED, category search order
  tie-break, forcedLockOnActor not modelled (none used in slice).
- Navi voice on lock (NA_SE_VO_NAVY_HELLO / ENEMY / HEAR) not played.
- Camera still gets lock bool only. Next reviewed step: target focus XYZ
  -> Camera_CalcAtForLockOn aim (Z_TARGET_FRIENDLY / UNFRIENDLY).

### BUG-039: Standard work-RAM gap 2,352 B

**Labels:** `bug`, `priority: P1`. **Assignee:** Claude. **State:** Open.

After minimap, CD-DA, fairy wings/glow and the 16-slot sparkle pool
(384 B bss + ~0.7 KB navi code), standard .bss ends 2,352 B below the
work area, Clean 5,584 B. Next large addition must first move data to the
cart (candidates: kokiri_sgl forest tables, link_scene .data 18 KB).

**2026-09-27 fix:** Link's POLYGON/ATTR tables (18,048 B .data) are cold:
read only when equipment changes, into the hot `equipped_*` copies. Now
`build/generated/link_mesh.c` is compiled `-fno-lto`, `.rodata` objcopied
to `LINKMESH.BIN`, loaded into cart carve 0xF000 (fixed carve 0xF000 ->
0x14000) by `kokiri_scene_load()`. Clean 5,616 -> 23,616 B free. Standard
not rebuilt (expect ~20 KB). Per-frame draw path unchanged (still work RAM).
Human Kronos 2026-09-27: Link draws, sword/shield swaps good. Closed.

### BUG-034: kokiri_camera_facing soft-float

**Labels:** `bug`, `priority: P2`, `performance`. **State:** Open.

demo_camera.c kokiri_camera_facing calls slAtan(toFIXED(dz), toFIXED(dx)) on
variables: SDK toFIXED multiplies by a double. gameplay_facing/collide_heading
route here; M2b.1 adds per-step calls (Mido block, chest/shop facing). Use a
range-checked integer scale (ratio only matters to slAtan).

### BUG-030: Bounded hit history needs actor-level damage policy

**Labels:** `bug`, `priority: P2`

**Assignee:** Claude. **Milestone:** live enemy/player damage and multiple hurtboxes.
**State:** Fixed.

Policy (source): multi-element hurtboxes of one actor set COL_AC_ELEMENT and
take one hit per AT per pass (CollisionCheck_AC_*VsJntSph returns after
SetATvsAC); separate source colliders (Link cylinder + shield) do not group.
History stays bounded at 4 and documented as such; actor-level protection is
the victim's own intangibility (Link: gameplay.intangible -> body invincible).
Tests: grouped vs separate elements; five interleaved attacks evict, and
invincibility still blocks.

Four-entry history fixes BUG-029's A/B/A case. A fifth distinct attack evicts the
oldest; that still-active attack may hit again. History is per collider, so two
hurtboxes on one actor also need shared reaction/damage handling. Neither is a
blocker for actorless grass or M2b.1 chest/shop work.

- [x] Integrate source damage timers or bounded attack-owned victim history for
  live combat; do not advertise unlimited once-per-actor suppression.
- [x] Test five interleaved attacks and multiple hurtboxes without duplicate
  actor-level damage/rewards, preserving source hard-body/shield behavior.


### FEAT-001: Real starter equipment route for M2 human testing

**Labels:** `enhancement`, `priority: P1`, `required`

**Assignee:** Claude (current M2 owner). **Milestone:** M2b.1, after contact/body
work and before M2c human combat testing. **State:** Starter route implemented
and human-tested 2026-09-26; remains open for required boulder (BUG-032).

Current ground sword/shield are slice shortcuts. Bring source maze sword chest,
40-rupee shop shield, fresh-file rupee route and Mido equipment gate forward.
Full scope/dependencies: M2_COMBAT_PLAN.md, M2b.1.

- [x] Crawl maze, open source chest, receive sword once; chest flag persists.
  (Host-tested; offer box/facing from EnBox_WaitOpen; owned, not equipped.)
- [x] Reachable source rupees permit first shield purchase without a sword.
  (24 En_Item00 + 19 En_Wonder_Item modes 2/0/5 = 43; host-tested.)
- [x] Shop costs 40, handles refusal/cancel, grants once; UI uses VDP2.
- [x] Mido allows Deku Tree passage only with sword and shield equipped.
  (EnMd_BlockPath offset 60, OC push through actor wall checks, path 1 walk.)
- [x] Remove shortcut spawns; preserve equipment in existing saves.
- [x] Fresh-file route and save/reload pass human testing before M2c acceptance.
  Human reports "Human test good" after the requested route check (2026-09-26).
- [ ] Maze boulder path/collision and damage work by final M2 acceptance.

Full shop stock, other chests and wider NPC work remain M3. No child Lost Woods
Mido gate. Audit source placements, flags and full actor drops during implementation.

### BUG-028: Registered colliders follow reused actor slots

**Labels:** `bug`, `priority: P2`

**Assignee:** Claude. **Milestone:** M2b, before live actor contacts. **State:** Closed after Astra re-review (2026-09-26).

Register a collider, kill its owner, reuse the pool slot, then resolve contacts.
Expected: old registration ignored. Actual: contact identifies the replacement
actor. Reproduced against the compiled fixture; see M2B_REVIEW.md.
Current actorless grass path is unaffected.

- [x] Snapshot and validate registered ownership for AT/AC/OC.
- [x] Regress attacker/victim replacement before resolution and OC reuse.

### BUG-029: Alternating attackers defeat once-per-attack memory

**Labels:** `bug`, `priority: P2`

**Assignee:** Claude. **Milestone:** M2b, before multiple live damage sources.
**State:** Closed after Astra re-review (2026-09-26).

Keep attack identities unchanged; overlap one victim with A, then B, then A.
Expected hit counts 1,1,0 under the stated once-per-attack rule; actual 1,1,1.
Only the last attack is remembered. Reproduced with existing fixture tags;
same storage issue applies to distinct actor handles. Grass cut bits prevent
duplicate grass rewards, so current grass acceptance need not wait.

- [x] Bound victim history per attack or implement/document source timer policy.
- [x] Cover interleaved actor attackers and actorless tags.
- Multiple hurtboxes and history eviction remain tracked separately as BUG-030.

Re-review: actor_sys 38/38 and gameplay 60/60 pass. BUG-029 accepted as a
bounded four-entry per-collider history, not an unlimited per-actor guarantee.

### BUG-001: Wall sphere pass drops line-hit precedence

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** before wall-damage contact consumers.
**State:** Open.

#### Description and evidence

M1a disclosed that `bg_wall` does not seed the sphere pass with its line-test
polygon. Source preserves a prior data1 bit-27 wall when choosing contact identity.
Code-inspected gap; no player-visible failure reproduced. See M1A_REVIEW.

#### Steps / expected versus actual

Construct a line hit on a bit-27 wall followed by another sphere-pass wall.
Expected source contact precedence; current sphere pass starts without the line
polygon. Add an exact geometry repro when integrating that consumer.

#### Acceptance criteria

- [ ] Preserve source precedence and test the two-contact case.
- [ ] Ordinary wall movement remains unchanged where precedence is irrelevant.

### BUG-002: Malformed collision decode can damage live scene data

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** scene-load recovery / M8.
**State:** Open.

#### Description and evidence

`scene_flow.c` reuses the active collision buffer; `bg_mesh_decode` writes before
all metadata validation completes. A later rejection may leave the old scene's
collision partially replaced. Code-inspected and disclosed by Claude; normal
built assets/human smoke have not demonstrated a failure. Not an active blocker.

#### Steps / expected versus actual

Load a valid scene, then inject a same-size collision asset with invalid late
metadata. Expected safe failure with intact old scene or stopped gameplay;
current decode can partially overwrite live arrays before returning false.

#### Acceptance criteria

- [ ] Validate before mutation, stage the decode, or stop gameplay safely on failure.
- [ ] Malformed-load regression proves no continued use of partial collision data.

### BUG-003: Locomotion timing checks assume pre-analog implementation text

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next locomotion-test edit.
**State:** Open.

#### Steps to reproduce / evidence

Run `python -m unittest discover -s game/tests -p test_locomotion_timing.py`.
Previous review observed one failure and one error: source checks require old
`kokiri_camera_input_heading(demo_yaw, walk` and
`link_anim_roll_input(kokiri_camera_walking()` strings. Analog integration replaced
those calls; these checks predate M1a. Not rerun during this bounded re-review.

#### Expected versus actual

Tests validate current heading/roll cancellation behavior; stale text matching
instead fails even when that behavior remains valid.

#### Acceptance criteria

- [ ] Update checks for actual behavior/current integration without weakening roll rules.
- [ ] Module passes and still detects incorrect heading/roll cancellation.

### BUG-004: Locomotion clips play at 2/3 of the source rate

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M8 polish or the next locomotion
animation task. **State:** Open.

#### Description and evidence

z_skelanime.c LinkAnimation_Loop/Once advance `playSpeed * R_UPDATE_RATE * 0.5`
= 1.5 x playSpeed frames per 20 Hz update, i.e. playSpeed frames per 30 Hz
step. TRAVERSAL_TIMING.md said 2/3 frame per step; its row is corrected (M1c).
Locomotion clips keep the existing 2/3 presentation tuning (ANIM_PARITY_NOTES
item 4); M1c ledge climbs use the source rate. Code inspection, no report.

M1g handoff adds a roll-specific duration mismatch (reported by Claude, not
independently timed in Kronos): source Player_Action_Roll ends at frame >= 20
with playSpeed 1.25, about 0.8 s; the port plays all 32 frames at its slower
cadence, about 1.6 s. This predates M1g. Revisit both the end frame and playback
rate during roll timing/polish work; do not fix only the shared cadence.

#### Acceptance criteria

- [ ] Decide per clip: source rate (plus the source's per-action playSpeed) or
  the documented tuning; keep foot sliding acceptable.

### BUG-005: M1c wall/ledge port subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** wall-sensitive actions (climb, crawl,
push). **State:** Open. Disclosed by Claude, M1c; code inspection.

- `unk_880` wall run-speed cap (Player_ProcessSceneCollision) not ported.
- Fixed M1f: a step with no horizontal move now runs the wall sphere at
  rest (kokiri_collision_actor_probe_still), as the source does.
- Air steering: M1d keeps an action's speedXZ (hop 2.5, 250 jump 1.0, let go
  0.8) with the stick centred, decaying 0.1 a frame; with input, the input
  speed replaces it at once instead of func_8083DFE0's 0.05 a frame rise.
- Hang: the feetFloorFlag auto-drop (Player_Action_8084BBE4) is not ported;
  the source's stick-forward wall climb from a jump at yDist >= 150 and the
  vine/ladder start from a walk-off (floor property 6, WALL_FLAG_3) are M1e.
- Headroom revert: the source's one-frame y = floor at the new x/z, and the
  crushed flag for a ceiling on another bgId, are not reproduced.
- Floor snap uses the floor-class query (as gravity does); RaycastDown's
  up-facing steep walls and isSoft -1 are not floors there.
- Crawl wall radius/height (10/15/30) belongs to the crawlspace milestone.

#### Acceptance criteria

- [ ] Port each item when its consumer lands, with a regression test.

### BUG-006: Talk takes an A press before the ledge climb

**Labels:** `bug`, `priority: P2`

**Assignee:** Astra. **Milestone:** M3 NPC placement. **State:** Fixed in code; Kronos pending.

Source list8 checks Player_ActionHandler_12 before TALK; gameplay_step()
consumes A for talk/pickup/menu first, and only an unclaimed A reaches the
ledge climb. Only differs with an NPC in talk range facing a 27+ ledge.

- [x] 2026-09-27: demo.c preflights the real ledge selector before sending A
  to gameplay. A valid moving/grounded climb reserves the press for traversal;
  open text, pause, carrying, attack/shield and invalid ledges keep their rules.
  `test_ledge_talk.py` executes the selector/preflight, including the delayed
  dynamic-wall case. No extra position update or duplicated climb action.
- [ ] Kronos: ledge beside NPC, ordinary talk, final text advance on both pads.

### BUG-007: Floor jump/land SFX and the second climb-end voice are missing

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** SFX bank rework / M8. **State:** Open.

No NA_SE_PL_JUMP / NA_SE_PL_LAND (+ floor offset) sample exists; every jump,
landing and step-up plays voices only. M1d hang: NA_SE_VO_LI_HANG_KID,
NA_SE_PL_SLIPDOWN and NA_SE_PL_CLIMB_CLIFF are also missing (the footstep
stands in for NA_SE_PL_WALK_GROUND and the landing; CLIMB_END plays). NA_SE_VO_LI_CLIMB_END_KID picks rand 2
of EFFECT_35/36; only EFFECT_35 fits (core bank now 852 sound-RAM bytes spare).

- [ ] Add floor jump/land sounds and EFFECT_36 when sound RAM allows.

### BUG-008: Source-snippet host tests no longer compile

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next edit of these tests. **State:** Open.

test_title_flights slices demo.c from title_showcase_camera to recover_link;
M1b put link_standing/link_leave_ground in that slice, so it no longer
compiles. test_opening_audio (cutscene.c), test_forest_partition and
test_equipment_draw (kokiri_sgl.c/main.c) fail the same way on code M1c did
not touch. Seen in the M1c full run (628 tests: these 4 errors + BUG-003's 2).

- [ ] Extract by stable markers or compile the real units; all four pass.

### BUG-009: Link drawn at 1.45x the source child against source headroom

**Labels:** `bug`, `priority: P1`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** human visual check / M8. **State:** Open.

The Link recipe draws at 0.0145 (source actor scale 0.01): 63 units tall,
the source child is about 44. M1c movement uses the source headroom
(ceilingCheckHeight 40), so under a 40-62 ceiling his drawn head can clip.
S1.COL has no ceilings in that band over its floors (scan, M1c). The
step-up rise constants use the drawn scale, so the climb reads correctly.
M1d root transfers (pull-up x/z, let-go pelvis) also use the drawn scale:
letting go of a hang puts the actor ~60 below the top where the source's
child goes ~35.

- [x] Human judges the scale; if changed, rebuild RISE and Navi LINK_HEAD.
- Fixed in code 2026-09-28 (human: "Fix Link P1 issue", raised to P1). Recipe
  0.0145 -> source 0.01: Link bakes 44 units tall, same scale as En_Ko/Md/Sa.
  RISE constants regenerate from the scale. Camera Normal1 player height
  62 -> Player_GetHeight child 44: dist 93/139, yOffset -9, hang -37, climb
  -14/-5. Collision head sphere 54 -> 36 (+8 radius = 44). Kronos pending:
  Link size vs Kokiri, camera framing, step-up/hang/let-go, jump under
  bridges, Navi hover, sword/shield on back.

### BUG-010: 250 jump has no mid-air ledge grab yet

**Labels:** `bug`, `priority: P1`

**Assignee:** M1d. **Milestone:** M1d hang. **State:** Closed (2026-09-26).

Human decision 2026-09-26: M1c starts the source 250 jump on ledges 47+;
Player_Action_8084411C's grab (ledgeClimbType >= 2, yDist < 150, total > 45)
and the hang/pull-up are M1d. Until then Link hops at the wall and lands back
below. No snap-to-top shortcut. Full ledge-climb acceptance waits for M1d.

- [x] M1d: grab, hang, pull-up and drop from the 250 jump and from walk-off
  (host tests, test_player_bg). Code accepted in M1d review (2026-09-26).
  Human Kronos check confirms tall-ledge jump/grab, hang, A drop and pull-up;
  porch slow walk hangs. Runtime acceptance recorded 2026-09-26.
- [x] M1e: pull-up and let-go now measure from sSkeletonBaseTransl
  (-57, 3377, 0) x 0.64, not 0 (about 1 unit).

### BUG-011: Released digital pad can interrupt climb early

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next climb/input integration.
**State:** Open.

#### Description and evidence

M1c review, code inspection: `player_input_motion` writes digital walk/run speed
before returning whether a direction is held. `demo_update` passes that speed to
`link_anim_roll_input` even with no direction. `climb_step` uses only
`roll_input_speed_q8 > 0` to interrupt the last four frames. Consequently a released
digital pad still looks like movement to the climb interrupt; centered analog does
not. No Kronos repro performed. No blocked gameplay demonstrated.

#### Steps / expected versus actual

Fixed in M1d (code accepted 2026-09-26; Kronos check pending): demo.c hands link_anim_roll_input 0 unless
player_input_motion reports a held direction.

Start a 100/150 step-up on a digital controller, then release directions. Expected:
finish the un-interrupted clip. Current wiring supplies nonzero speed and can end
in the last-four-frame interrupt window, resetting the draw offset early.

#### Acceptance criteria

- [ ] Climb interrupt uses actual requested movement, independent of roll-facing policy.
- [ ] Released digital and centered analog finish normally; held movement still interrupts.
- [ ] Regression covers demo input-to-animation wiring, not only direct state calls.

### BUG-012: 250-jump retained air speed is cleared before launch

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next air/grab integration.
**State:** Closed (2026-09-26; code review and human Kronos check).

#### Description and evidence

M1d code review: demo.c assigns `link_air_speed_q8 = 256` when starting JUMP250,
then the final `if (grounded || intent_speed)` clears it on grounded preparation
steps. The frame-8 launch sets vertical velocity but does not restore air speed.
Thus the claimed retained 1.0 speed is unavailable with centered input, including
as the speed required by player_hang_grab. This differs from the disclosed gradual
air-speed approximation. Holding direction still provides a path; no severe route
block demonstrated. No Kronos reproduction performed.

#### Steps / expected versus actual

Start a 250 jump, release direction during preparation and leave it centered through
descent. Expected retained launch speed permits the applicable grab. Code path
clears it before launch, so speed-dependent grab can be refused.

M1e review: fix attempted, but incomplete. The frame-8 launch sets
link_air_speed_q8 256 along the facing, then the same update's final cleanup
clears it again: grounded was computed before launch and remains true.
Keep P2/open. Cover the actual launch/cleanup integration order when fixing.
See [M1E_REVIEW.md](M1E_REVIEW.md); no Kronos reproduction claimed.

Second-fix review: the `launched` guard now prevents grounded cleanup on the
launch update. Accepted by code inspection. Keep open for runtime verification;
no host test executes this demo_update path. Existing clean map gap: 34,944 B.

#### Acceptance criteria

- [x] Initialize/preserve action air speed at actual launch without retaining stale ground speed.
- [x] Manual launch/grab check: human reports tall-ledge jump works, hangs, drops with A in response to the requested check.
- [x] Human reports normal movement good; existing hop/let-go paths unchanged by the launch guard.

Resolution: second launch-guard fix accepted. Human Kronos check on 2026-09-26
supersedes the pending-runtime notes above. No automated demo_update integration
test exists; manual acceptance does not claim one. Human subsequently confirmed
pull-up works too.

### BUG-013: Floor/ceiling/wall point-in-poly slack

**Labels:** `bug`, `priority: P1`

**Assignee:** Claude, M1e. **Milestone:** fixed in M1e; close after review
and a Kronos walk check. **State:** Closed (2026-09-26).

M1a ported the "Approx" tests (CollisionPoly_CheckYIntersectApprox1/2,
Check{X,Z}IntersectApprox -> Math3D_TriChkPointPara{Y,X,Z}Impl) as a flat
1-unit edge tolerance. Source: box +1, near a vertex, edge determinants
within 300 (about 300/edge-length units), or within 1 of an edge for a poly
facing the axis. Lines (detMax 0) were right. Found in M1e: a 400-wide
25-high step blocked instead of being walked onto; narrow polys were too
strict. Fixed in kokiri_collision.c `inside_approx` for bg_floor, bg_ceiling
and the wall sphere. The legacy kokiri_collision_floor (gravity, standing)
keeps its strict inside test.

- [x] Source test ported; M1c step boundary retested (25 climbed, 26 blocks).
- [x] Kronos: human reports normal movement all good (2026-09-26).

Resolution: source tolerance fix accepted by code review, host regressions and
human runtime check.

### BUG-014: Climb port subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** vine-heavy scenes (M5). **State:** Open.

- Player_Action_8084BF1C's own Actor_UpdateBgCheckInfo (wall push radius 6,
  ceiling) is not run; func_8083F360's 12-unit hold does the positioning.
- Dyna wall carry while climbing (wallPolyActor prevPos) not ported.
- SkelAnime_UpdateTranslation turns prevTransl by prevRot; the port turns the
  whole step's delta by the current facing (differs only while turning).
- Climb sounds: NA_SE_PL_WALK_GROUND + wood/vine offsets use the footstep
  sample; the ladder-end landing uses it too.
- Swimming/iron-boots start conditions and PLAYER_STATE2_12 idle flag unused.

### BUG-015: Climbing down Link's house ladder from the porch

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** human check against real OoT.
**State:** Open.

S1.COL's lip at the ladder top (polys 784/785, wall type 3 = WALL_FLAG_2) is
20 high. func_8083EC18's climb-down start needs BGCHECKFLAG_WALL; the wall
sphere's centre (+26) is outside the lip's box (+1), so under the ported
rules walking at it starts nothing and Link walks off (hang/fall rules
apply). Climbing UP onto the porch works (host test on S1.COL). If real OoT
climbs down here, something in the start path is still missing.

- [ ] Human: on real OoT, walk from the porch to the ladder top; record result.

Human Kronos observation (2026-09-26): ladder ascent works; slow walking from
the porch hangs, running jumps off. No ladder descent. Original OoT comparison
still pending; keep P2 open, nonblocking for M1f.

### BUG-016: Grounded ceiling check ignored the glue dip

**Labels:** `bug`, `priority: P1`

**Assignee:** Claude, M1f. **State:** Open (tunnel fix accepted; remaining checks below).

Actor_UpdateBgCheckInfo checks ceilings over ceilingCheckHeight + dy - 10.
A grounded actor has dy = -7.5 each update (velocity -4 glue + gravity,
x1.5). The M1c port used dy 0, so headroom was 40 not 32.5, and crawling
30 not 22.5: the sword maze's 24-high crawlspace refused all motion. Fixed:
the ground dip is 7 (integer-exact for 7.5), kept as a distance. The +50
floor ray's start is not lowered by the dip (step-up up to 7.5 higher than
source; logged here).

- [x] Crawlspace passes; headroom retested (32 blocks, 33 passes).
- [x] Crawlspace: human reports current build good; M1f code review accepted.
- [ ] Kronos: check other low roofs explicitly; location/result not yet recorded.

Remaining floor-ray height approximation is deferred, nonblocking for M1g.

### BUG-017: Crawl port subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M1l camera / M8. **State:** Open.

- OnePointCutscene 9601/9602 (crawl exit camera) not ported (M1l).
- Camera_Subj4 first person ported (M1f); its 10-frame zoom-in and the
  eyeLerp yaw sway are not.
- Crawl sound lists (D_808548B4, D_808548D8) not played.
- Fixed in M1l: require crawl camera setting 0x1E, valid vector range and
  nonzero XZ line before enabling first person. Invalid data keeps the normal
  camera and Link visible. Host checks include real sword-maze bgCam 9.
- In the tunnel the source draws the held tunnel_start frame with its raw
  x/z root (movementFlags cleared); the port keeps x/z pinned.
- Fixed: the enter prompt now shows "A: Enter" on the prompt row (ahead of
  Talk, as handler 5 precedes TALK).

### BUG-018: M1g turn/bonk source subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M8 polish; M7 when bonk actors appear.
**State:** Open.

The light analog band now supplies direction without movement. Above that band,
speed retains the existing linear curve, not Player_CalcSpeedAndYawFromControlStick's
curved mapping. Revisit with analog locomotion polish; no current route blocked.

Roll bonk plays the climb-end voice. BODY_HIT's sample, screen shake and rumble
remain absent. Add the source sound when revisiting the core SFX budget. Roll's
pre-existing duration mismatch is BUG-004, not corrected by M1g.

Tree actor overlap and large-crate break/drop signaling remain for integration
when those actors exist. Claude's source audit found no relevant bonk-drop actors
in current Kokiri/Lost Woods actor lists; Hyrule Field trees belong to M7. Apply
the drop rule when adding them; wall bonk alone does not implement their rewards.

- [ ] Source speed curve chosen/ported with analog feel check.
- [ ] Body-hit SFX and feedback implemented or explicitly scoped out.
- [ ] Relevant actor bonk signaling and source drops implemented with actors.

### BUG-019: Bonk/hang voice sounds wrong to human

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** next Link SFX pass. **State:** Closed
(human Kronos 2026-09-27: fixed).

Human M1g Kronos pass: movement/bonk works, but Link sounds like a girl on
bonk/hang. Bonk currently uses ACTION_CLIMB0. Exact hang event/sample is not
identified. Compare source child sample selection, tuning and runtime playback
pitch before replacing the voice; no incorrect sample or pitch has been proven.

- [ ] Reproduce both cues and identify samples/pitch.
- [ ] Compare source playback and obtain human acceptance.

### BUG-020: Push-block live integration and source subset

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** before Deku Tree room 5 acceptance.
**State:** Open.

Human deferred the proposed live push-block test setup. No diagnostic block is
inserted in Kokiri Forest. Actor core and Link interaction have host coverage,
but scene asset loading/spawning/drawing and a live dynamic actor are still
required; M1h is not runtime accepted merely because its helper tests pass.

Supported core: real collision mesh, small/medium/strength-gated size variants,
20-unit push/pull, cooldown, wall checks, five-point floor support, falling and
rider carry. Source switch-dependent immobility, stacked-block movement, full
floor-switch signaling, rotated support corners and block/push SFX remain
integration work. Current core does not claim full Obj_Oshihiki parity.

- [ ] Source room 5 spawn/params/mesh/draw and switch semantics integrated.
- [ ] Push, pull, obstruction, ledge/fall and rider behavior pass in game.
- [ ] No invented block drops: source Obj_Oshihiki has no Item_Drop path.

### BUG-021: Grass patch behaves like a raised floor

**Labels:** `bug`, `priority: P1`

**Assignee:** Astra. **Milestone:** Clean runtime check.
**State:** Closed. Human reports "Test good" on 2026-09-26.

Human marked this important (P1). Human reports Link steps onto grass patches
and rupees/items appear on top.
Expected: walk through the grass at ground level; grass can visually hide ground
pickups. Human also recalls a small grass/rustle effect and sound when walking
through it; confirm those details against source before implementing them.

Confirmed source scene grass polygons have entity-ignore flags. The modern
bg queries respected those flags, but legacy player floor/head-sphere queries
and build_actors' floor placement did not. Both now filter by source flags;
camera spheres use the camera-ignore flag. No scene geometry was removed.
Real examples: (60,-430) and (-480,190) have grass at y=28, ground y=1;
(-570,1720) has grass at about y=144, ground y=120.
Sword/shield placements now resolve to y=1. Their draw height also no longer
adds the artificial 46-unit grass-clearance offset (16px icon at scale two now
centres 16 units above ground, with a small bob).

Host tests cover the three real patches, player movement through grass, and
source-data pickup floor extraction. The old ledge test at (172,28,-483)
stood on ignored grass: from real ground y=1 it is a 59-unit 250-jump ledge.
Human: walk across the two item patches, collect items/rupees, and check grass
can obscure them. Rustle sprite/sound moved to separate minor BUG-024;
source behavior still needs verification. No grass drop behavior changed.

- [x] Identify affected patch and its source actor/collision data.
- [x] Host checks: Link walks through at ground height; pickups use correct floor.
- [x] Human confirms movement and pickup visibility in Clean.
- Rustle sprite/sound verification remains BUG-024.

### BUG-022: Carry props and full reward integration pending

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M3 props / M1i acceptance. **State:** Open.

M1i player action hooks cover attach frame 4, stationary put frame 4, throw frame
3 (speed +8, vertical 12), throw-only props and safe cancellation. Only the
strengthless bush failure is wired to current forest props. Successful carry
needs actor ownership/hand transforms, carrying locomotion, thrown collision,
break effects and source rewards; it is not yet live gameplay. Large/heavy rocks
need their separate strength/actions. Failure voice/prompt remain polish.

Source audit: EnKusa_DropCollectible uses spawn-selected random tables for types
0/2, seeds/hearts for type 1; thrown impact uses that drop path. Existing
build_actors.py grass_rupee_slots is explicitly rupee-only and is insufficient
for adding successful bush throws. Obj_Tsubo/En_Ishi must likewise retain their
own params, restrictions and reward paths. No new prop/drop actor was added here;
failed lifting neither cuts a bush nor awards a drop.

- [ ] Successful pot/rock/bush carry and throw integrated with actual actor owner.
- [ ] Source drops, conditions and collectibles supported in the same prop task.
- [ ] In-game carry, put, throw, wall impact and scene transition checks pass.

### BUG-023: Slope/fall runtime and damage integration pending

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M1j runtime / M2 health. **State:** Open.

Slope movement/poses are wired; needs forest slope check. Slip sound, dust,
animation morph and exact pushed-speed interactions remain approximations.
Sliding uses source grounded floor tolerance plus the omitted downward glue
distance (18 integer units), preventing steep slopes from becoming free falls;
ordinary locomotion's previous ground-follow tuning remains unchanged.

D_80854600 fall damage policy is implemented/tested: distances 400..799 deal 8
health units, >=800 deal 16, floor types 6/9 exempt. It is not applied to live
health yet. M2 owns damage reactions, invulnerability, death and continue, which
must be integrated together; do not mark all fall consequences or M1 complete.

- [ ] Forest sliding, uphill resistance, flat exit and jump/ledge behavior verified.
- [ ] Landing calls policy once and M2 owns health/reaction/death consequences.

### BUG-024: Grass overlap rustle effects and sound

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** M3 grass / M8 feedback. **State:** Open.

Human recalls a small grass sprite/rustle sound while passing through scene
grass. BUG-021 collision and item-height fix passed the human check; this is
the separate feedback follow-up. Confirm source effect triggers and material
audio selection, including the entity-ignore grass surface above the solid floor.
Do not restore solid collision or force pickups above foliage for visibility.

- [ ] Verify source overlap effect and sound, then implement missing feedback.
- [ ] Keep grass pass-through and ground pickup placement from BUG-021.

### BUG-025: Water traversal source subset and runtime acceptance

**Labels:** `bug`, `priority: P2`

**Assignee:** Astra. **Milestone:** M1k human check; M2/M5 integration.
**State:** Open.

Child swim entry/exit, buoyancy, A dive/hold/release, depth cap, return to surface,
wall/floor/roof collision and sloped-bank exits are wired. X supplies a stroke;
land sword, shield, roll and Y jump are suppressed while water owns the step.
Current source subset: no entry splash/ripples, water SFX, underwater filter,
full body pitch/animation morph, HUD dive prompt, targeted/back/side swimming, water-specific
ledge exits or running-jump water animation. Dive-turn uses an 8-step recovery
instead of the source pitch condition. Movement rates use fixed-point source
values but the input speed curve remains the existing port's approximation.
General follow camera is retained until the traversal camera pass.

Human subsequently reports "Water is good. Continue next" (2026-09-26).
Record water runtime acceptance; individual unreported cases and dungeon water
remain to be checked. This supersedes the earlier unavailable-pond note.

The 450-step submerged hook corresponds to source's 300 updates before the
environmental hazard is eligible; it is NOT a drowning deadline. M2 must wire
health-dependent environmental timers, death and respawn together. An obstructed
rise currently remains swimming under the roof; death/respawn is still pending.
No scale upgrade in live inventory yet (base 120 depth); host input tests can
exercise the 240/360 limits. Do not mark all M1 water consequences complete.

Real source ydan water boxes belong to rooms 3, 5, 9, not room 0. Host test uses
all 2321 source collision polygons and checks those room filters. The current
disc collision exporter cap is 2048, so M5 must budget/raise that cap or partition
the collision before staging ydan. Host coverage does not prove dungeon runtime.

- [x] Human reports water works in Kronos (2026-09-26).
- [ ] Explicit pause/resume and dungeon-water acceptance when available.
- [ ] Verify missing animation/FX/audio and ledge-exit behaviors against source.
- [ ] Integrate drowning, death and respawn with M2; exercise ydan in M5.

### BUG-026: Dialogue special characters and missing dither backdrop

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next dialogue/UI pass. **State:** Open.

Human screenshot: Mido's "Mr. No Fairy" line shows stray yen-like symbols
around the quoted nickname. Character dialogue draws over the scene without
the readable dither backdrop used by cutscenes. Human explicitly requests
logging this separately while milestone work continues.

Trace source message decoding, text encoding and glyph mapping before changing
the string: do not guess whether the visible symbols are control bytes, escapes
or unsupported glyphs. Dialogue should render intended special characters and
use a cutscene-style dither backdrop. Keep UI on VDP2; no VDP1 texture allocation.

- [ ] Mido line renders intended punctuation without stray symbols.
- [ ] Other supported special characters and message controls remain correct.
- [ ] VDP2 dither backdrop covers each dialogue page and clears on close.

### BUG-027: Traversal camera source subset and runtime acceptance

**Labels:** `bug`, `priority: P2`

**Assignee:** Astra. **Milestone:** M1l human check / M8. **State:** Open.

New traversal adapter uses Normal0 Unique1 hang offset/pitch and Jump2 climb
offsets/near-end pitch, scaled to the existing 62-unit model camera. Hang holds
entry yaw; climb follows the wall-facing heading even when stationary. At-point
eases through entry/exit and camera-ignore-aware line collision shortens the eye
ray. Normal mode still uses the existing follow behavior.

This is a fixed-point adaptation, not a complete port of Camera_Jump2/Unique1:
source waist-based hang-entry yaw, climb yaw freedom after entry, cached floor
state, distance-envelope logic, per-field rate interpolation, FOV variants and
Jump2's alternative collision ray remain follow-ups. Only traversal/return
gets the new collision ray; general Normal1 camera collision is still pending.
Crawl special exit shots and entry zoom/sway remain BUG-017. Swim Jump3 remains
BUG-025. No claim of full M1 camera parity or full M1 acceptance.

- [ ] Human checks ladder/vine ascent/descent, hang/pull-up/drop framing.
- [ ] Human checks nearby walls and smooth return to walking camera.
- [ ] Port remaining source camera details in the relevant polish pass.

## Bug report template

### BUG-NNN: Brief description of the failure

**Labels:** `bug`, `priority: P2` (or appropriate priority), `needs-triage` if unconfirmed

**Assignee:** Unassigned

**Milestone:** Relevant milestone or Backlog

**State:** Open

**Revisit trigger:** Specific dependency, affected feature integration or polish pass

#### Description

What fails and how it affects the player. State whether reproduced or suspected.

#### Steps to reproduce

1. Start from the relevant scene/save/controller state.
2. Perform the triggering action.
3. Observe the failure.

#### Expected behavior

Describe the intended result; link source behavior or an agreed requirement.

#### Actual behavior

Describe what was observed. For a potential issue, state that reproduction is
pending and give the code evidence; do not invent observed behavior.

#### Environment

- Build/commit:
- Emulator/version and 4 MB cart configuration, or host-test environment:
- Controller mode:
- Scene/room/save state:

#### Evidence and related work

Logs, screenshots, test output, relevant file/symbol and linked reviews/issues.
Include only available evidence; do not require screenshots for a code-only finding.

#### Acceptance criteria

- [ ] Reproduction no longer fails, or suspicion resolved with evidence.
- [ ] Relevant gameplay path remains working.
- [ ] Appropriate verification recorded; runtime versus host evidence distinguished.

#### Resolution

Fill when closed: fix summary or reason not planned/duplicate, verification,
commit/PR if available and date. Keep the issue record after closing.

## Feature request template

### FEAT-NNN: Brief description of the requested capability

**Labels:** `enhancement`

**Assignee:** Unassigned

**Milestone:** Backlog until assigned

**State:** Open

**Scope decision:** Proposed / approved with reference

**Revisit trigger:** Relevant milestone or explicit assignment

#### Problem or player benefit

What need this solves and why it matters to playable progress.

#### Proposed behavior

Concrete player-facing result. Separate required scope from optional additions.

#### Alternatives considered

Briefly list meaningful alternatives, including existing behavior if sufficient.
Omit if none are relevant; do not invent extra research work.

#### Dependencies and scope

Required systems/assets, affected files/owner, source reference where applicable,
and what remains outside the request. Link existing milestone plans rather than
duplicating their required features. A logged request is not authorization to start.

#### Acceptance criteria

- [ ] Agreed player-facing behavior works.
- [ ] Dependencies and applicable source/drop rules satisfied.
- [ ] Appropriate tests/runtime evidence recorded.

#### Resolution

Fill when closed: delivered behavior or reason not planned/duplicate, verification,
commit/PR if available and date.

### System UI / enemy-map follow-up - 2026-09-27

Fixed missing System page: Save/Load/Title, explicit default-No unsaved-progress
warning before Load/Title, live controller detection, blue selection vs gold
equipment. Enemy-map renderer now includes active hostile actors across mapped
scenes. Previously Clean only drew the old debug launcher/projectile, and the
code's final Start opened pause and hid the minimap. Completing Start is now
consumed until release. Cheat remains session-only, survives scene changes,
clears on new/load game/session end, and never enters saves. 193 focused checks
and Clean build pass; human Kronos check pending. Owner: Codex.
Audio startup record renumbered BUG-047 to avoid Claude's existing BUG-045
Game Over record; no change to either issue's status.

2026-09-27 Codex item/text follow-up: counts, saved C-slot assignment, stale pickup audio and text recoil fixed in code; human runtime review pending. Live stick/slingshot actions remain pending for item-action milestone. BUG-043: shared Clean build now only 448 B below SGL (0x06083E40).

### BUG-048: Death Save prompt cannot select No

**Labels:** `bug`, `priority: P1`. **Assignee:** Claude (M2e owner).
**State:** Open. **Reported:** human gameplay review, 2026-09-27.
**Milestone:** M2e regression; investigate with BUG-049.

Reproduction reported: die, reach the Save Yes / No prompt, attempt to choose
No. Actual: only Yes is selectable. Expected: both choices can be selected;
No skips saving and proceeds through the normal death flow. Prevents declining
a save. Controller type, attempted direction, scene and exact build not supplied.
Cause unknown; no agent reproduction or fix claimed.

Verification after repair: both choices on digital and analog pads, one change
per press, No performs no save, Yes reports actual save success/failure.

### BUG-049: Continue Yes spawns Link in sky/nowhere and freezes

**Labels:** `bug`, `priority: P0`. **Assignee:** Claude (M2e owner).
**State:** Open. **Reported:** human gameplay review, 2026-09-27.
**Milestone:** M2e blocker; address before further M3 expansion.

Reproduction reported: die, advance the death prompts, choose Continue = Yes.
Actual: Link loads into the sky/nowhere and the game freezes. Expected: resume
at a valid scene entrance with collision loaded and responsive gameplay.
Death location, scene/entrance, save outcome and exact build not supplied.
Cause unknown; do not label this a proven bad-spawn or memory-corruption cause.
No agent reproduction or fix claimed. Separate from BUG-045 presentation gaps.

Verification after repair: reproduce the reported path, check valid ground and
camera, movement/combat responsiveness, restored health and retained inventory;
check forest/interior deaths, Save Yes/No, and Continue No returning to title.

### BUG-050: Child Link death voice sounds like adult Link

**Labels:** `bug`, `priority: P3`. **Assignee:** Claude (M2e owner).
**State:** Open. **Reported:** human listening review, 2026-09-27.
**Milestone / trigger:** M2e death audio; check alongside BUG-048/049.

Reproduction reported: child Link dies. Actual: death voice sounds like adult
Link. Expected: child Link's death voice with original pitch and duration.
Adult sample selection is not yet proven: inspect source age/voice mapping,
extracted sample and playback rate/pitch before diagnosing. Preserve the
half-rate SFX policy; offline resampling must not lower playback pitch.
No agent listening verification or fix claimed. Verify corrected death voice
in game; retain Continue freeze (BUG-049) as the higher-priority blocker.

2026-09-27 Claude death-flow fixes (uncommitted, human Kronos pending):

- BUG-048 cause: demo.c ends each step with player_input_set_dialogue(
  gameplay_blocks_world()). Dead is neither paused nor talking, so the flag
  dropped to false and player_input discarded every D-pad menu edge; only
  the default Yes could be confirmed. Now `|| gameplay.dead`.
- BUG-049 probable cause (not reproduced): Continue called enter_world()
  mid-step, re-reading the SAME scene from disc (whole-file jo_fs_read_file
  with the heap near peak, BUG-035). With Link already active, a failed load
  had no fallback and left the mode in LOADING. Now respawn_after_game_over():
  same resident scene respawns without a disc read; other scene loads like a
  door; failed load respawns in the resident scene at spawn 0; mode always
  reaches PLAY; the stale catch-up step is abandoned like take_door().
- BUG-050: CHAN_6424 (NA_SE_VO_LI_DOWN_KID) -> transpose 1, notes 0/1/2 ->
  Soundfont_0 EFFECT_1/2/3 = SAMPLE_0_127/128/129, sequential 98/106/58
  ticks at 96 ticks/s. Build matches; OCT -3 plays 5512.5 Hz at true pitch.
  Adult CHAN_625F uses EFFECT_14..16 (143..145), not used. Likely cause:
  5.5 kHz storage (bible half-rate rule) removes >2.7 kHz brightness, so the
  child voice sounds darker. Not changed: exemption (~13.5 KB more sound RAM
  at 11025 Hz) needs a human decision.
- BUG-051 new: human 2026-09-27, boulder moves/damages/knocks down correctly
  but mesh does not roll.
- Clean build: .bss end 0x06083EE0, 288 B below SGL. 253 focused checks pass.

Human update (2026-09-27): lower importance to P3, deferred audio polish.
Does not block RAM work or M3. Human identifies the heard voice as adult Link;
actual built-sample/playback cause remains unresolved. Source mapping checks
alone do not settle the audible report. Keep half-rate policy; no rate exception
requested. Revisit during M8 audio polish or the next death-audio change.

### BUG-052: Loading a Game Over save starts Link dying

**Labels:** `bug`, `priority: P0`. **Assignee:** Claude (M2e owner).
**State:** Open. **Reported:** human gameplay review, 2026-09-27.
**Milestone / trigger:** M2e save/load regression; fix before further M3 expansion.

Reported reproduction: die, save on the Game Over screen, then load that saved
game. Actual: the loaded game starts with Link dying. Expected: loading the
save starts a playable, living Link with the source-defined restored health and
valid spawn. Blocks normal recovery through the saved adventure. Repeated
reload/death loop and permanent save corruption are not established.
Scene, slot, exact build and intervening Continue/Title choices not supplied.

Cause unverified: inspect saved health, load-time health restoration and reset
of transient death/reaction state against the original game. Do not assume
zero health was serialized or label the save corrupt without evidence.
Separate from BUG-049 (Continue spawn/freeze); test both paths after repair.
No agent reproduction, runtime check or fix claimed in this logging turn.

Acceptance: Game Over Save Yes -> load the same slot produces a living,
controllable Link; repeat after forest/interior deaths. Verify inventory/flags
survive, ordinary saves still load, and Save No leaves the previous save intact.

2026-09-27 Claude BUG-043: triggers + title paths moved to cart
(MUSICTRG.BIN/TITLEPTH.BIN). Clean gap 14,656 B, Standard 11,360 B. Heap
peak (BUG-035) needs human Standard-build row 27 reading. Kronos pending.

### BUG-053: Pause corruption after Continue / Link room

Human screenshot and live Kronos capture confirm displaced pause art and
unreadable glyphs. Read-only inspection proves both the page and font buffers
match the rebuilt mounted ISO exactly two sectors (4096 B) late. Emulator
started before ISO rewrite and still runs the older binary/file positions.
See [live evidence](CONTINUE_MENU_CORRUPTION_2026-09-27.md).

P1; owner Codex. Cause of this captured corruption: disc replacement under a
running session. No renderer change warranted from this evidence. Cold boot
with an unchanged disc and repeat Continue in house/forest before closing;
no fresh-boot acceptance claimed. Runtime session preserved. Never rebuild
mounted test media. Separate from BUG-049/052 gameplay recovery defects.


### BUG-054: Fresh-boot title freezes with music and VDP1 0 FPS

- Priority: P0. Owner: Astra. Code fixed; target retest pending.
- Human reported 2026-09-28; fresh boot after build confirmed.
- Live CPU evidence: SDK exact-size allocator loops in the full 51200-byte
  work zone during action_audio_init callback allocation, despite free cart
  zones. Music interrupt continues; main draw callback is never registered.
- Fix in heap_profile.c: bounded exact-size scan with next-zone fallback;
  shared SDK unchanged. Five focused allocator tests pass.
- Clean rebuild passes; 5568 B below SGL (160 B fix cost).
- Retest: cold boot same Clean image; moving title forest and music together.


### Report: Brother dialogue flickers and teaches unavailable camera modes (2026-09-28)

- P1, code fixed; Kronos acceptance pending. main.c no longer clears and
  repaints an unchanged dialogue page each frame. Speaker probes moved offscreen.
- C-Up camera implementation: five source house panoramas/overhead toggles,
  outdoor first-person, shop fixed by source rule. Temporary hold-L look removed;
  L toggles the map. Navi retains first claim on C-Up.
- Dialogue action labels resolve from saved preset, pad mode and jump binding
  before wrapping; extra pages preserve words and choice grouping.
- Source audit, limitations and human checklist: CAMERA_TEXT_PLAN.md.

### Human acceptance: dialogue and interior view (2026-09-28)

Human confirms long dialogue no flicker, dynamic labels look correct, interior
C-Up works. Close the reported flicker for the tested session; full controller
matrix/outdoor camera acceptance remains separate. Speaker bold was silently
falling back because its guard required ink in an unused destination cell.
Guard corrected; panel gains 4 px top/bottom padding. Visual retest pending.


### M3c/M3d follow-ups ? 2026-09-28 unbuilt checkpoint

Owner: Astra. Source implementation and acceptance remain separate; no bugs or
milestones are closed by host tests alone. See [M3c/M3d details](M3CD_IMPLEMENTATION.md).

- P2 visual/source parity: simplified sign-piece and thrown-prop/drop motion,
  missing pot/rock debris, collectible-fairy appearance, reduced gossip reaction,
  and heart/nut two-layer combiner approximation. Revisit during M3 runtime review;
  escalate if a reward or interaction fails. Item-dependent water/song reactions
  stay linked to those item integrations.
- M3b required follow-up: original Saria greeting camera/cues. Current greeting
  text closes its progression flag; this does not complete the cutscene.
- Context HUD follow-up: Read/Grab/Throw labels are absent from the current
  Talk/Open/Enter artwork bank, although context A interactions are implemented.
- Old Navi hint timer test: source branch ordering fixed, including fractional
  phase reset. Previously failed alone (3002 instead of 3001); now passes alone.
- Required next verification: authorized target build and real RAM gap, then
  Kronos props/chests/shop/pad/save checks. Last 7,424-byte gap is historical.

## Human Kronos verification (2026-09-28)

Human reports hearts, plant transparency, carry animation and on-screen text
instructions all look good in the current Clean disc. These four reported visual
regressions pass human review. This does not certify every controller preset,
throw/reload transition, shop occlusion or the full M3 milestone.
Current build: `game/build/game-clean.cue`, BSS end 0x06082e50, 4,528 B below SGL.
Baseline commit: 249cef5. Regression fixes remain uncommitted. Older status and
RAM figures below describe earlier checkpoints.

## Forest blue screen / missing greeting (2026-09-29)

- P1, owner Codex. Capacity defect fixed; reported runtime failure not yet
  reproduced. User can dismiss Jo's blue screen with Start while walking.
  Exact error text was unavailable; do not assume every blue screen is heap OOM.
- Forest baking omitted post-room NPC/prop textures. Staged actors require a
  conservative maximum 46,896 B / 522 slots (all props, both moving/story NPCs,
  every overlapping child visibility box). Reserve 64 KiB / 576 slots separately
  from the existing 32 KiB margin; enforce against staged assets before mastering.
- Keep actor upload cache invalid until props/masks also succeed. Previously a
  dismissed prop upload failure could cache an incomplete bank as successful.
- Preserve existing uncommitted Saria greeting work. Stop gameplay catch-up when
  it starts; verify greeting clips retain idle vertex/material ordering. Earlier
  saves may already contain the greeted bit from the old dialogue-close path;
  no save flags were cleared. Test first house exit on a fresh file.
- Clean rebuilt at existing game-clean.cue: room spare 33,504 / 34,688 / 103,360 B
  after actor reservation; BSS end 0x06083b30, 1,232 B below SGL. 213 focused tests
  passed (gameplay, NPC models/bank, cutscene skip, allocator, VRAM, directory).
  PowerShell wrapper returned 1 from compiler warning stderr; underlying build
  log confirms mastering and final map verification completed successfully.
- Pending human/Kronos: first house exit greeting, forest traversal/room changes,
  NPCs and props visible with no blue screen. No emulator session was run here.
## Hut-exit GFS_Open failure (2026-09-29 screenshot follow-up)

- P1, owner Codex. Screenshot identifies jo_fs_get_file_size / GFS_Open failed,
  with 40% dynamic memory usage. The earlier VRAM repair did not fix this cause.
- SDK fs.c derives JO_OPEN_MAX from JO_MAX_FS_BACKGROUND_JOBS, default 1.
  music_service keeps an LVL or PCM handle open between rendered frames.
  A Saria track/clip, door or room read during that interval cannot open a file.
- Set JO_MAX_FS_BACKGROUND_JOBS=2 in the project makefile. Both reads remain
  synchronous on the main thread; one persistent music handle plus one asset
  read is the required peak. Shared SDK unchanged; no disabled error guards.
- New host regression runs the real SDK size/read routines with a bounded mock
  GFS handle pool: capacity 1 reaches the screenshot's error, configured capacity
  2 reads successfully and retains the music handle. Runtime retest still needed.
- Clean rebuilt: extra handle costs 256 B, BSS 0x06083c30, 976 B below SGL.
  12 focused tests pass (filesystem handle regression, cutscene skip, NPC bank).
  Permanent prevention rule recorded in DOSEI-LEGEND-BIBLE.md by user request.
