# Inventory visual changes, 2026-10-08

Implemented, host-tested and included in the matching Clean target. Combined
target/ISO evidence is in [INVENTORY_HANDOFF_2026-10-08.md](INVENTORY_HANDOFF_2026-10-08.md).
Human runtime acceptance remains open. This does not complete Player migration or
inventory gameplay. No actor is imported or converted by this visual work.

## First-person tools

`ITMAIM.SPR` contains slingshot, bow and hookshot hand/tool pictures. The source
selections are `Player_OverrideLimbDrawGameplayFirstPerson`:
`gLinkChildRightArmStretchedSlingshotDL`,
`gLinkAdultRightHandHoldingBowFirstPersonDL` and
`gLinkAdultRightHandHoldingHookshotFarDL`. Offline posing uses the final frame
of `gPlayerAnim_link_bow_bow_ready` or `gPlayerAnim_link_hook_shot_ready`, selected
by the source `func_80834D2C`. The existing Flex importer preserves per-vertex
matrix ownership before rendering the hand. Link materials remain flat.

This is a static presentation approximation: fixed rear three-quarter views
and lower-right screen placement, without source draw/release animation or
full first-person forearms. No skeleton, mesh or animation bank is added at
runtime. Source item/projectile behavior remains separate and unchanged here.
The existing VDP2 crosshair and its position are unchanged.

The SPR1 atlas uses direct cells 0/1/2 for slingshot/bow/hookshot; cells 3/4
are blank. World yaw lookup must not be used for this presentation-only sheet.
`npc_sprite_draw_screen` shares the existing cel upload/rebind code. One cel
draws at a time. A read-only `recomp_aim_inventory_slot` selects the art; regular
and elemental bows share a picture, as do hookshot/longshot.

Budget: 10,296 B cart heap, 2,080 B VDP1 including CLUT, one sprite slot and
one displayed sprite command. The atlas preloads with room resources, so a
new inventory pickup needs no live CD read. `vdp1_budget.py` reserves its
complete byte/slot cost beside room and actor budgets, preserving the 32 KiB
spare margin. The regular loader and upload capacity guards stay enabled;
missing or unaffordable presentation never alters shot admission or substitutes
another item's art.

## Adult equipment

The previous optional gear-bank failure hid Biggoron's Sword and the Mirror
Shield: special equipment bits removed ordinary Link's placeholders, while
`gear_ready == false` prevented the replacement geometry. Hylian then used the
flat base-model variant. The new fallback retains the correct original gear
geometry, original vertex ownership, shield culling and live normals.

Exact duplicate texture tiles now share storage across all gear groups:
325 -> 196 tiles; 20,832 -> 12,576 B for pixels/CLUTs, saving 8,256 B and 129
sprite slots. Geometry is unchanged: 534 polygons and 355 vertices across 11
mutually selected groups. `LGEARMSH.BIN` appends one RGB555 fallback per polygon
(1,068 B). Overall staged gear heap drops by 8,736 B after deduplication and
this addition. Generated assets and runtime header must be rebuilt together.

If VRAM or slots cannot hold artwork, geometry uses these baked colours.
Missing/short `LGEARTEX.BIN` or `LGEAR.TEX` also preserves valid geometry with
the same fallback. Hylian's design surface becomes blue; Mirror's frame becomes
red and reflective centre silver. Reverse surfaces keep source-derived colours.
Texture IDs remain intact while flat, and the next room that fits restores
source textures without a new mesh or live CD read. A missing/invalid geometry
or skin file still fails its existing loader validation; flat fallback requires
valid source geometry.

## Verification

WSL: all 9 `test_link_shield.py` checks pass without skips. They cover actual
source materials, culling and live rotations; original variant selection;
fallback colour provenance; cross-group tile sharing; and the real upload
function through byte exhaustion, slot exhaustion, missing pixels, and repeated
texture restoration. All 2 `test_item_sprites.py` checks pass without skips,
including a complete source bake and three distinct nonempty bounded aim cels.
The atlas preview was inspected offline. No emulator was launched.

Owned edits: `build_item_sprites.py`, `build_link_gear.py`, `vdp1_budget.py`,
`npc_sprite.c/.h`, gear loader/upload in `kokiri_sgl.c`, upload comment in
`npc_draw.c`, `TOOL_AIM` load/draw in `oot_core_host.c/.h`, aim-slot query in
`recomp.c/.h`, aim presentation call in `main.c`, and the two tests above.
Existing dirty changes in those shared files were preserved.

Combined target RAM fit and complete scene budget checks pass; the linked
combined handoff records measurements. Rendered gameplay acceptance remains open.
