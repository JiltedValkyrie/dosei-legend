# Astra review: M1b air rules - 2026-09-26

Result: code review approved; M1c may begin. No severe blocker found in this
bounded review. This is not runtime acceptance of the changed jump/fall feel or
completion of the whole M1 milestone. No implementation changes or commit made.

## Reviewed behavior

- Compared player_air departure/launch conditions with local OoT z_player.c
  func_8083AA10 and func_8083A4A8. Strict speed, angle and drop thresholds match
  the stated supported subset. Floor PROPERTY (not floor TYPE) supplies 6/7/8/9
  rules. Water jump and hang remain explicitly deferred.
- Inspected demo integration: previous grounded/floor state, commanded Q8 speed
  rather than rounded travel, roll-speed override, departure before gravity,
  auto-jump cue and floor-property lookup. The manual Y-jump velocity prevents
  auto-jump from launching a second time on the same departure.
- Fall-start height remains the ground departure height instead of being raised
  at the apex. This agrees with the reviewed source fallDistance basis.
- Inspected jump/run-jump/end animation selection, end-frame hold and transition
  to ordinary falling below departure. Source Player_Action_8084411C gives
  run_jump_end priority when the run-jump animation remains active on landing.
  Source also has wall/other action transitions; these are not claimed complete
  by M1b and must be integrated with the later wall/traversal handlers.
- Gravity/terminal constants follow the documented Actor_UpdatePos conversion.
  Measured the real collision/manual-jump functions on a flat host fixture:
  apex 51 world units, landing on step 25. Faster flight/fall is intentional;
  visual/controller feel remains unverified on this revision.

## Verification

Reran separately:
- test_player_air: 13/13
- test_collision_gravity: 9/9
- test_player_controls: 52/52
- test_link_animation: 30/30
- test_oot_follow: 29/29

Total: 133 passing tests. Existing clean map verified: .bss ends 0x060782d0,
48,432 bytes below SGL. No rebuild or Kronos run by Astra; Claude reports clean
build and no software-float helpers in changed objects. Previous human M1a smoke
is not evidence for this new gravity/auto-jump behavior.

The air tests exercise real rules/collision/animation but their departure harness
mirrors demo ordering, rather than compiling demo_update. Scene/pad/audio integration
therefore still needs the runtime check; synthetic edge tests do not prove the
actual house porch, voice or animated root motion looks correct.

## Remaining checks and ownership

Human/runtime check: run off house porch (auto jump + voice), B-walk off (fall),
manual Y jump (same height, quicker landing), and normal/run-jump landings. Keep
this check pending in the M1 handoff; escalate if it reveals a playable-route break.
It need not block independent M1c implementation under the severity-first rule.

M1c owns wall/ledge sensing and related action integration. M1d owns deep-drop hang;
M1k owns water-specific running jumps. BUG-001/002/003 remain the existing
nonblocking ledger, including obsolete locomotion timing source-string checks.
No new bug asserted solely from an untested future interaction. M1c returns for
review before its next checkpoint, following existing ownership/review rules.
