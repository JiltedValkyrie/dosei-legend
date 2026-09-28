# Minimap plan (VDP2 NBG2 + VDP1 markers)

Claude, 2026-09-27. Built (standard + Clean); Kronos visual check pending.
Code: tools/build_minimap.py, src/minimap.c/.h, MINIMAP.BIN (cart 0xD000).
Not yet: hi-res (map off in 480i), entrance icon, red start arrow
(sPlayerInitialPos), hide toggle binding, dungeon floors.
Source: `src/code/z_map_exp.c` (Minimap_Draw, Minimap_DrawCompassIcons),
`src/code/z_map_data.c` (sOwMinimap*, sOwCompassInfo), map_grand_static.

## Layers and VRAM (read from Jo/SGL setup, not measured)

| Resource | Use | Minimap |
|---|---|---|
| NBG0, B1 | printf text/HUD | keep, top priority |
| NBG1, A0+A1 | 512x256 16-bit bitmap (title, backdrops) | keep |
| NBG2 | unused | **map layer**: cell mode, 16 colours, no zoom |
| NBG3 | forced off while NBG1 is 32768-colour | unavailable |
| RBG0 | tables in A1 under the NBG1 bitmap | unavailable |
| B0 | unallocated in bitmap mode | **minimap reservation** |

## Reservations

- B0 `0x25E40000`: NBG2 page map, 8 KB (64x64 one-word names).
- B0 `+0x2000`: minimap cells, 16 KB max (4bpp; 96x85 largest source map
  = 12x11 cells = 4.2 KB; hi-res 2x-tall copy fits). Rest of B0 free.
- CRAM: one 16-colour bank for the map ramp, one for markers (Link arrow,
  entrance icon, debug dots). Picked above palettes the text uses.
- Named constants in one header (`minimap_vram.h`); no other code writes B0.

## Per-scene data (generated, one row per scene/floor)

texture id, width, height, screen x/y (sOwMinimapPosX/Y), compass
scale x/y + offset x/y (sOwCompassInfo), entrance icon x/y + flag
(sOwEntranceIconPos*, sOwEntranceFlag), colour (R_MINIMAP_COLOR 0,255,255),
hi-res variant flag. Dungeons later: rooms/floors (dgnMinimap*, floor Y
table, room switch table) and map/compass ownership rules use the same
row shape with a floor index. Kokiri Forest = map index 4: 96x62 at
(202,160), compass {8, 8, 660, -730}.

## Runtime

- Scene load: upload that scene's cells/map to the B0 reservation, set
  NBG2 scroll to the screen position, enable NBG2; scenes without a map
  disable it.
- Link arrow (VDP1, every frame): screen x = 160 + (offX + x/scaleX)/10,
  y = 120 - (offY - z/scaleY)/10; 8 facing frames from shape yaw.
- Marker priority: Jo SPCTL 0x23 (type 3, mixed). RGB world pixels use
  sprite priority 0 (below NBG2); marker sprites are palette pixels with
  the priority bit set -> slot 1, set above NBG2.
- Enemy dots: `#ifndef DOSEI_CLEAN_TEST` only (test nut for now).
- Hide: minimapAlpha rules (hidden in text/pause/cutscene) plus a user
  toggle; both just switch NBG2 and markers off.
- Hi-res 480i: NBG2 cannot zoom; use a 2x-tall baked copy and doubled y.

## Unverified until built (visual check required)

VDP2 VRAM cycle pattern with NBG2 on B0 next to the NBG1 bitmap and NBG0
text; marker sprite priority 1 above NBG2 while the world stays below;
fades (colour offset must include NBG2).
