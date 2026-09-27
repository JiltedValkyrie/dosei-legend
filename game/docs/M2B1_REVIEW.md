# M2b.1 route verification - Astra, 2026-09-26

Human reports "Human test good" on 2026-09-26 in response to the route
check: M2b.1 starter route accepted. This is human runtime evidence, not
an automated Kronos pass. Boulder and other logged follow-ups remain open.
No implementation change or commit made during this verification.

## Verified

- Re-ran gameplay 75/75, actor_sys 38/38 and grass_floor 1/1: 114 pass.
- Independently checked the existing Clean map: BSS ends at 0x06082a90,
  leaving 5,488 bytes below SGL's work area. No rebuild performed.
- Reviewed the chest, shop, Mido and contact integration paths. The host
  route test supplies coordinates directly; it cannot establish that the
  player can physically reach every interaction through world collision.

## Runtime limit

Launched an isolated copy of Kronos against game-clean.cue with a separate
backup-memory path under game/build/m2b1-review. The emulator responded,
but background window captures returned a blank render area, including
after showing the window behind other windows without taking focus.
This does not establish either a game boot failure or a successful boot.
Closed the isolated process. Existing player backup memory was untouched.
No walking, purchase, gate or save/reload runtime pass is claimed.

## Route checklist accepted by human

1. Fresh file: obtain rupees without the sword, then crawl through the maze.
2. Open the sword chest once; equip the owned sword on pause.
3. Shop: refusal at 39 rupees, cancel without charge, purchase at 40.
4. Equip shield; Mido refuses with only one equipped and moves with both.
5. Save/reload: gear and chest state persist, shop cannot charge again for
   an owned shield, and Mido stays aside.

BUG-033 remains the priority memory task before another large addition;
measure heap use rather than shrinking the arena. BUG-032's maze boulder
remains required before final M2. Existing placeholder and presentation
issues remain deferred as logged. The reported full-suite failures have
not been independently compared against HEAD in this verification.
