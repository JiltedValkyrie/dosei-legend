# Dungeon room/door/floor-web checkpoint (2026-09-30)

Uncommitted on dev. All 12 Deku Tree room banks now registered in the normal
Clean build. Nine source shutters retain type/switch flags; the three En_Holl
passages use the existing streaming path. Shutters have original door geometry,
A-facing activation, lift/hold/close state, closed-door movement rejection and
source front/back clear/switch tests. Clear flags are not fabricated: absent
scrub/enemy/puzzle implementations still block the corresponding route.

Both source floor webs have original mesh/collision/placement and saved destroyed
flags. A central fall over 750 units begins the source-timed break; breaking
webs survive room streaming until their switch is set. Normal room unload removes
collision without granting progress. No source collectible drops for these actors.
Wall webs, fire/torch integration, switches/platforms, enemies, boss and story are
still missing. This is NOT a complete playable dungeon or M5/M6 acceptance.

245 focused checks pass, including real dynamic floor collision, room unload,
web-break persistence, shutter side/flag gates, swept closed-door collision and
all live room-bank files (including base-36 room A/B names). Clean build passes:
BSS 0x0607b510, 35,568 bytes below SGL; disc directory capacity 384. New SH-2
mechanism objects have no software-float references. Kronos boots to file select;
`game/build/dungeon-connected-boot.png` is boot evidence only, not traversal.
Build/test logs: `game/build/dungeon-connected-build.log` and
`game/build/dungeon-connected-tests.log`. Door animation/camera/SFX/A-prompt and
web edge deformation/particles remain presentation gaps; real gameplay testing
still required. Earlier checkpoint measurements and room-0-only status below
are historical.

# Dungeon pause map checkpoint (2026-09-30)

Fixed the map reward/menu mismatch: dungeon scenes now show the five source
Deku floor diagrams, menu directions select floors, visited rooms are blue and
map ownership reveals unexplored rooms. VDP2 only, using the existing page cache.
Save v8 persists visited rooms; v2-v7 migrate with unknown history clear.
Changed pause artwork/renderer, menu controls, gameplay visit recording and save
serialization. 229 focused gameplay/save/renderer checks pass; Clean build passes
with BSS 0x06079cb0 (41,808 bytes below SGL). Source-art preview inspected at
`game/build/dungeon-map-preview.png`; build log `game/build/dungeon-map-build.log`.
No in-game map/controller acceptance claimed. Compass markers and automatic
current-floor selection remain open (BUG-062). Full M5/M6 remains incomplete.
Uncommitted on dev. Earlier checkpoint measurements below are historical.

# M5/M6 implementation checkpoint - 2026-09-29

User authorized autonomous implementation and foreground testing. Work remains
uncommitted on `dev`. **Neither milestone is complete.** This is the current
status; earlier checkpoints below other handoff sections are historical.

## Live implementation

- Source manifest covers 12 Deku Tree rooms, two boss rooms and ten Woods rooms,
  including actors, objects, rotation/params, transitions, exits, water/cameras,
  spawn-to-room mappings and source hashes. See M5_M6_SOURCE_ROOMS.md.
- Live scene IDs: existing Deku Tree shell 7 (room 0); Lost Woods 8 (all ten
  rooms). Boss 9 remains an isolated preflight proposal, not a live registration.
  All 24 original room banks also pass the separate KRM1/KBG2 preflight.
- Woods' nine En_Holl tunnels now stream the resident scene. Source entrance
  table resolves forest/bridge returns and wrong-turn respawns. Kind 0 uses a
  single resident bank at the crossing, not source dual-room prefetch/fading.
  Invisible kinds 2/4/6 preserve source cylinder/width/height/load bands. Actual
  shutters still fail closed; no puzzle doors or debug warps were fabricated.
- C-item use: sticks swing with DMG_DEKU_STICK and break on accepted actor hits;
  X puts the stick away for the sword. Slingshot press draws the first-person
  aim view, release spends one seed and fires. Nuts spend one nut and throw a
  downward projectile, then flash/stun through the source DMG_DEKU_NUT mask.
  Swept seeds stop at geometry and actors; targets before a wall remain hittable.
  Ammo/ownership/pool limits are enforced; pause/dialogue freeze the world.
  Projectiles clear on room changes, held stick/fire survives room streaming,
  and scene reset/death clears transient items. No debug inventory grants.
