> Historical isolated preflight. Superseded for current implementation/build
> status by DEMO_PLAN.md and M7_HYRULE_FIELD_PLAN.md. The measurements below
> remain useful; their ?not implemented / no rebuild? statements describe that
> earlier checkpoint, not the current integrated Clean image.

# M7a Field and story preflight - 2026-09-30

Owner: Codex/Astra. Human authorized M7. This is source/offline evidence,
not a playable Field or runtime acceptance. Usual Clean image remains the
previous feedback/fanfare build; this task does not replace that image.

## Reproduce

```
python game/tools/build_field_preflight.py --base-tile-limit 32 --source-tessellation --with-owl
python game/tools/build_field_story_preflight.py --audio
```

Writes only `game/build/field-preflight/`; never registers or stages a scene.
Original default hybrid bake failed VRAM by 47,904 bytes. The new explicit
Field policy caps shared base tiles at 32 pixels and skips extra forest floor
refinement; it retains source geometry, UV subdivision and collision. Existing
scene conversion defaults remain unchanged. This is an offline policy, not a
claimed fix for the renderer's foreground warp.

| Reservation | Polygons | Vertices | Texture/CLUT bytes |
|---|---:|---:|---:|
| Field room | 1,403 | 1,681 | 346,784 |
| Link + larger owl draw / both owl resident texture banks | 1,084 | 624 | 44,320 |
| Total geometry / bank textures | 2,487 | 2,305 | 391,104 |

With other resident VDP1 costs, 411,520 / 445,432 bytes; 33,912 bytes spare.
1,563 sprites / 2,400. This includes the 32 KiB reserve, not 33,912 bytes of
unassigned actor budget. Perch model: 240 vertices / 400 faces, 15,360 texture
bytes, 20 poses. Flight model: 301 / 520, 15,560 bytes, unfold 15 / takeoff 60 /
fly 15 / glide 2 poses. Source scale .025; original two skeletons and vertex
matrix ownership retained. Open eyes only; head tracking/blink remain actor work.
Both texture banks reserved resident, one skeleton drawn at a time. En_Owl has
no enemy drop table. Other props, worst views and runtime acceptance remain open.

Owl body lists use a large clamp rectangle over a small source image. The
importer now accepts explicit XML image dimensions to avoid reading past that
image. Existing actors do not opt into this binding. Unknown material still fails.

## Story and audio assets

Bridge source camera: 1,131 ticks, destination at tick 1,130 to Field spawn 3.
Field introduction: 331 ticks, source stop at tick 330 and title-card event.
Gameplay Field uses a distinct audit scene name so nightmare camera clearance
cannot distort its real camera. Camera export does not implement title cards.
Bridge Link cues 17/40/66/67 and Fairy Ocarina sequence binding remain explicitly
unmapped in the ledger, with source text, actor cues and destination preserved.

Owl sequence 90: 3,160 score frames, 319,248 PCM bytes, 75,840 level bytes,
361 triggers; loop frame 186. Fairy Ocarina sequence 61: 544 frames, 319,274
PCM bytes, 13,056 level bytes, 42 triggers. Both fit their SCSP sample region.
The audio interpreter accepts the owl's neutral bend reset; non-neutral bend
still fails until pitch automation is implemented. No silent opcode omission.
These banks are isolated, not linked/staged/played. Existing synthesis limitations
remain recorded in each generated manifest.

Field sequence 2 is a logic controller. Real arrival uses sequence 3, exploration
uses phrases 4-14, and stillness uses 20-23. No claim of playable Field music until
phrase selection, continuity and conversation/area restoration are implemented.

## Source graph

One room, 1,579 collision triangles, 73 placed actors, 15 exit-list entries.
Presence in source does not authorize all actors: child-day demo omits Field
enemies and day/night behavior. Some exit entries have no collision polygons;
their actor/script triggers need separate auditing. Field return is exit 4 ->
Lost Woods spawn 8; bridge departure enters Field spawn 3.

