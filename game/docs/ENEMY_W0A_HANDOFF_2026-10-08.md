# Enemy W0a handoff — 2026-10-08

Owner: Astra, branch `oot-core`. The received plan and its two inbound links
were already human edits. Five review questions are resolved in
[ENEMY_DESIGN_REVIEW.md](ENEMY_DESIGN_REVIEW.md); the current rollout contract
is [ENEMY_ROLLOUT_PLAN.md](ENEMY_ROLLOUT_PLAN.md).

## Delivered scope

- A: source/profile identity correction, regenerated coverage and enemy roster,
  all scene/layer candidates and explicit unknown spawn/memory evidence.
- B: OAP1 fixed-address two-pass linker, exact ELF/BIN/CRC binding, ctor/BSS
  handling, validated internal overlay registration, full actor/effect teardown
  before object/code overwrite, checked scene-carve loading and stopped error
  state. API23 connects the matching C host and resident core. An isolated
  constructor fixture imports zero actors/effects and stays off disc.
- D/E: all 34 existing generic NPC clips become seven object+skeleton SPR2
  libraries with linked animation keys. Both SkelAnime init paths keep clocks
  without joint/morph allocation or pose evaluation. Scene-object union preload
  runs before actors; missing libraries fail admission. Sixteen shared cel
  slots are pinned for each submission frame; 16 exported views remain a cap.
- F: C combat state/source melee flags reach the proxy; source body/shield hits
  enter one C-owned reaction/health queue. Knockback overrides precede shield
  blocking; large knockback can push without damage during invincibility.
  Tool hit identity is fresh per spawn and stable across view ordering.
  Source random-drop rows 13/14 are no longer clamped to row zero. The semantic
  shield matrix supports the source projectile reflection direction.
- G: bounded, pointer-free EffectSs snapshots, without new effect imports.
- H: generated existing SFX dispatcher plus offline ESF1 scene libraries and
  room copy maps with hard sound/cart limits and named unsupported sounds.

No actor/effect source import, scene registration, emulator run or commit.
This is shared infrastructure; systems C-I and the full enemy rollout are
not complete. The legacy C enemies and C-owned Player remain in production.

## Verification

Final combined WSL host run: **91 tests pass, zero skips** (83 focused checks
plus eight actual gameplay regressions). Suites cover coverage/roster/audio,
pack validation/ctor registration/release, sprite archive identity and malformed
input, preload/missing-library handling, cel pinning, clock-only animation,
combat/health ownership, tool identity, effect views, item drops and actual
dynamic collision conversion. Existing audio events pass through their real C
dispatcher. The real source Octorok reflection function and matrix conversion
send shots outward at six tested facing angles for child/adult shield states.
The gameplay cases cover ordinary/guarded damage, intangibility, fall/roll,
hurt clock/reset and exactly-once core horizontal impulse including zero speed.

Matching WSL `./build.sh --clean --quick OOT_CORE=1` passes after full asset
generation. Usual `build/game-clean.cue/.iso` rebuilt; ISO is 72,622,080 B.
Main `.bss` ends at **0x06083ee0**, **288 B below SGL**. Resident core target
size is text 399,844 B + data 46,512 B + BSS 62,204 B = **508,560 B**, within
the existing 589,824 B carve. This is not combined real Player fit evidence.

The fresh SH-2 test OAP binds to that exact core (CRC 4081439942); 124 B file
plus 4 B BSS/alignment, one constructor, zero actors/effects. Pack math audit
passes. Core and main disassembly audits report 1,388 / 608 allowed hardware
multiply sites and **zero failing sites outside libgcc**. Existing libgcc
sections remain excluded by the audit; no broader cleanup claim is made.

All **892 ISO files match staging byte-for-byte**, including `0.BIN` matching
the final raw executable and `OOTCORE.BIN` matching the final core ELF output.
The seven SPR2 libraries are present; no OAP fixture is staged. Disc directory
fits its 1,536-entry limit. All **75 staged OOCs** pass structural checks;
largest is 51,252 B, with maxima 12 rooms, 15 layers, 12 objects and 89 room
entries. Source profile import count remains 26.

Local evidence: `build/enemy-w0a-final.log`, `build/enemy-w0a-verify.log`,
`build/enemy-w0a/{core-wide.log,game-wide.log,iso-audit.json}`,
`build/oot-core/ooc-structure-review.json` and `build/oot-core/pack-test/TEST.OAP`.
The isolated pack can be rebuilt through the BUILD.md W0a fixture command.
No runtime or human acceptance follows from these target/host results.

Full asset generation completed before the final code-only Clean rebuild.
The first target link exceeded high work RAM by 1,600 B and its guard removed
the unsafe image. Cold scene/SPR2 admission now runs in the cart core, while
the existing dynamic collision owner records share the already reserved 4 KiB
low-RAM draw carve. The SH-2 size assertion checks that carve. Heap sizes,
actor capacities, ZeldaArena/THA limits and SGL boundary remain unchanged.

Seven SPR2 files total 394,912 B; the Ranch scene union needs 394,919 B with
Jo read terminators, before allocator metadata/fragmentation. The 85% heap
guard remains active. Clip resolution is 32px with four sampled poses;
original clip identity and gameplay clock duration are retained.

Coverage resolves 429 profiles, with the same 26 source profiles imported.
The roster has 98 scoped actors, exactly 20 ACTORCAT_BOSS profiles and 65
conservative scene candidates / 1,089 room-layer rows. No scene is marked ready.
The original 20 missing enemy registrations remain in scope; the additional
Hyrule Castle candidate is inventory/follow-up, not an added W0a registration.

River's conservative audio set needs 208,892 B against the existing 79,462 B
area limit, including retained non-enemy sounds. The generator rejects it;
no sample is silently dropped and no enemy bank is enabled at runtime.

## Runtime acceptance and next work

Human checks existing NPC scene entry/room changes, Ranch population and
animation, MISS 0, heap/FPS, scene reload, existing sword/shield/tool contacts
and drops. A host/target pass does not establish these outcomes. Error/retry
paths are host-tested; hardware CD failure recovery is not accepted yet.

W0b imports remain gated on the earlier Wave 0 Fx32 exit requirements.
Continue mandatory real Player migration in parallel. Its old retention and
five-region free-space figures predate W0a; recompute combined retention,
adapters and peak allocations from the current ELF/BIN before accepting fit.

Importing waves still need per-actor semantic anchors and Draw-side-effect
audits, BodyBreak/child-counter timing, tint/alpha/scale/Lens rendering,
elemental reactions and vertical knockback, seeds/nuts, targeting/Navi/BGM,
effect imports/visual recipes, enemy audio loading and measured live actor,
THA/arena, sound, sprite and room budgets. Grab/capture/gear actors wait for
real Player cutover. All 20 missing scene registrations remain future work.
