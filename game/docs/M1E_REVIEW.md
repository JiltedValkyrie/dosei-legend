# Astra review: M1e - 2026-09-26

## Human runtime follow-up

Human reports tall-ledge jump/hang/A release works, house ladder ascent works,
vines behave as expected, and normal movement is good. BUG-012/013 now accepted
and closed on code review plus manual evidence. No automated demo_update test
claimed. Human subsequently confirmed pull-up works too. Porch slow walk hangs and
running jumps off; no ladder descent. BUG-015 stays open pending original-game
comparison. M1f may proceed. This supersedes corresponding pending notes below.

Code review approved for continued M1 work. No severe current-route blocker
found in this bounded review. Runtime acceptance remains pending. No code edits
or commit by Astra.

## BUG-012 second-fix review

The second fix is accepted by code inspection: launch is captured once in
`launched`, and grounded cleanup now requires `!launched`. The climbing branch
zeros intent speed during jump preparation, so the launch speed survives this
update. On the next step positive vertical velocity advances the jump before
grounded cleanup. Ordinary landing cleanup remains enabled.

Existing clean map rechecked: 34,944-byte gap. No rebuild or host test of
demo_update performed. Keep BUG-012 open for the centered-input jump/grab
Kronos check and remaining acceptance criteria. M1f may proceed.

## Original finding: BUG-012 (P2; superseded by second fix above)

The frame-8 launch now assigns retained speed 256, but the same demo update
still reaches `if (grounded || intent_speed) link_air_speed_q8 = 0` afterward.
`grounded` was computed before the animation update and launch, while Link was
standing; the launch does not change it. Consequently the new assignment is
cleared on the launch step too. The reported fix is incomplete. Holding direction
still supplies movement, so this remains nonblocking under the severity-first rule.
Cover the actual launch/cleanup ordering in an integration regression when fixing
it; animation and helper tests alone do not exercise this ordering.

## Reviewed

Compared ladder/vine start, centering, rung snapping and climbing/end sequencing
with local OoT `func_8083EC18`, `Player_Action_8084BF1C` and
`Player_Action_8084C5F8`. Inspected demo integration, root-delta playback,
vine pull-up/let-go transitions and the shared projected-triangle tolerance.
BUG-013's determinant-based tolerance and regression coverage are accepted for
code review; general walking/step/wall runtime acceptance remains required.
BUG-014's disclosed climbing subset stays deferred. BUG-015 remains unresolved:
host ladder ascent does not establish original-game porch descent behavior.

## Verification

Independently reran player_climb 12, player_bg 37, player_controls 53,
bgcheck 27, link_animation 31, player_air 13 and collision_gravity 9:
182 tests passed. These do not run the full demo update loop.

Verified the existing clean map: .bss ends at 0x0607b7a0, leaving 34,912 bytes
below the SGL work area. No rebuild, disassembly audit, full-suite run or Kronos
run by Astra. Claude's target-build and no-float reports remain separate evidence.

## Runtime follow-up

Check boot with the larger LINKANIM file; house ladder ascent and step-off;
porch descent approach; vine ascent, sideways motion, top pull-up and A release;
general forest walking, steps and walls. Observe root continuity and clear landing.
Keep BUG-012/013 and prior runtime-dependent entries open until their criteria
are met. Climb camera remains later M1 work, not delivered by this approval.
