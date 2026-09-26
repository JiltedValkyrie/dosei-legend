# Demo plan source review - 2026-09-25

Claude: apply these corrections while doing M0/M1. Review of DEMO_PLAN.md,
not approval of your in-progress implementation. Your existing diff is untouched.

## P1: save layout changes belong in M0, not M8

M0 expands SAVE_SCENE_COUNT; M8 postpones save versioning. These must happen
together. `save_file.c:84` serializes every scene, while `save_file.h:39-42`
fixes version 1 and a 210-byte payload. Each added scene adds 16 bytes.
Update payload size, version, backup buffers and serialization checks in the
same change; reject old saves cleanly. Preserve existing compact scene IDs.
Check round-trip flags on the highest new scene and old-version rejection.

## P1: child Lost Woods has no Mido meadow gate

The source-facts table and M6 incorrectly apply the EVENTCHKINF_0A Mido gate
to this child demo. In the US 1.2 extraction, the only ACTOR_EN_MD in spot10
is room 3's alternate actor list at 030001A8. Its header at 03000150 is
alternate-list entry 1, i.e. scene layer 2 (adult day); child day uses the
base header. `z_play.c:413-419` selects the age/time layer. Adult night's NULL
header follows source fallback rules; never merge alternate actor lists.

`EnMd_ShouldSpawn` accepting SCENE_LOST_WOODS does not create an actor absent
from the chosen room actor list. The meadow cannot be called source-blocked
for child Link on this evidence. Correct M6 and the scene table. Keep the
meadow implementation out of scope for now, but explicitly record the scope
conflict: either an acknowledged demo boundary or added reachable content
needs a human scope decision. Do not invent a child Mido gate.

## P1: M1 needs a world-collision contract before traversal

The proposed AT/AC/OC combat skeleton does not provide moving world collision.
`Obj_Oshihiki/z_obj_oshihiki.c:104-108` registers a DynaPoly collision mesh;
pushable blocks, moving platforms and removable webs need geometry ownership,
transforms, contact identity and safe removal. Include this M1 prerequisite,
with a small representative actor; full dungeon actor delivery can remain M5.

Current `kokiri_collision.h` queries return floor height or move a position,
not the hit polygon/bgId needed by traversal. Extend the result contract to
identify wall/floor/ceiling contacts and owner, including clearance probes.
`collision_surfaces()` currently emits exit/floor/wall/material only despite
its richer docstring. Preserve required surface bits, camera references and
polygon flags through exporter -> asset -> loader -> runtime queries.

Water is separate: `include/bgcheck.h` CollisionHeader has numWaterBoxes and
waterBoxes; WaterBox carries bounds, surface height and room/camera properties.
Floor types alone cannot implement M1 swimming/diving. Export and query water
boxes before claiming that acceptance case works.

## P2: heights and wall flags are not a complete traversal algorithm

Use symbols, not the plan's line numbers, as implementation references.
`z_bgcheck.c:69-79` maps wall TYPES to flag masks: types 2/3/4 differ from
WALL_FLAG_1/2/3. `func_8083EC18` checks flag 2 too, omitted in the summary.
Port that mapping; do not compare raw wall type against flag numbers.

The 27/39/47 child thresholds select ledge categories, not unconditional
permission to climb. The ledge probe around `z_player.c:11235` also rejects
height <18, blocked ceilings, obstructed ledges, unsuitable normals and wall
flags; action handlers impose more state and timing checks. Preserve these.
Test threshold boundaries plus low ceiling, blocked top, crawl reversal and
standing rejection using actual scene geometry.

Keep physics feet separate from this port's floor+90 camera anchor. Establish
20 Hz source versus 30 Hz runtime timing for traversal, timers and root motion;
do not paste frame constants unchanged or double-apply animation travel.
Keep the user's Y jump and Saturn control mapping.

## P2: make M1 dependencies and acceptance honest

M1 asks for fall damage/drown respawn before M2 damage/death, lifting actors
before M3 props, and complete ydan traversal before M5 imports ydan. Bring
only the required health/respawn hooks, representative props and geometry
fixtures forward, or mark those checks pending until their dependencies land.
Do not mark all M1 complete from animation playback or a forest-only test.
New liftable actors still require their source drop behavior in the same task.

## Evidence and limits

- Local decomp: `D:/Workspace-Claude/game-decomps/n64/oot`.
- Hashed the actual compressed US 1.2 ROM: MD5
  `57a9719ad547c516342e1a15d5c28c3d`, matching its checksum manifest and the
  Link importer's required ROM. ROM revision is suitable for this task.
- Checked local extracted spot10 headers/actor lists, player and bgcheck source,
  block collision registration, current collision exporter/API and save packing.
- Review is source/document inspection. No game build or Kronos validation;
  no claim that all extracted assets or all later milestone facts are verified.
- M0/M1 owner/status table should reflect the human's current assignment:
  Claude doing both. Keep checkpoint ownership and verification explicit.
