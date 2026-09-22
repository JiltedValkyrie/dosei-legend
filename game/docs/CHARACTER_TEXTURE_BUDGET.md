# Character texture budget — 2026-09-22

Permanent user policy: halve both dimensions of non-face character tiles at
import time. Keep face detail at the previous import resolution, and preserve
existing flat-shaded bodies. See the engineering Bible for future importers.
Shared implementation: `game/tools/character_textures.py`. Source XML names,
head limbs and expression bindings identify facial materials; anonymous head
materials conservatively retain detail. Horses include their eyes and nose.
Props, scenery and UI do not use this reduction.

Logical 4x4 tiles require physical 8x4 storage on VDP1; repeat columns instead
of stretching the UV domain or cropping. Palettes still cost 32 bytes per tile.
This is quarter pixel resolution, not a promise of quarter total VRAM usage.

## Nightmare overlap

The renderer resets the actor texture bank when visibility changes. The old
bank was not simply accumulating textures forever: conservative visibility
retains both mounted groups together around frame 321. All seven actor/prop
banks left only 48 bytes spare with the previous assets.

| Bank | Previous bytes | New bytes |
|---|---:|---:|
| Ganondorf | 74,464 | 38,400 |
| Zelda | 79,680 | 33,056 |
| Impa | 63,776 | 32,128 |
| Zelda's horse | 71,040 | 30,976 |
| Ganondorf's horse | 72,480 | 29,408 |
| Bridge + chains | 2,880 | 2,880 |
| All banks | 364,320 | 166,848 |

Compiled Link/UI residency also falls from 31,400 to 30,600 bytes. With the
128,256-byte command/scratch reservation and 264-byte tail, total VDP1 usage
for all banks is 325,968 / 524,288 bytes (62% HUD), leaving 198,320 bytes free.
This bound includes both groups even if visibility retains all of them.

The reported intermittent striped-screen crash has not been reproduced here;
VRAM pressure was a measured risk, not a proven diagnosis of that crash.

Validation: face tile bytes unchanged in policy tests; 16x16 body tiles become
8x8; 8x8 body tiles become logical 4x4 with repeated-column 8x4 storage, including
transparent index zero. Source material tests cover face, hair, hood, anonymous
head, shared hair and Zelda's third expression segment. Full suite: 497 tests,
one skipped, two existing setup compile errors (`test_equipment_draw` and
`test_forest_partition`); no assertion failures after asset rebuild.

Normal and clean images both build, with 7,152 / 17,968 bytes below SGL's work
area. Separate `opening-check` nightmare replay on the project-local draw-cap
fixed Kronos reaches scene 2 (Deku/Navi) without a crash. Window captures show
Zelda/Impa at frame 293, Link at frame 465 with the 62% VRAM HUD, and scene 2
at frame 60. One successful replay does not establish an intermittent crash fix.
