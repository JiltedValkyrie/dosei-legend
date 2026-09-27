# Astra review: M1a - 2026-09-25

Original review: changes requested before M1b (superseded by re-review below). Human reports Clean runtime test had no
issues; recorded as human evidence, not an Astra emulator run. No implementation
files changed or committed in this review.

## P1: registration resets every live platform's motion history

`shared/lib/collision/kokiri_collision.c:1068`: bg_dyna_register calls
bg_dyna_step(), which copies current -> previous for ALL slots. Registering any
new mesh after an existing platform moves erases that platform's pending rider
motion. The contract explicitly puts bg_dyna_step once before actors move, so
registration must not introduce another global snapshot mid-step.

Reproduced against the real C library and PUSHBLK.COL:
register A (POS), step, set A to (30,0,0), register B, carry A rider (0,100,0).
Actual: false, rider x=0. Expected: rider x=30, same as without registering B.

Initialize only the newly registered slot's previous transform. Add a two-slot
regression with registration between movement and carry; cover slot reuse too.

## P1: rider position and facing flags do not match source

`shared/lib/collision/kokiri_collision.c:1133-1156`: bg_dyna_carry treats
ROT_Y as permission to rotate the rider's position, and always changes position
once either motion path is active. Source `src/code/z_bg_collect.c` separates
these: POS applies previous-inverse/current transform to the rider's position
(including platform rotation and scale); ROT_Y changes rider facing independently.

Reproduced with a block rotating 0 -> 0x4000 at origin and rider (10,0,0):
- POS only: actual false/(10,0,0), expected position (0,0,-10), yaw unchanged.
- ROT_Y only: actual position (0,0,-10), expected position (10,0,0), yaw +0x4000.
Both flags together passed the existing test and concealed this mismatch.

Separate position and yaw flags, preserve previous scale for the position
transform, and test POS-only, ROT_Y-only, both, neither, translation+rotation and
scale change. Disabled/removed slots must not carry a rider. These semantics are
needed by the moving-world contract before future traversal depends on it.

## P2: LINKANIM validation is not bound to the executable

`game/src/link_anim.c:77-96` checks shape and compares computed checksum to the
checksum stored in the same file. `game/tools/build_link_model.py:693-710` emits
no expected content identity into the generated ELF header. A valid older file
with the same total frame/limb counts passes even if frame contents or clip
boundaries differ from this executable. The boot claim "does not match this
build" and handoff claim "refuses stale file" are therefore too strong.

Confirmed from the loader predicates: modify a root value in a copy of the actual
57,700-byte file and recompute its header sum; magic/dimensions/length/checksum
all still pass. This is a stale-but-valid asset scenario, not disk corruption.
The altered copy was only in memory; shipped assets were not modified.

Emit an expected content digest/build signature with the compiled clip metadata
and compare it at load. Prefer a digest that covers frame order and clip layout,
not only an additive sum (reordering samples preserves the sum). Add loader tests
for valid current asset, truncated/corrupt asset, and valid same-shape stale asset.
Current byte-equivalence tests are useful but do not exercise stale rejection.

## Other reviewed points and follow-ups

- Fixed cart carve arithmetic is consistent: actor 0x0000..0x1fff, dyna
  0x2000..0x67ff, within new 0x8000 reservation. Frame file exceeds the 51,200-byte
  work arena and therefore cannot fit that allocator zone at its current size.
  Preserve explicit cart residency if future animation payloads shrink.
- Keep the acknowledged wall line-hit/flag-27 precedence gap in the contract
  ledger; correct it before hazard/wall consumers rely on source-equivalent hit
  identity. Current smoke tests do not cover that tie-break.
- Legacy ignore-flag behavior is explicitly preserved. M1b must deliberately
  select BG_IGNORE_ENTITY and test affected polygons; not a silent global switch.
- Collision decode into live storage is nontransactional on malformed input, as
  disclosed. Track safe failure/staging before claiming recoverable scene loads.
  Camera vector range validation should also avoid first+count unsigned wrap.
- Representative push-block mesh tests are useful foundation evidence. No live
  actor registers yet: do not call this a runtime-tested moving-platform actor.
  Bring a bounded representative actor/check forward or keep that M1 requirement
  explicitly pending for the named push/pull checkpoint.
- Timing document is a baseline for the inspected Actor_UpdatePos path, not a
  universal guarantee for every player action/animation timer. Audit each source
  handler before conversion; keep manual Y-jump apex as the human requirement.
- Existing locomotion timing text checks need updating for the previously approved
  analog integration. They are not new M1a collision regressions.

## Verification

Reran separately: bgcheck 19/19, link_animation 26/26, collision_gravity 9/9,
collision_index 3/3, player_controls 52/52: 109 passing tests. Ran extra in-memory
C-library reproductions for the two dyna findings above. Existing clean map
verified: .bss ends 0x06077e60, gap 49,568 bytes. No rebuild during review; Claude
reports clean build and disassembly check. Human reports runtime smoke test good.
No Astra Kronos run and no claim of full M1 traversal acceptance.

Claude: fix the three findings and add their regressions, then return M1a for
re-review. M1b remains pending that review. No commit requested or made.

## Re-review - 2026-09-26: approved for M1b

All three requested fixes accepted. Registration snapshots only the new slot;
carry applies POS and ROT_Y independently with previous uniform scale retained;
LINKANIM validates an order-sensitive clip-layout/body digest against an ELF
constant. Camera vector range validation also avoids unsigned addition wrap.
Inspected regressions cover the previous repros, slot reuse, isolated flags, scale,
disabled/removed slots, real loader corruption and valid same-shape stale/reordered
files. No new severe blocker found in this bounded re-review.

Reran: bgcheck 27/27, link_animation 30/30, player_controls 52/52 (109 total).
Existing clean map checked: .bss 0x06077f60, 49,312-byte gap. No rebuild or emulator
run by Astra; Claude reports clean rebuild/disassembly. Human smoke test was on
the previous M1a image, not newly claimed for this revision.

M1b may begin. This approves M1a foundations, not completion of all M1 traversal.
Remaining wall precedence, malformed-load recovery and old timing-test text checks
are nonblocking follow-ups in BUG_FEATURE_LOG. M1b owns explicit ignore-mask/timing
integration; M1h still owes the live representative dynamic actor. No commit made.
