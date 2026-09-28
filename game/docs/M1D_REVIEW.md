# Astra review: M1d - 2026-09-26

Code review approved; M1e may begin. No severe current-route blocker found in this
bounded review. Runtime acceptance remains pending; no code edits or commit.

## Reviewed

Inspected walk-off wall/water restrictions, descending grab eligibility, hang
placement, controls and root transfer on pull-up/let-go. Compared hang control and
pull-up sequencing with local OoT Player_Action_8084BBE4 / Player_Action_8084BDFC.
The source gives pushed-stick pull-up priority over held-A release after the grab
frame. The supported code follows that ordering. Vine/ladder starts and feet-floor
auto-drop remain disclosed limitations, not completed source parity.

BUG-011's integration fix is accepted: demo now passes zero roll input speed when
player_input_motion finds no movement; a digital pad at rest no longer supplies
its base speed to climb interruption. BUG-010's mid-air-grab implementation and
host sequence checks are accepted. Keep both entries open for their requested
Kronos checks rather than claiming visual/gameplay verification from host results.

One additional nonblocking finding logged BUG-012: retained 250-jump air speed is
assigned at preparation but cleared by grounded-step cleanup before frame-8 launch.
With centered input the speed-dependent grab may fail. Holding direction supplies
speed, so this does not stop M1e under the severity-first rule. Add an integration
regression around actual launch ordering during the next air/grab edit.

## Verification

Reran player_bg 37/37, player_controls 53/53, player_air 13/13,
link_animation 31/31 and collision_gravity 9/9: 143 passing tests.
Existing clean map verified: .bss 0x0607a080, 40,832-byte gap.
No rebuild, full-suite rerun, disassembly audit or Kronos run by Astra this review;
Claude reports clean build and integer-only changed units. Collision sequence
harnesses are useful but mirror demo integration rather than executing demo_update.

## Runtime and deferred obligations

Check boot with 103,752-byte LINKANIM, westward B walk-off at (314,3,-198), wait
for grab, pushed-stick pull-up and centered-stick held-A let-go. Check 250 jump at
(-462,0,-682), yaw 0x727D, with held direction and with released direction separately.
Observe wall clearance, root continuity/180-degree turn and let-go landing, not just
state transitions. Recheck released digital climb interruption for BUG-011.

Porch walk-off expectation now depends on hang eligibility; the previous M1b plain
fall expectation is superseded. M1b/M1c runtime jump/opening checks remain pending.
BUG-005/007/009 continue to track approximations, missing audio and drawn-scale
consequences. Hang camera remains the later named M1 camera task. M1e owns the
vine/ladder starts; full M1 completion is not implied by this checkpoint approval.
