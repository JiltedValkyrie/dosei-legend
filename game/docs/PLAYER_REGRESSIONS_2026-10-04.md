# Player regression fixes — 2026-10-04

Branch: main, continuing the local 2598d01 merge. Preserve shared changes.
Human owns emulator/hardware acceptance; no emulator launched in this task.

## Report and changes

| Human observation | Implemented change | Practical limit |
| --- | --- | --- |
| Capped save shows four items and Emerald only | Pause draws all 24 source inventory slots, 24 quest bits, equipment and upgrades from a fixed ItemId atlas. Labels include upgraded and trade/bottle variants; wrong-era items remain visible but dim. | Source slots have mutually exclusive upgrades/trade states. Ownership is not implementation of every weapon action. |
| Map always shows Kokiri | World marker reads each source scene's misc-settings area. Shared adult Bazaar/Shooting Gallery use the source Kakariko override. Name comes from current scene. | The existing detailed dungeon-floor implementation remains Deku-specific; full map discovery/floor coverage remains work. |
| Ocarina cannot equip | Stable C action 4 handles Fairy/Time Ocarina; source-slot actions retain original ownership/age gates. HUD pictures follow actual items, including same-slot bottle changes. | Unsupported weapon/item use explicitly denies; it does not pretend to execute. |
| Songs/Adult Link missing | API 18 bridges original z_message song/result/choice handling, all 12 source note sequences, five instrument notes, source warp entrances, Saria follow-up, and overworld Sun day/night reload. Level Select adds Child/Adult, with original child/adult Link assets sharing one renderer. | Unimported song puzzle actors, Temple sword time travel, dungeon Sun stun, Scarecrow recording and memory game remain incomplete. Native traversal remains approximate. |
| Generic houses have top view only | Source house panoramas now cover 12 known house types, including six newly generic types: kakariko, kakariko3, impa, malon_stable, labo and tent. C-Up toggles supported views. Virtual panorama bank IDs no longer become gameplay actor room IDs. | Source fixed-view shops retain their fixed camera/JPEG. Shop browsing and multi-backdrop Market variants remain pending. |
| Magenta door rectangles | Door bake establishes the original opaque setup, samples the wood texture and rotates normals correctly. | The common leaf still shares art across source regional variants. Full door-route coverage has registered-asset/source actor blockers. |
| Graveyard tomb looks broken | Offline baker folds provably opaque combiner alpha to 1 instead of treating dark intensity as transparency. Stale registered room banks are rebuilt. | Other converter approximations remain; human comparison pending. |
| HUD hearts flicker | Hearts compose in the inactive VDP2 bank before map entries switch; common sampling avoids per-pixel divides. C-item HUD banks also compose off-screen. | Target build does not prove scanout acceptance. |
| Cucco-populated Ranch/Kakariko extremely slow | Remove unused Cucco wing/head interpolation. Conservative 32-bit bounds reject distant collision triangles before source Fx narrow phase; defer static-wall square roots. | Existing wide narrow-phase math remains debt. No measured target FPS claim. |

## Controls and resource ownership

Level Select: Up/Down area, Left/Right room, L capped items toggle, R era,
A enter, B title. Capped items defaults **No**, era defaults **Child** on every
open; navigation/toggles do not mutate the loaded save. Confirmed test entry
uses a fresh in-memory file and binds no backup slot. No fake completion flags.

Assign Ocarina from pause using the existing assignment modifier + C direction.
While playing, A and the four D-pad directions supply the original five notes;
B cancels. Input does not also move, attack, jump or change the camera.
Pause freezes source updates and consumes its closing press. Source song rewards
update core quest bits before save copy-out. Saria yes/no/repeat dialogue follows
source child/adult hints; missing scene-specific Navi scripts use the original
0x15F no-script fallback. Native C Saria is not yet a source actor for proximity.
Failed scripted/door loads consume the request, rebuild the source scene at its
saved entrance and stop the stale step; they do not retry a warp every frame.

PAUSEINV.BIN is 56,272 B in VDP2 B0 (0x52000..0x5FBD0). Pause reads the existing
B0 backup, with no second heap/CD load. Initial HUD load uses one bulk read per
file through boot scratch. C banks occupy 0x4B000..0x4CF80; heart banks use
0x50000 and 0x51000, with atlas at 0x50800. No extra VDP1 actor slots for UI.

