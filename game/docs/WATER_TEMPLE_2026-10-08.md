# Water Temple source integration

Human requests this immediately after Field, as a full dungeon integration test.
Source scene 5 (`MIZUsin`), runtime scene 79 (`Z27`), 23 rooms and 25 waterboxes.
Do not confuse source ids with runtime/save indices.

Code in progress: the temporary C collision backend can borrow the source
WaterBox table while the Water Temple PlayState lives. Queries see source actor
height changes immediately, including indices 16..24, without raising the
legacy 16-entry override cap or keeping another mutable height copy. Host writes
are refused while borrowing. Scene replacement/unload unbinds before OOC release.
This is water ownership plumbing, not completion of real Player migration.
Core ABI26 support now compiles in the Clean raw target; the accepted Field ISO
is still ABI25 and is unchanged. This is not a Water Temple actor-pack build.

Transition plumbing now preserves original TransitionActorEntry lists for every
scene layer, including absent versus explicitly empty headers. Water Temple has
27 transition entries; room passage actor En_Holl was missing from the original
inventory and is now included. Runtime binding preserves indices and enables
the source table only after all of its actor profiles exist. Source room-side
spawning runs on load/room change. Three host cases cover extracted retail data,
layer fallback, one-time spawning and encoded door indices. No unavailable door
is marked spawned. En_Holl room requests and Player door traversal remain open.
OOC format 0x4f4f4302 rejects stale blobs; all OOCs must regenerate before the
next disc build. Pack loader rejection/ownership tests pass (nine cases).

Host: the live-water/room/unbind test and four scene-lifetime tests pass. Twenty
original prop actors compile in an isolated SH-2 probe (63,238 bytes of unlinked
text, not a final pack size). There are 39 extra resident-engine exports and
126 unresolved references, largely assets plus Player/camera/room interfaces.
All 36 prop/enemy/support translation units now compile in the isolated SH-2
probe, with no importer problems. With the five sprite conversions below,
combined unlinked text is 140,644 bytes; unresolved engine/asset references remain.
This is not a linked pack or runtime admission. With the current 84,620-byte
OOC, raw text alone would leave 36,880 bytes in the 256 KiB scene carve before
rodata, writable data, the 2,534-byte sprite helper and object payloads.
Measure the linked complete population before choosing its final placement.
No temple actor pack is staged, no temple target build or human dungeon acceptance yet.

Sprite conversions (code, host tests, isolated SH-2 compile, offline bake):
- Shell Blade: clock-only clips; status/effect timing moved from Draw to
  Update; source death/drops keep the bounded body-break completion adapter.
- Stinger: root display offset baked; source death alpha and scale in view.
- Tektite: feet and contact sphere from offline anchors in Update (source
  sFootOffset, limbs 8/13/18/23); ice-chunk timer moved to Update. View
  variant 1 = blue textures (TEKTITE_BLUE), 0 = red.
- Keese: wing/body effect anchors baked (root +2300); elemental effects run
  from Update. Source Draw lerps TEXEL1 (gKeese*) / TEXEL0 (gFireKeese*) by env
  alpha; the bake now honours that. Variant 0 = normal body plus gKeeseEyesDL
  on KEESE_LIMB_HEAD (also ice Keese), 1 = fire body. REACT_TO_LENS Keese are
  hidden unless the Lens is active, matching the source DrawXlu limb gate.
- Spikes: no skeleton. Contact sphere and both fire cadences moved to Update.
  Skeleton-less display-list bake keys rock/metal/spiked variants by the
  gEnNyRockBodyDL/gEnNySpikeDL symbols. Death rock fragments are not drawn
  (body hidden while the source death effect owns Draw); death/drop timing kept.
Host: core views (Tektite/Keese/Spikes variants, lens and death visibility)
and the water sprite anchor fixture pass. 25 sheets bake; the Clean raw
target links them into archives: Z27 needs 394,097 sprite heap bytes
(Tektite 216,097 of it for both colour sets), below Field SA's 479,243 peak.
Not runtime-admitted: no temple pack or population/heap acceptance.
Pending: Like Like (Player grab, shield/tunic theft) and Dark Link (Player
skeleton/mirroring) need real Player integration; support actors unconverted.
The shared offline converter now supports source ModifyVertex ST/RGBA cache
edits without applying skin transforms twice; two command tests and two sprite
view tests pass. Unsupported screen-coordinate edits still fail explicitly.

Current support target: WSL Clean raw compile succeeds, .bss ends 0x060837f0
(2,064 bytes below fixed SGL). Core (1,400 sites) and converted-enemy/helper
math audits pass, zero forbidden sites;
Field pack remains within its existing carve. Current CD staging is transitional:
only explicitly requested OOCs are rebuilt so far; do not master it without all
101 OOCs, new sprite admission and matching packs being validated.

The actual imported BgMizuWater actions also pass a Linux host probe: source
level priority/current-flag exclusion, old-switch clearing, a new request during
motion, five-unit main-level steps, all eight affected indices across 25 boxes,
and local water types 2/3/4 rising and falling by one unit. Untouched water boxes
stay unchanged. Cutscene/message calls are checked engine I/O, not camera or
ocarina integration acceptance. Six water/lifetime/core-rate host cases pass.

Source actor sets are in `tools/water_temple_sources.py`. Prop scope includes
water planes, moving platforms, breakable walls, timed shutters, vortex collision,
switches, hookshot blocks, push blocks/stops, room timers, jets/currents, spike
traps, boulders, time/ice blocks, chests, source doors and ocarina triggers.
Non-boss enemy scope includes Keese, Spikes, Like Likes, Shell Blades, Tektites,
Stingers and Dark Link; Skulltulas/rewards and Ruto/scarecrow support are included
in the source inventory. Sprite conversion is required before runtime admission.
Morpha keeps the explicit boss/model/complex-hitbox exemption.

Required dependencies remain explicit: source transition-actor door records;
water-level/ocarina/save flags; collision/carry for moving platforms and push
blocks; hookshot attachment; key/chest/room-clear gates; currents and Iron Boots;
Like Like capture/gear recovery; Dark Link's real Player dependencies; original
drops, source effects and sound. Existing C Player proxy fields alone do not
establish these behaviors. Measure complete room/actor/object/effect populations
inside existing texture, scene, arena and command limits before staging.

Evidence: `build/water-temple/props.json`, `all.json`, per-actor compile logs;
`build/field-enemies/host-water.log`. The probe never writes the running disc.
Run source actions with `bash oot-core/tests/run_water_temple_probe.sh` in WSL.
The compile inventory needs its imported actor-directory include path for
Ruto's cutscene include; it does not replace that data with a placeholder.