| Exit | Destination | Spawn | Collision polygons | Demo handling |
|---|---|---|---|---|
| 1 | SCENE_MARKET_ENTRANCE_DAY | 0 | 0 | Explicit boundary required |
| 2 | SCENE_KAKARIKO_VILLAGE | 0 | 3 | Explicit boundary required |
| 3 | SCENE_ZORAS_RIVER | 0 | 2 | Explicit boundary required |
| 4 | SCENE_LOST_WOODS | 8 | 3 | Return to Woods |
| 5 | SCENE_LAKE_HYLIA | 0 | 1 | Explicit boundary required |
| 6 | SCENE_GERUDO_VALLEY | 0 | 2 | Explicit boundary required |
| 7 | SCENE_LON_LON_RANCH | 0 | 4 | Explicit boundary required |
| 8 | SCENE_MARKET_ENTRANCE_DAY | 1 | 6 | Explicit boundary required |
| 9 | SCENE_LAKE_HYLIA | 0 | 1 | Explicit boundary required |
| 10 | SCENE_FAIRYS_FOUNTAIN | 0 | 0 | Explicit boundary required |
| 11 | SCENE_GROTTOS | 0 | 0 | Explicit boundary required |
| 12 | SCENE_LON_LON_RANCH | 1 | 0 | Explicit boundary required |
| 13 | SCENE_LON_LON_RANCH | 2 | 0 | Explicit boundary required |
| 14 | SCENE_LON_LON_RANCH | 3 | 0 | Explicit boundary required |
| 15 | SCENE_ZORAS_RIVER | 3 | 4 | Explicit boundary required |

## Owls

| Params | Position | Assignment |
|---|---|---|
| 004C | [4284, 182, 7877] | Required intro talk/repeat/flight |
| 00FF | [3276, 510, 971] | Audit source trigger; static talk or omission still undecided |
| 013F | [-6270, 30, 8579] | Audit source trigger; static talk or omission still undecided |
| 014B | [-4670, -500, 13739] | Audit source trigger; static talk or omission still undecided |

## Next implementation work

1. Recover high RAM / file-table capacity before runtime integration. Current
   Clean still has only 144 bytes before SGL and 379/384 disc entries. Keep
   heap51200, SGL3750/3200 and sprite2400 unchanged.
2. Wire source Tree aftermath and Saria farewell/item grant/destination, with
   save/skip/reload ownership. Boss blue warp already commits Emerald only after
   successful forest load; post-Emerald guard behavior has host coverage.
3. Register distinct gameplay Field and source intro A0; test natural arrival,
   repeat entry, return exit and every boundary. No debug grant substitute.
4. Implement owl talk/repeat/departure/camera and music restoration, Field phrase
   controller, remaining props and ocarina context/audio/VDP2 staff. Prove large
   coordinate collision/water traversal and worst-view submission on target.

## Verification

291 focused checks pass: field_preflight, progression_manifest/rooms,
boss_reward_assets, gohma and gameplay. New checks cover source skeleton/clip
identity, bounded owl image reads, exact story destination/stop, unmapped-cue
reporting, rejection of unsupported live title cards and non-neutral pitch bend.
The existing boss/guard tests cover Emerald gating; they do not prove the still
missing live bridge/Field route.

Logs: `game/build/field-owl-budget.log`, `field-story-preflight.log`.
Manifests: `game/build/field-preflight/field_preflight.json`,
`owl/owl_manifest.json`, `story/story_preflight.json`, `story/audio/*manifest.json`.
No runtime code changes, target rebuild or emulator run in this checkpoint.

Broader regression check also passes: hybrid, character textures, cutscenes,
opening and interior audio. Updated the stale opening-audio host harness for
existing camera/Navi sound state and independent music attenuation. No runtime
audio behavior changed by that fixture repair. Total focused checks: 291.
