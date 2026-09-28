# Navi C-Up prompt on VDP2

Codex source/layout review and implementation, 2026-09-27. Human expanded
scope to the gameplay button HUD and selected Saturn A/X/C labels. Human
reviews visuals with the finished M2 batch; no agent emulator checks.

## Implemented status

- Original OoT green sword button, blue action button, amber C directions,
  and blinking Navi graphic; small Saturn A/X/C identifiers. The direction
  label swaps live to D-PAD for a connected 3D pad in analog mode; digital
  mode uses C. Label sits above the direction cluster. Sword artwork
  follows equipped state. Action artwork follows existing Enter > Open >
  Speak priority. The separate text prompts were removed from main.c.
- C-item slots show original empty arrows: the game has no C-item assignment
  state yet. No invented equipment bindings or control changes. Health and
  rupee displays remain their existing separate systems.
- `build_gameplay_hud.py` runs from build_minimap.py, emits BUTTONS.BIN and
  gameplay_hud_data.h. 111 deduplicated cells = 3,552 VDP2 bytes; no VDP1
  allocation. Sixteen variant maps use 4,864 work-RAM bytes plus palette/state
  and a 16-byte D-PAD label map patch.
  Actual quantized artwork preview: build/generated/gameplay-hud-preview.png.
- NBG2 has zero scroll; map artwork gets transparent sub-cell padding, so
  Kokiri remains exactly at (202,160), with unchanged marker coordinates.
  Map cells own B0+0x2000..0x3FFF, buttons B0+0x4000..0x5FFF. Palette
  CRAM 800..815 is separate from map 768..783 and markers 784..799.
  Minimap payload is 3,948 bytes, guarded against its 4,096-byte cart carve.
- `minimap_layer_flags` refreshes the
  shared page even without a map row. Independent hiding, scene clear/restore,
  pause/title/file-select/dialogue/cutscene suppression. Navi reads existing
  gameplay.navi_calling; blink uses 60 Hz demo ticks, not render frame count.
- Validation: Clean image built, 12,304 bytes below SGL work area. Thirteen
  focused tests pass (5 HUD + 8 minimap): artwork indices/transparency,
  tile/cart limits, exact map placement, blink/pause timing and action priority.
- Remaining visual approximations: 16-colour palette and thresholded alpha;
  no N64 A-button rotation or partial HUD fades for crawl/underwater yet.
  NBG2 remains standard-resolution only, matching the existing minimap limit.
  Human must check palette selection, layer priority, prompt appearance and
  scene transitions in the final M2 batch. Host checks do not prove those.

## Source contract

Local OoT `src/code/z_parameter.c`, `Interface_SetNaviCall` and
`Interface_DrawItemButtons`:

- `naviCalling` owns prompt visibility, not Navi's position, proximity alone,
  or whether an actor is locked. Connect this to the actual available hint/
  dialogue state being implemented; clear it when source conditions clear it.
- The call transition initializes visible phase and a 10-update timer.
  Drawing toggles visibility every 10 eligible interface updates. Translate
  source timing into the game's timebase; do not use render-frame counts.
- Hide during pause and cutscenes. Source HUD visibility modes can force
  alpha zero; crawling, underwater-free and PLAYER_STATE1_21 use alpha 70;
  otherwise use healthAlpha. Trace the named flag and local equivalents before
  mapping it. Do not restart the blink timer on every draw or repeat audio.
- `include/interface.h`: C-Up button origin (254,16), displayed 16x16.
  `z_construct.c`: label origin (247,20), displayed 32x8; button tint
  RGB(255,160,0), label white. The label overlaps the button, as in the source.
- Artwork: `assets/xml/textures/parameter_static.xml` names
  `gButtonBackgroundTex` (IA8, 32x32, offset 0xA00) and `gNaviCUpENGTex`
  (IA4, 32x8, offset 0x2FC0). Follow the texture load active at the C-Up draw
  before extracting/compositing the button. Use local US 1.2 assets, not a
  recreated text label or downloaded screenshot.

The N64 C-Up graphic denotes the logical action. Retain the current Saturn
input adapter (digital C+Up, analog-mode D-pad Up); do not remap controls.
First-person fallback is separate behavior, not something the graphic enables.

## Proposed VDP2 implementation

Use the existing 16-colour NBG2 HUD/minimap plane. It already has an allocated
map and fetch configuration; avoid adding another layer or consuming VDP1 slots.

Current ownership (`src/minimap.h` / `src/minimap.c`):

| Resource | Current use |
|---|---|
| VDP2 B0 + 0x0000..0x1FFF | NBG2 64x64 one-word map |
| VDP2 B0 + 0x2000..0x5FFF | Minimap cell reservation |
| CRAM 768..783 | Minimap palette |
| CRAM 784..785 | VDP1 minimap markers |
| NBG0 | Existing text/font |
| NBG1 | Title/interior backdrop |
| B1 + 0x1F000 | Sky table; preserve |

1. Bake original prompt artwork offline to transparent 4bpp 8x8 cells.
   Preserve its sub-cell placement with transparent padding. Composite label
   over button offline; reserve a distinct 16-colour palette. CRAM 800..815
   is a candidate only: audit all palette users and SGL palette-name encoding
   before allocating. Assert cell/palette bounds in the builder.
2. Convert NBG2 to a fixed screen-coordinate page (zero scroll). Currently
   minimap_scene scrolls the plane to the map's pixel origin. Bake/pad the map
   to its source pixel origin in the shared page, preserving exact placement
   even when x/y are not multiples of eight. Keep marker screen coordinates.
   This prevents the prompt moving when maps change. Do not merely stamp the
   prompt into the existing scrolled page.
3. Reserve prompt cells within the existing B0 cell reservation, separate from
   minimap uploads; reject a generated map that overlaps them. A tile-aligned
   40x16 composite needs 10 cells (320 bytes); allow bounds to follow the actual
   composite and padding. Never assume this fits every future map without a guard.
4. Initialize the shared page and prompt even in scenes with no minimap row.
   Draw/clear map and prompt rectangles independently. `minimap_layer_flags()`
   currently enables NBG2 only when a map is visible: generalize to map OR
   prompt visible. Hiding the minimap must not suppress a valid Navi prompt.
   Scene uploads must restore prompt cells/map entries instead of erasing them.
5. Preserve NBG2 priority below NBG0 text and above the world. Audit both
   main.c initialization and kokiri_sgl.c backdrop/world screen switches.
   Clear prompt on title, file select, pause, dialogue/state transitions and
   scene changes according to the call/HUD state. Check fade masks explicitly.
6. Keep prompt state independent of display writes: expose pending/visible/
   intensity from the hint interface; graphics consumes it. Blink by replacing
   only prompt map entries with the transparent cell. For partial alpha, use
   a documented local dither approximation if needed; do not fade the whole
   minimap plane just to fade Navi. No runtime float math or per-frame CD reads.

## Validation and ownership

- Claude owns implementation and integration with the current hint work.
  This plan does not assign Codex edits to active main/minimap/Navi code.
- Focused checks: pending/no-pending transitions; blink cadence across render
  rates; no repeated audio; minimap hidden or absent; exact padded pixel
  positions; scene uploads and cell bounds; palette isolation; menu cleanup.
- Clean build only. Keep existing hires limitations explicit; no hires build
  required for this task. No agent Kronos/background checks.
- Add to final M2 human checklist: prompt appearance/placement, blink, C-Up
  hint consumption, disappearance after dialogue, map toggle and room change.
  Human checks visuals and audio once with the completed M2 batch.