Adult Link is the original object_link_boy mesh: 379 vertices, 672 polygons,
184 tiles; child is 385/704/154. Both fit existing mesh/texture/equipment carves.
One pose buffer, joint matrices and alternate skin metadata use checked low-RAM
carves at 0x17800/0x18C00/0x19800. Drop/grass view scratch uses 0x19000 with the
same 24-row limit; used rows are filled before reading. Matrix reset explicitly
clears low RAM and invalidates the pose cache. Reserve
the larger age's complete texture/palette footprint and 184 sprite slots once;
room budgets include it. Age switches stage/validate assets, fence VDP1, and
publish model/animation together. Failed allocation/read/upload preserves the
previous live age, descriptors and VRAM. Peak temporary staging is about 479 KB,
including a replacement animation bank; no second resident animation bank.
Adult has its source skeleton/gear/common clips; existing crawl/climb special
actions still include child-authored clips. No first-person adult arm model.

## Verification

Host: actual imported collision differential preserves all 3,190 probes across
Ranch/Kakariko scenes; wall square-root calls fall from 27,214 to 701. UI tests
exercise complete inventory/quest rendering, source regions, shared adult shop
overrides, atlas lifecycle, hidden/visible hearts, item-bank composition, era
selection and save migration. Ocarina tests compare all 12 sequences and six
warp entrances with local source, plus ownership/restriction/cancel/playback and
Sun reload recovery, all 12 learned-song grants surviving a save remirror,
pause/closing input, Saria branches and failed scripted-warp recovery. Adult tests cover corrupt/partial files, allocation and
upload failures, draw-fence failure, repeated switching and NULL-free rejection.

Host batches cover 578 distinct passing cases, including the final poisoned
matrix/actor-view guards. Added Saria negative-fraction proximity checks use the
actual 32-bit Fx-word extraction; source 64-bit truncation is not used there.
Two inapplicable asset checks skip: the obsolete single-scene generated C table
and standalone progression cache. Current binary room banks have separate passing
staging/geometry checks. Logs: regression-stable-tests.log (three stale fixtures,
subsequently fixed), regression-logic-final-tests.log, regression-final-tests.log
and regression-carves-tests.log. The final Saria/entry/UI subset also passes 19 checks.

The full asset build initially stopped at a generated Ocarina include path;
the explicit path and make dependency are now fixed. Relinks hit the preserved
SGL boundary by 1,264 B, then 128 B. Link matrices and actor-view scratch now use
checked low-RAM gaps; cold setup functions use Os. Heap size, SGL limits and actor
capacities remain unchanged. The final WSL Clean relink passes with .bss end
0x06083E80, **384 B** below SGL. Logs:
regression-clean-build.log, regression-clean-link.log, regression-clean-fit.log,
regression-clean-final-link.log. The interrupted populated-scenes-bake.log is not
target verification.

`regression-target-audit.log` replays actual final build flags with LTO removed
for inspectable per-function probes, and archives matching linked main/core
symbols/disassembly. New UI/save/entry, age-loader, transition-recovery,
Saria/song and collision-bounds paths contain no wide or soft-float helpers.
Audited individual stack frames peak at 172 B (HUD), below the 1 KiB master
stack; this is not a proof of every complete call chain. Existing Fx narrow
phase and other legacy wide operations remain explicit migration debt.

The usual `build/game-clean.cue` / `build/game-clean.iso` is rebuilt. ISO size:
72,853,504 B. SHA256:
`E02E88BE03EE53D9C774E8D6F8C94992C3A5891D5B4AD5EEF75B1CBEB6ED7DE7`.
`regression-iso-audit.log` reads the mastered directory and compares all **889**
payloads byte-for-byte with staging, including the icon atlas, all five adult
files, door art, main executable and OOTCORE. Every CUE track exists. No emulator
was launched; screenshots, traversal and measured populated-room FPS still need
human acceptance.

## Remaining world work

The prior 75 registered scenes/35 missing source destinations and incomplete
429-profile actor ledger still apply until regenerated audits say otherwise.
Full NPC/dialogue/reward coverage, gameplay horses, complete two-way routes,
special entrances, source song actors, item actions and adult story progression
remain required. Boss meshes/hitboxes are unchanged; Link is separate from the
permanent NPC/non-boss sprite rule. Human visual/performance acceptance pending.
The old route audit overreads Kakariko cutscene-layer exit arrays into following
light data because their shared collision exit range is longer. Bound extraction
by referenced-data ranges and leave unresolved entries explicit; do not infer
routes from the bogus lighting values (for example 0xFFBE/0xEA7C).

The previous commit/branch migration is local. Remote publication/deletions
remain blocked by the earlier automatic approval review requiring explicit
approval of the GitHub destination; this regression task did not retry that push.
