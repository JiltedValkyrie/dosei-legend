# Astra review: M1c - 2026-09-26

Code review approved; M1d may begin. No severe current gameplay blocker identified
in this bounded review. Runtime acceptance remains pending. No code edits, rebuild
or commit by Astra.

## Scope reviewed

Inspected player_bg probe/action, demo wiring, collision horizontal/vertical order,
climb state timing/offsets, child-root import policy and source handler references.
Compared the root adjustment with Player_OverrideLimbDrawGameplayCommon and ledge
choices with Player_ActionHandler_12 in the local OoT source. Child root adjustment
is axis/flag-dependent in source; the current clip allowlist is an implementation
choice for the imported gameplay/opening set, not a blanket rule for future clips.

Accepted human scope: low-step correction belongs here; child root adjustment is a
prerequisite; 47+ starts the source jump but no mid-air grab or snap-to-top. M1d owns
BUG-010. Full wall/hang/swim interaction is not claimed complete by this approval.

The collision path tests wall, ceiling and floor rather than blindly snapping all
small heights. Tests cover threshold/headroom rejects and concrete forest ledges.
Vertical movement no longer uses the old wall sphere to pin Link at contact; the
remaining custom bridge/head check is documented. Visual root/offset continuity
and the opening's changed draw height still require observation.

## Verification

Reran test_player_bg 28/28, test_player_air 13/13, test_link_animation 31/31,
test_collision_gravity 9/9, test_player_controls 52/52, test_bgcheck 27/27:
160 passing tests. Existing clean map checked: .bss 0x06079450, 43,952-byte gap.
Did not rerun the full 628-test suite; historical snippet failures remain logged.
Claude reports clean rebuild and no float helpers; no new target disassembly or
Kronos run performed in this review.

## Nonblocking finding

BUG-011 added: released digital pad still supplies base walk/run speed to the
animation input, so climb_step's speed-only last-four-frame interrupt can fire
without movement. Centered analog differs. Fix during next climb/input integration;
no evidence of a blocked playable route. Existing BUG-004..010 remain recorded,
including model scale/headroom, source subset gaps, sound and pending grab.

## Pending runtime acceptance

Human should check low steps, hop (561,-23,-212) toward +Z, step-up near
(1219,-60,59) toward +X and (172,28,-483), plus 47+ jump returning to the wall foot.
Check draw continuity, climb voice, opening bed/stand heights, M1b porch auto-jump
and manual Y-jump/faster fall. These results are not inferred from host tests.
M1d can proceed while checks stay pending; escalate actual route breaks immediately.
