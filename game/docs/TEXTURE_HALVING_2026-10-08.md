# Texture-halving Clean experiment — 2026-10-08

The usual `build/game-clean.cue/.iso` contains the human-accepted **mode-2** room
textures, built in WSL with `OOT_CORE=1`. Clean now defaults to **2**, retaining
explicit `DOSEI_TEX_HALVE=0/1/2` overrides. Standalone tools and other build
variants retain default **0**. The human clarified this covers mesh TEX tiles, not
NPC/item SPR sheets, HUD or RGB backdrops.

## Measured bytes

Baseline was captured before editing or rebuilding. Active-room statistics
exclude the three obsolete image-scene banks described below. All values are
bytes; TEX payloads exclude palettes, which live in the matching mesh tables.

| Measure | Before | Mode 2 |
|---|---:|---:|
| Largest active room TEX | 349,184 | 87,296 |
| Median active room TEX | 257,792 | 64,448 |
| Largest active room VRAM bank, including CLUTs/alignment | 361,664 | 124,640 |
| Median active room VRAM bank, including CLUTs/alignment | 278,176 | 79,680 |
| NAVIPOOL pixel allocation payload | 566,400 | 141,536 |
| Field pool pixels in STM | 401,536 | 100,816 |
| Field residency budget, including its actors/runtime sprites | 333,824 | 175,904 |
| All staged TEX payloads, including obsolete-bank removal | 89,966,776 | 22,327,712 |
| Whole Clean ISO | 151,592,960 | 83,494,912 |

The largest room's VRAM bank shrank **65.5%**; median VRAM shrank **71.4%**.
Active room TEX payloads shrank **75.0%**. CLUTs, geometry and alignment explain
why texture-area savings differ from pixel-file savings. No load-time timing
was measured.

Within the unchanged **445,432-byte** texture area, the largest active room
bank leaves **320,792 bytes** before other residents. Reserving **16,672** for
worst-age Link, **34,272** for existing runtime sprites and **65,536** for actors
leaves **204,312 bytes**; retaining a further 32 KiB margin leaves **171,544**.
Field's own residency sweep leaves **269,528 bytes**. These are offline budget
figures, not measured gameplay allocation. Existing actor/gear sublimits remain.

[Per-room CSV](TEXTURE_HALVING_2026-10-08.csv) lists all **390 baseline TEX
banks**: **387 active**, plus three explicitly marked obsolete removals. Columns
include pixel bytes, aligned bank bytes, texture-area free bytes, and free bytes
after the fixed resident reserves above. The corresponding empty flat bank has
no TEX file and is covered by the artifact checks instead.

## Implementation and verification

- **Code:** `DOSEI_TEX_HALVE=0/1/2` reuses the former `fit_room_pixels` sampler,
  now shared as `sample_indexed_tile`. The optional pass precedes the existing
  pixel cap and records changes in `reductions`. Width remains at least eight
  and a multiple of eight; palette entries and sampled transparency indices
  remain unchanged. Mode participates in the all-scene cache fingerprint.
- **Coverage:** native/generic rooms, authored/imported rooms, panorama/story
  banks, Navi's deduplicated pool and every Field pool tile, including near/far
  and landmarks. Field halves after pool construction, preserving tile IDs;
  Navi reuses already-halved room tiles without applying the pass twice.
  Mode 1 additionally handles child/adult Link and gear TEX. Mode 2 leaves
  their files byte-identical. No runtime renderer, caps or command-table change.
- **Host:** 34 focused unit cases pass: seven density/cleanup, nine existing
  room budget, thirteen Field/opening/VRAM, and five final retail-map checks.
  No skips. The saved pre-edit converter matches mode 0 on 100 varied budget
  fixtures and actual Deku room 0 MSH/TEX/manifest.
  After human acceptance, WSL Bash syntax and 15 actual wrapper selection/export
  cases pass: Clean unset selects 2, explicit overrides survive, other variants
  retain 0. Evidence: `build/tex-halve/clean-default.log`.
- **Actual assets:** all **388 retained room MSH banks** keep geometry,
  palettes, object bounds and LOD records; descriptors/pixel extents validate.
  Every Navi MAP reconstructs the corresponding TEX from NAVIPOOL. Field keeps
  all geometry/palettes and halves every pool tile exactly once. Seven Link
  binary/texture assets match baseline hashes.
- **Mode-1 offline smoke:** isolated outputs pass descriptor/palette checks:
  LINK 8,912 → 2,784 B; ADULT 7,928 → 2,808 B; LGEAR 6,272 → 3,136 B.
  These outputs were not staged in the mode-2 image. Mode 1 has no target or
  runtime acceptance claim.
- **Target:** full WSL Clean `OOT_CORE=1` mode-2 build passed, followed by a
  quick repack after obsolete-bank cleanup. Main `.bss` ends at `0x06083900`,
  with the same **1,792-byte** SGL margin. Both matching SH-2 math audits pass
  with zero forbidden software-wide/soft-float sites. All **1,452 ISO files** match staging;
  all 101 OOC scene blobs remain. Final ISO SHA-256:
  `2c455fe2ecf17d5686ac382ddb891a01aeef5af3212215d88fadfb9cdb69bd0d`.
- **Human acceptance:** user says the reduced textures look almost the same
  and reports improved performance. Their screenshot shows **VRAM 49%** and
  **CPU~ 79%**. This accepts the reduced look and keeping mode 2 for Clean;
  no paired FPS/load-time gain or separate Kokiri/Field route completion was
  measured. Broader gameplay checks remain open. No emulator was launched by
  the agent. The accepted image already uses mode 2; only the future Clean
  build default changes, so no new target rebuild is needed for this setting.

## Stale-bank finding and evidence

`SNR0`, `SPR0`, `SQR0` still held old story MSH/TEX data under current image
scene IDs: `entra_n`, `market_alley`, `market_alley_n`. Registration and the
runtime image branch use RGB backdrops there; current story banks use C* IDs.
These three old banks were not rewritten by the current room builder and made
the first raw-file maximum misleading. Density builds now prune only native
MSH/TEX for image registrations. RGB, collision, mesh registrations and C*
story/panorama files remain. Explicit mode 0 performs no cleanup.

Removal saved **734,208 TEX bytes**, **896,064 total staged bytes** across six
files. This is separate from resampling savings. Original files remain backed
up under `build/tex-halve/before-banks`; the exact removal ledger is
`build/generated/obsolete_image_banks.json`.

Evidence: `build/tex-halve/before.json`, `before-image.json`, `after.json`,
`after.csv`, `field-before.json`, `off-verification.log`, `mode2-clean.log`,
`mode2-repack.log`, `final-map-tests.log`, `iso-audit.json`, `game-wide.log`,
`core-wide.log` and the isolated
`mode1/` outputs. See [BUILD.md](BUILD.md) for repeatable commands and cache/
interruption gotchas. Mandatory Player migration and other runtime acceptance
requirements remain open.
