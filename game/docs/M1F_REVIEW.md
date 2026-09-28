# Astra review: M1f - 2026-09-26

Code review approved; M1g may proceed. Human reports the current crawl/camera
build works. No severe current-route blocker found in this bounded review.
No implementation edits or commit by Astra.

## Scope and findings

Reviewed centered A entry, forward/reverse exit selection, root-motion playback,
crawl collision sizing and restoration, standing wall contact, Enter prompt,
first-person camera selection and return to follow camera. Compared exit logic
with local OoT Player_TryLeavingCrawlspace and ceiling ordering with
Actor_UpdateBgCheckInfo. The shared grounded ceiling range now includes the
negative vertical displacement needed for the real tunnel.

BUG-016's tunnel-blocking fix is accepted. Its disclosed floor-ray/step-height
approximation remains a follow-up; do not claim exact source parity. No separate
low-roof location/result was supplied by the human, so retain that explicit check.
BUG-017's camera transitions, sway and audio gaps remain nonblocking.

Additional defensive camera follow-up under BUG-017: crawl_camera_begin accepts
any camera record with at least four points, without checking the crawlspace
setting or a nonzero line before marking the camera valid. A degenerate line
makes crawl_camera return while first-person mode still hides Link and suppresses
the follow camera. Current sword-maze data works; this is a potential future-data
issue, not a reproduced current-route failure.

## Verification

Independently reran player_crawl 5, player_bg 37, player_climb 12, bgcheck 27,
collision_gravity 9, player_controls 53 and link_animation 31: 174 tests passed.
The crawl tests use the real sword-maze collision. They do not execute the full
demo_update camera path.

Existing clean map verified: .bss ends 0x0607c6f0, 30,992-byte gap below SGL.
No rebuild, full-suite rerun, target disassembly audit or Kronos run by Astra.
Human runtime pass is separate evidence, including the latest camera update;
no individual unreported camera effects or additional roof locations are inferred.
