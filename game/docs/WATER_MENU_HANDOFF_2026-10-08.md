# Water ledge and debug menu - 2026-10-08

## Changes

- Surface swimmers use wall, floor, facing, delay/A and landing headroom checks
  before A to dive. Control transfers to STEP_UP with the original swim step-up
  clip. Tall banks, low ceilings, blocked controls and diving do not climb.
- Child/adult entry, exit, buoyancy, resurfacing and collision clearances use
  age thresholds. Preserve these fixes in the mandatory real Player migration.
- Start opens saves; the last row is Level Select (Debug Mode), opening without
  delay. The original title cheat remains with its existing input delay.
- Region then map then options: all 101 maps occur once in ten regions. Shared
  interiors have their own group. A cycles Room and toggles Link: Child/Adult
  and All Items? Off/On. Begin Play Test starts; Go Back returns to maps. B
  backs through the hierarchy to saves. Left/right also cycles Room.
- Browsing and toggling leave the live save and backup slots untouched.
  Failed room entry stays on options with its error; Forest Temple room 9
  retains its existing direct-placement limitation.

## Verification

- 104 host checks pass without skips: water (18), land ledges (40), level menu,
  legacy opening delay and save files (46). Log: build/water-menu-tests.log.
- Full WSL Clean rebuild passes, including regenerated child/adult clip assets.
  Main .bss ends 0x06083740, 2,240 bytes before SGL; heap and actor capacities
  unchanged. Resident core remains 508,560 bytes. Build: build/water-menu-build.log.
- Both ELF integer/math audits pass. ISO has 1,457 files (79 filesystem slots
  spare), all byte-identical to staging; LINKANIM.BIN matches generated clips.
  ISO size 151,918,592 bytes. Evidence: build/water-menu/.
- 15 additional map/session checks pass without skips: continue/respawn, collision
  capacities, all-map registration, scene resource lifetime and music trimming.
  Total this task: 119 host checks. Log: build/water-menu/map-regression.log.
- No runtime/human acceptance claimed: check both ages at the reported shore,
  menu readability and navigation, test start and return through the save screen.
  Kronos was closed before rebuilding the usual game-clean.cue/.iso. No commit.

SHA-256 of the final Clean ISO:
`6ff96cdc8ffe7360328ecbe61bc97413d4336a42bf5f7c6f3810b1ee6664f774`
Main disc payload:
`cfd47f8860d73861d6a4859f77fe04fc4edc66a9d04120481b6131692ab629b4`
Core disc payload:
`c064546f350f7708f26ae936993d0429a44c6c9fefe9b63d66ba88e34c188a66`