- Stick fire has a 210-source-frame lifetime (315 fixed steps), extinguishes on
  putaway and consumes one on expiry. Torch/web ignition integration is pending.
  Seed/nut/stick visuals are compact flat stand-ins, not imported source models.
- Nut C assignment, source icon, ammo and assignment markers now work in pause.
  Existing save C IDs stay stable; nut is ID 3. Save v7 appends Deku map/compass
  bits and migrates v2-v6. Slingshot/map/compass and all six source dungeon
  chests are exported with source reward/text/treasure flags. Only room-0 map
  chest is on the current live dungeon route; other treasures await rooms.
- Dungeon and Woods area music route through NA_BGM_DUNGEON (24) and
  NA_BGM_SARIA_THEME (62), with original sequence banks. No gameplay CD reads.
  Audio bake supports long instruments under the SCSP per-sample limit,
  per-instrument source sample-rate overrides and zero-decay releases.
  Seed shot/impact and nut flash have resident source-sample SFX; these remain
  reduced single-layer playback, not full N64 effects sequencing.
- Post-Emerald exit guard uses the original moved endpoint. Mido blocks,
  speaks 0x1045, walks his source path and sets EVENTCHKINF_1C on arrival;
  then forest disappearance/house population follows existing source filters.

## Capacity and build

Sprite definition/picture/hash arrays moved to a guarded NOLOAD low-RAM section,
zeroed before jo_core_init, using a project-local SDK wrapper/linker script.
Shared SDK remains unchanged. Low RAM also holds streamed room metadata and
29,288 bytes of music triggers. Neither malloc nor SGL/sprite limits were cut.
Disc directory grew to 293 entries; guarded capacity increased 288 -> 320.
The normal Clean build includes these assets and retains all refusal checks.

## Verification

341 focused checks passed across gameplay, collision/item lifecycle, chest/save
migration, controls, pause, audio, room banks/portals, source manifests, directory,
filesystem handles and allocator. Full discovery initially ran 1,023 tests with
15 failures and five setup errors; updated equipment/room tests now pass. Four
unrelated stale extraction harnesses remain recorded in BUG_FEATURE_LOG.
Foreground boot/title/world rendering observed in Kronos:
`game/build/m5-m6-items-woods-boot.png`. This is not proof of a dungeon playthrough
or controller acceptance. Final Clean BSS ends at 0x06079850, 42,928 bytes below SGL.
The final image is game/build/game-clean.cue; build details are in m5-m6-build.log.

## Required work still open

M5: full dungeon room/shutter integration, mouth/intro, webs/torches/switches,
blocks/platforms/water mechanisms, map/compass display, dungeon enemies with
source models/AI/damage/drops, ordered scrub puzzle, Gohma/eggs/minions, heart
container/warp, Emerald/death/flashback story and dungeon/boss resume acceptance.

M6: Woods enemies/drops, placed pickups/grass, target and Skull Kid games, owls,
source tunnel fading, Saria bridge/ocarina chain, Field handoff and boundary
policy for Meadow/Goron/River. Unregistered source destinations are still
reported by the exporter; no invented gates added. M6b/M7 remain distinct.

Items: source hand/weapon models and animations, precise nut throw-frame timing,
stick wall-break/ignition/water behavior, source jump-stick damage classification,
slingshot targeting/reticle and digital-pad aiming acceptance, acquisition
presentation and runtime item/room-churn checks. See BUG-058 onward.

## Reproduce

```powershell
python game/tools/build_progression_manifest.py --notes game/docs/M5_M6_SOURCE_ROOMS.md
python game/tools/build_progression_rooms.py
python -m unittest game.tests.test_gameplay game.tests.test_save_file game.tests.test_player_controls game.tests.test_interior_audio game.tests.test_room_portal -q
powershell -NoProfile -ExecutionPolicy Bypass -File tools/launcher/build-game.ps1 -Variant clean
```
