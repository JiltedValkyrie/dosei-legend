# VDP2 pause windows and health HUD

Human scope: four OoT Start-menu pages and save window; show only actually
owned items. Existing gear equip/save stay live. Unimplemented item actions
must not report success. Human handles Kronos; no emulator was launched.

## Runtime

Latest additions: the 3D scene and ambient animation freeze behind transparent
grey dither. Music ducks by 6 dB independently of SFX and existing music fades.
System includes saved label presets (Saturn auto, Xbox, N64, GameCube, PS4/5),
optional physical jump binding and Reset defaults. DOSEICFG is an independent
8-byte checked backup record; write failure is shown, game slots unchanged.
Jump defaults to Saturn Y; custom binding replaces that button's gameplay
action, while menu navigation stays unchanged. Label presets alone do not remap
emulator inputs. N64 omits the default jump label. Enemy-map status is hidden
when the cheat is off. Clean keycaps replace the old baked L/R artwork.

Map now renders at 288x171 (source 216x128, uniform scale rounded to pixels),
with eleven regional 15-colour palettes instead of 13 colours for the whole
page. Up to 165 art colours; source clouds/discovery state unchanged. This is
a larger rendering of original artwork, not newly invented high-resolution art.
Map page uses CRAM 848..1023 and a 39,952-byte cart record, still within the
existing 40 KiB reservation. Other pages retain their 38,432-byte format.
Button label maps moved to B0+0x12000..0x13FFF (5,344 bytes used), saving
work RAM. Pause/map cells remain B0+0x6000..0xF5FF; no extra VDP1 allocation.

- Start opens/closes. L/R changes Items, Map, Quest Status, Equipment, System.
- D-pad moves the Items/Equipment cursor; A equips owned sword/shield.
- B opens the save question; directions select Yes/No, A confirms. B returns
  to the page. Start leaves either window. Save uses the existing backup-device
  request and reports its actual result, including failure/no device.
- Items read stick_owned and slingshot. Equipment reads gameplay.owned and
  equipped; the default tunic/boots remain visible. Quest reads the Emerald
  bit. No unowned item preview icons. Stick/slingshot use remains unwired here.
- Map shows the original map with undiscovered-region clouds and Kokiri marker.
  Current slice has Kokiri plus its interiors; no invented travel/discovery state.
- Hearts read save_state.health and health_capacity (16 units per heart).
  Empty/quarter/half/three-quarter/full textures use the original fraction
  table, tint, 10-heart row spacing and a size pulse on the last occupied heart.
  Capacity clamps at 20; damage, healing, death and file load update by reading
  live state. No Claude damage callback is needed. Existing HUD visibility
  suppresses hearts in title/file select/cutscene/dialogue/pause.

## System page and session cheat follow-up

System offers Save game, Load game, Return to title. Load/Title require a
Yes/No warning about lost unsaved progress; No is selected initially. B cancels;
Start closes. Load enters the existing file select without writing anything.
The page shows the live detected port-1 controller type and enemy-map state.
Digital-mode 3D pads identify as ordinary digital pads, so the label says
Digital pad; analog mode says 3D pad (analog). Disconnected and unsupported
inputs are reported explicitly.

Selection outlines are light blue (palette 15); equipped outlines remain gold
(palette 14). Page art uses palette entries 1..13, with zero transparent.

Enemy-map cheat is session state only. It survives map/room changes and normal
respawn, clears when ending a session or choosing a new/load file, and is never
serialized. Markers enumerate all active hostile enemies/bosses, not just the
old test projectile. Completing the code consumes Start until it is released;
another Start press remains the normal pause control. Code is still Up Up Down
Down Left Right Left Right A Start, and repeating it switches the cheat off.

Latest follow-up Clean: .bss ends 0x06082B60, 5,280 B below SGL; 250 focused
checks pass. Human Kronos check pending. PAUSE50.BIN adds one disc page using
the existing page buffer/cells, with no additional VRAM allocation.

## Assets and memory

Original extracted English pause section textures, source page colour arrays,
slot positions, original cursor masks, world-map clouds and normal heart IA
textures. Saturn left-page label is L (the N64 source texture says Z).
Offline tools: build_pause_windows.py and build_health_hud.py. build.sh bakes
pause assets; build_gameplay_hud.py also bakes hearts.

NBG2 shares the existing HUD name table at VDP2 B0+0. Pause cells occupy
B0+0x6000..0xF5FF (38,400 bytes), CRAM 816..831. A 40 KB cart carve at fixed
pool offset 0x1D000 stores one page; fixed pool grows to 0x27000. Page changes
stream from CD; cursor movement uses the cached page. Closing restores minimap,
button names and heart names. No extra VDP1 texture slots.

Heart cells occupy B0+0x10000..0x1077F (1,920 bytes); their source atlas is
B0+0x10800..0x10A7F (640 bytes), CRAM 832..847. HEARTS.BIN is 672 bytes.
Only small status fields and a 32-byte loading buffer use work RAM.

## Parity limits / review

This is the standard-resolution, front-facing window implementation, not a
claim of complete KaleidoScope parity. The 3D page-turn animation and animated
Link equipment portrait remain unimplemented; the portrait aperture is blank.
Dungeon map content, songs/quest interactions, C-item assignment and unavailable
inventory systems remain for their own gameplay implementations. Item labels
use the existing VDP2 font rather than OoT's variable-width font. No hidden
items are drawn to make unfinished pages appear populated.

Human batch review: open/close in forest and interiors, change all pages,
compare owned/unowned gear, equip sword/shield, cancel and confirm a real save,
then take quarter/half-heart damage and heal; check HUD restoration after pause
and after scene changes. Test digital and 3D pad navigation. Do not call visual
parity verified until that review.

## Verification

Clean built successfully with shared M2e/Game Over changes; final .bss end
0x06082DF0 leaves 4,624 bytes below SGL. 153 gameplay, 7 pause/health, 6 button
HUD and 8 minimap checks passed. No Kronos run or commit. Human batch review
remains pending; BUG-046 tracks incomplete visual parity.
