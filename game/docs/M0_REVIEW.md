# Astra M0 review — 2026-09-25

## Re-review approved - 2026-09-25

Both findings resolved. Capsule interval clipping passes vertical/sloped repros,
reversed slope, flat segment and height/range misses. Unsigned attention sum
fits uint32 after the range box; each signed square fits int32. Pool comment
corrected. No new blocking findings. Generous capsule ends remain a documented
approximation, not exact rounded-cap or full OoT collision parity.

Independently reran actor_sys 20/20 and cutscene_skip 9/9. Existing map gaps
verified: normal 1840 / hires 1744 / clean 4624 bytes. No rebuild or Kronos run
this review; previous runtime checks remain open.

PAL note corrected: demo_vblank normalizes ticks via phase += 60 and subtracts
refresh (50/60); skip_input receives 60 ticks/sec at either refresh. Both give
120 ticks in two seconds. No timing fix needed; not a PAL emulator test.
Music fade chaining is nonblocking. Measure actual heap use before further
arena cuts; the earlier estimate is not a complete allocation inventory.

M0 code review approved. Claude may start M1 with the world-collision contract.
Keep runtime checks visible and work uncommitted. Review M1 before next milestone.
Historical first review follows.

Original verdict: changes requested. Keep M1 waiting. Reviewed uncommitted `dev` diff;
no gameplay code changed by this review.

## Findings

1. **P2 — Capsule overlap misses vertical and sloped contacts**
   (`game/src/collide.c:105-116`). XZ projection selects one segment point,
   then rejects on that point's height. Vertical segments always use endpoint A.
   Reproduced through the existing compiled actor_sys_host.c adapter:
   - Capsule `(0,0,0)` to `(0,100,0)`, radius 5; cylinder feet `(0,40,0)`,
     radius 10, height 20: `co_overlap(0,1)` returns -1 (no contact).
   - Capsule `(0,0,0)` to `(100,100,0)`, radius 5; cylinder feet `(0,40,0)`,
     radius 50, height 20: also -1, although `(40,40,0)` lies in both.
   Sword sweeps can therefore miss enemies. Account for the whole segment and
   cylinder height interval; cover both cases before gameplay use.

2. **P2 — Attention distance overflows despite its range guard**
   (`game/src/actor_sys.c:193-207`). Clamping range to 46340 protects each
   square, but not their sum. Reproduced: targetable NPC at XZ `(40000,40000)`,
   search from `(0,0)` with range 46340 and NPC mask returns slot 0 instead of
   no target. True distance is about 56569; signed overflow wins the nearest
   comparison. Use safe squared-distance arithmetic and cover this boundary.

## Risk checks

- Cart: SDK registers only bank 1 for a 4 MB cart. Bank 2's allocator zone
  ends at `0x227FC000`, where the fixed 16 KB carve begins; actor reservation
  uses its first 8 KB. Bounds and initialization order look sound. No overlap
  found. Minor: actor_sys.h still incorrectly says storage uses jo_malloc.
- Save: header-before-size correctly identifies a 220-byte v1 save without
  reading the v2 checksum. Backup reader passes actual stored length.
- SFX: deferred area selection during opening and reload after core restore
  look correct on inspection. Core ends at 518286; forest uses 3310 bytes,
  leaving 2692. Audio host tests bypass CD upload, so actual bank restoration
  still needs runtime verification.
- Arena: allocator can spill into cart zones; 52 KB is not the total allocation
  limit. Existing normal map core.o BSS is 0xD064, consistent with the reduced
  arena. Three build results remain implementer's evidence; not rebuilt here.
  Runtime heap use not measured by this review.

## Verification and decisions

- Independently reran 145 passing tests: actor_sys, asset_names, save_file,
  save_state, action_audio, character_textures, link_geometry_precision,
  gameplay. Separate Python processes.
- Reproduced equipment_draw, forest_partition and opening_audio harness
  compile failures. Missing stubs/types are outside this diff's changed
  function bodies. Whole-suite crash not investigated.
- Kronos not launched; preserve no-focus directive. Title/new file, outdoor
  grass sound, flat hair and old-save UI still need runtime checks.
- Controls already resolved by Sept 22 handoff's explicit superseding remap:
  **L + D-pad looks; Z targets/recenters**. CLAUDE.md's older line is stale.
- Meadow: recommend ending at its entrance with an explicit demo boundary,
  preserving the source's child access facts. Adding meadow expands approved
  scene scope; human choice remains open. Do not invent a Mido gate.

Claude: fix both reproduced bugs, add focused regressions, return diff for
review before M1. No commit requested.
