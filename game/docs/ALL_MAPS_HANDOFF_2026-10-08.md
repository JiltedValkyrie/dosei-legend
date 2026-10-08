# All retail maps: registration and asset admission

Human report: Level Select showed the Deku Tree and several boss rooms, while
the other dungeon maps were absent. Human scope then expanded to every map.
The cause was scene registration filtering, before W0a's scene loader ran.

The source table contains 101 retail maps and nine entries inside
`#if DEBUG_ASSETS`. The installed verified US 1.2 ROM has no segments or
extracted scene assets for `test01`, `besitu`, `depth_test`, `syotes`, `syotes2`,
`sutaru`, `hairal_niwa2`, `sasatest`, or `testroom`. These nine debug maps are
recorded as unavailable source inputs; no substitute map is invented.

The previous 75 runtime scene IDs remain fixed: the original eleven entries,
then `LEGACY_GENERIC_ORDER` in `tools/build_scene_table.py`. Newly admitted
retail maps append after them. Existing filenames and legacy save IDs retain
their meaning; current generic save flags also retain original source SceneId.
Registration cache identity now includes the producer and preflight contents,
so changed budgets cannot reuse old exclusion decisions.

Whole source collision is retained. The former 2,321-polygon ceiling excluded
large dungeons; the largest retail scene, Inside Ganon's Castle, has 5,096.
The C loader allocates the exact decoded size for each scene, validates the new
mesh before publication, then releases the old allocation. Global heap and
actor pool capacities stay unchanged. Scene index storage is sized for the
measured retail demand; final target and peak-memory evidence belongs below.
This is still the temporary C collision world during mandatory Player migration.

Room texture density and optional subdivisions now obey existing room storage
limits while retaining source face coverage. Two discovery cases needed separate
fixes. `moribossroom_scene` was wrongly treated as a room because its prefix
contained the word `room`; discovery now matches the actual room-name prefix.
`hiral_demo` has no static faces: its only room display list immediately ends.
Its two authored collision triangles remain. An explicit KRM1 source-empty flag
admits only a 32-byte bank with all geometry counts zero. Runtime loading clears
the previous geometry counts and skips empty SGL submissions. The source's
cutscene skybox and actor visuals remain separate runtime/content requirements.

The completed retail preflight covers 101 scenes and 388 room rows: 359 mesh
banks, 28 image rooms and the existing streamed Field. No blocked rows remain.
Maximum generic bank counts are 2,047 vertices, 1,426 polygons, 1,426 tiles and
351,232 pixel bytes, inside the unchanged limits. Every source face ID from all
356 previously valid banks is retained; the other three banks are the two
Forest boss rooms and the authored empty stage. Bounded optional refinement and
the current texture/actor reserve policy suffice for this bake: the additional
indexed texture reduction guard is implemented and tested but needed zero
reductions here. Repeating normal `--retail-only --refresh-stale` reused all
results. Evidence: `build/retail-bake-workers/validation.json` and
`cache-proof.log`.

The collision index is 20 KiB; the measured worst full-retail requirement is
19,774 B. The largest decoded C mesh needs 194,520 B. During transactional
collision replacement both old and new allocations can coexist (389,040 B for
two largest meshes); the raw file uses reserved load scratch. This is an
allocation peak, not a claim of measured target free memory. The independent
Player/core collision migration remains necessary to retire duplicate worlds.

Final generated metadata is 56,444 B, with 101 entries and 438 portals. Every
portal matches the room manifest and an independent source transition-actor
decode, including setup layers. It occupies the existing heap rather than a
main-program static array. Including up to 102,664 B of cached area-music
headers, the conservative collision-stage inventory gives 2,225,400 B for
Field-to-Castle replacement against 2,626,560 B of heap zones. Field plus an
era/Link-bank swap gives 2,507,944 B. These include room tables, index, metadata,
music-level data/staging, Link/gear/tools, all currently loadable core meshes,
dynamic copies and applicable sprite archives. They describe those allocation
stages, not measured runtime free space; small SDK/UI costs and fragmentation
still require target telemetry.
New music PCM is loaded into sound RAM through the existing 8 KiB staging,
not retained as a whole additional heap file. No heap zones were resized.

