# Re-review - 2026-09-26

BUG-028 accepted: registered AT/AC/OC ownership is checked before resolution;
OC application rejects replaced owners. Regressions cover both sides and OC.
BUG-029 A/B/A fix accepted as a four-entry per-collider history. Eviction and
multiple hurtboxes remain P2 BUG-030 for live damage integration.

Re-ran actor_sys 38/38 and gameplay 60/60. Inspected Clean log: 13,344 B gap.
No new build or Kronos run. Timing comment corrected. Shared orchestration,
body/shield and OC/world constraints remain pending: M2b is not complete.
Claude may proceed to M2b.1 for early human testing. No commit made.

# M2b contact-core review — Astra, 2026-09-26

Grass checkpoint can continue to human testing. Actor-contact safety and
once-per-attack guarantees need the fixes below before live enemy integration.
No gameplay implementation edited or commit made during this review.

## Findings

1. **BUG-028: registration does not retain actor identity.** `live()` asks for
   the handle currently stored at `c->actor`, rather than the handle at
   registration. Register an enemy hurtbox, kill the enemy, spawn an NPC into
   the same slot, then run: one event hits the new NPC with its new handle.
   Reproduced with existing actor_sys_host functions: old handle 1, replacement
   handle 2, event victim 2. Old *completed* event handles are safe; outstanding
   registrations are not. Snapshot ownership when registering AT/AC/OC and
   validate that identity before reading actor position or resolving contacts.
   Test replacement of both attacker and victim, plus OC, before the run.

2. **BUG-029: last-hit memory does not enforce once per attack with multiple
   attackers.** On one overlapping AC, run attack 7/tag 1, then attack 7/tag 2,
   then attack 7/tag 1 again. Event counts are 1,1,1; the promised result is
   1,1,0. The second attacker overwrites the first attack's memory. Use bounded
   attack-owned victim tracking, or explicitly integrate source damage timers
   and revise the advertised contract. Test A/B/A with distinct actor handles
   as well as actorless tags. Current one-blade, permanently-cut grass path is
   protected by its cut bit and does not expose this defect.

3. **Timing claim needs correction during live-player wiring.** `cut_grass`
   says movement already ran, but `demo_update` calls `gameplay_step` before
   water/traversal/ordinary movement. `update_sword` calls `cut_grass` there.
   Current contacts therefore use the pre-movement position and resolve in
   that same step. This preserves the old grass path's order; it does not
   implement the claimed post-movement registration. Centralize begin/register/
   run when adding Link/enemies so grass's private `collide_begin` cannot erase
   their lists. Document the actual next-tick player-damage consumption point.

These are P2 integration follow-ups while the only live consumer is grass;
they become required fixes before the affected actor/contact consumers land.
No request to stop unrelated milestone work or revisit deferred push-block tests.

## Verification and limits

Re-ran actor_sys 35/35 and gameplay 60/60. Ran two additional repro scripts
against the real compiled fixture for findings 1 and 2; neither case is covered
by the current regression tests. Existing shield-order tests prove the helper
reports bounce in either order; they do not yet exercise a live player damage
consumer, as the handoff correctly discloses. OC world constraints remain pending.

No rebuild (review/docs only); no Kronos run. Human grass/pause/reset check still
needed. Pose-following sword sweep and full M2b acceptance remain open.