The full lifetime review found a real overlap: seven old Ranch SPR2 archives
(394,996 allocated bytes) survived while Gohma's 1,487,680 B native asset set
loaded. A lower bound with Ranch music exceeded total heap capacity by 94,008 B;
the title/Level Select path still exceeded it by 23,208 B. Old core resources
now unload immediately after successful collision admission, before new room
and native actor loading. Source destructors run before archive, tool, dynamic
copy, mesh and code-pack release. Frontend reset first detaches the old save
mirror. Dynamic registrations are removed before triangle storage is freed;
retry/repeated teardown is safe. Idle music trimming frees only non-current
area tables; all fading/swapping states retain both slots. With this cleanup,
the conservative native Gohma load is 2,497,236 B before small SDK/UI costs
(known START.RGB and one file buffer add 4,420 B). Same-frame music servicing
then replaces the old score before the next core/tool preload. The busy-music
case, fragmentation and real free/largest-block measurements remain runtime
checks. No percentage-based tool omission was counted as a memory saving.

Verification implemented:

- `tests/test_scene_decoder.py`: seven host checks pass, including real source
  room data, retail/debug discovery, restricted empty-stage conversion, malformed
  empty banks, a normal/empty/normal room cycle through the compiled production
  loader, and an empty draw through the compiled production submit function.
- `tests/test_all_map_registration.py`: final-build checks require all 101 retail
  registrations, stable first 75 IDs, every source room's staged files, labels and
  source enums, exact bank bounds, complete collision decoding, collision index
  admission, and bounded OOC/object storage. Partial builds fail these checks;
  missing maps are never reported as skips.
- Four production scene-lifetime tests check destructor/resource/pack ordering,
  frontend save detachment, dynamic unregister before free, repeated cleanup,
  collision failure and new-room load ordering. The music trim test covers
  both current slots, static music, every busy phase and repeated cleanup.

All 101 default map entries have an authored room-0 spawn or the existing menu
portal placement fallback. Forest Temple room 9 lacks a direct menu placement;
its source room/warp actors still need implementation. Portal placement does
not prove source gate traversal. The route audit now reports 101 registered
retail maps, zero missing retail registrations/extraction errors, and nine
unavailable debug inputs separately. Its 97 structurally reachable scenes,
102 blocked exit edges and 32 unsupported transition actors are not gameplay
acceptance; alternate source headers and script/warp paths remain unfinished.

The usual Clean image was rebuilt with the complete assets, then rebuilt once
more for the teardown/cache lifetime correction. Logs:
`build/all-maps-clean.log`, `build/all-maps-final.log`. Final main .bss ends at
`0x06083110`, 3,824 B below the unchanged SGL boundary. Resident core remains
399,844 B text + 46,512 B data + 62,204 B BSS = 508,560 B. All 101 OOC payloads
validate; largest OOC is 109,472 B and its aligned OOC/OOB set is 109,688 B in
the unchanged 262,144 B carve.

Final verification: 93 map/room/route/budget/lifetime checks and 91 shared
groundwork regressions pass (184 total, no skips). Both ELF math audits pass:
1,388 allowed hardware multiplies in the core and 601 in main, zero forbidden
sites reported. The 151,898,112 B ISO matches all 1,457 staged files byte for
byte, leaving 79 directory slots under the unchanged 1,536 limit. All seven
SPR2 libraries remain staged; the actor-pack test fixture remains off-disc.
Evidence is in `build/all-maps/{map-tests.log,regression-audit.log,iso-audit.json,
core-wide.log,game-wide.log,world-route-audit.log}`. Final program SHA-256:
`909ca76bcf5914df40684f7824bb16bca47d17371d54cb439297f4470f39c945`;
core SHA-256:
`c064546f350f7708f26ae936993d0429a44c6c9fefe9b63d66ba88e34c188a66`.

Host and target checks do not establish
runtime acceptance. Every-map entry, room transitions, collision, camera,
visuals and performance still need runtime/human verification. Map admission
does not establish complete enemy, boss, hazard, puzzle or story implementation.
The existing 85% legacy-tool admission limit can still hide sheets in adult
Gohma despite actual available bytes; this is logged separately, not marked
fixed or used to claim memory fit. No emulator launched and no commit made.
