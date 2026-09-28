# M8 draft: demo presentation, audio and tester support

Astra side draft, 2026-09-25. Expands DEMO_PLAN M8 after reviewed M7.

## Player-facing result and scope

The clean demo has coherent loading/door transitions, complete required sound
coverage, readable menus/help, version/build identity, useful error information,
and a README a tester can follow. This milestone closes presentation gaps in
working gameplay. It does not replace missing dungeon, item, save or story systems
with cosmetic placeholders, and it does not authorize a renderer rewrite.

All menus **must use VDP2**. This is the human's requirement to preserve VDP1
memory, not a preference to trade away when icons/maps are inconvenient. Menu
panels, text, cursor, icons, map/staff/help content, file select, shop choices and
Game Over UI must not allocate VDP1 textures or issue VDP1 menu sprite commands.
World actors retain their normal VDP1 path behind UI where appropriate; menu-only
3D previews are omitted or replaced with VDP2 artwork.

## Dependencies and evidence

M3-M7 should already supply their working doors, messages, item interfaces and
story transitions. M8 audits coverage and unifies presentation without introducing
second ownership/state machines. M2-M7 source-parity and deferred-case ledgers feed
README and acceptance; unresolved core cases stay blockers rather than becoming
vague "known issues". M9 owns final candidate validation and packaging.

Existing modules to inspect: `scene_flow`, `game_mode`, `message`, `main`, `cutscene`,
`music_banks`, current SFX loader, `save_file`/`save_device`, title/file UI and actual
VDP2 setup. Read `SAVE_CRASH_2026-09-25.md` and
`FOREGROUND_WARP_FAILURE_2026-09-18.md` before related changes.

Source references for behavior: OoT message/interface code, scene transition
handlers, audio sequences/SFX calls, life meter and game-over flow. This is a
coverage audit, not proof that every existing sound or UI behavior matches source.

## Delivery checkpoints

### M8a: VDP2 menu ownership and resource audit

Inventory every menu surface and its renderer: title/file select, pause pages,
shop, choices, Game Over/save, help, map, instrument overlay and boundary prompts.
For each, record VDP2 plane/layer, character data, pattern-name tables, palette,
priority/blend, font/icon reuse, upload timing and state restoration. Audit current
implementations; do not assume that a text-only screen proves all assets use VDP2.

Budget worst page, largest map and transitions while prerendered interiors/HUD are
resident. Reserve explicit tile/palette ranges or page banks to avoid overwriting
background assets. Upload/change state at a safe display boundary; restore camera
background, priorities and palette on close, scene change and error paths.

Use tile/page streaming or simplify menu art when VDP2 capacity is exceeded. No
VDP1 fallback. Track VDP1 residency/commands before, during and after every menu;
world pause behavior may change counts, but menu content must contribute none.
Check stale glyph cleanup, icon/cursor alignment and both display resolutions only
if the human later requests additional builds; current build target stays clean.

Review: VDP2 map, explicit VDP1-zero menu audit, before/after captures and no
corruption when menus open inside prerendered rooms or during bank transitions.

### M8b: transition and input consistency

Audit every door/scene/warp/respawn/cutscene handoff. Standardize fade/loading
presentation while preserving source destination/effect timing. No gameplay input
leaks while loading, no duplicate scene requests and no bright uninitialized frame.
Failure to load reports a useful outcome and retains/reaches a safe state rather
than running against partially installed collision or actor banks.

Preserve double-Start current-shot skip with its two-second prompt and complete
text cleanup. Ensure skipped shots still execute required story effects once.
Menu/context transitions flush stale button edges for digital and 3D controllers.
Controls help reports actual mapping, including 3D stick speed and D-pad routing.

Review: rapid door re-entry, skip at boundaries, pause/close, controller unplug,
slow media and bank failure fixtures. Do not use focus-stealing automation.

### M8c: sound coverage and lifecycle

Build a source-action -> sample/sequence -> bank -> trigger -> stop/restore matrix.
Include enemy/combat/shield/door/chest/item fanfare/heart/low-health/Game Over,
Navi, all area BGM, story shots, owl and ocarina. Distinguish missing coverage from
intentional scope omissions. Counts/bytes come from current assets, not old spare
RAM notes. Include staging/overlap peaks and note-on voice limits.

Audit core bank residency and swappable area bank lifetime around opening/story
banks, scene reload, death and instrument use. No sound ID can reference a released
bank. Avoid duplicate sounds per draw, orphan voices and repeated low-health alerts
while paused. If skip creates a chain of obsolete fades, bound/coalesce presentation
cues without dropping mandatory scene or gameplay events.

Review: named source event coverage, measured SCSP use, normal/skip playback,
scene churn, instrument cancel and Game Over -> continue music restoration.

### M8d: identity, diagnostics and save messages

Show demo version and reproducible build/source identity in title/help. Mark a
dirty candidate honestly; release packaging later records exact artifact hashes.
Keep routine developer overlays/test actors/debug grants out of clean UI.

Provide a minimal exception report with PC/PR/build identity using a proven safe
output path; avoid allocating memory or relying on the failing renderer inside a
crash handler. VDP2 is the display path for such text. Test with an isolated fault
fixture, never leave forced faults/debug triggers in the release image. Do not
claim recovery from arbitrary exceptions; useful reporting is the objective.

Audit save messages for success, full storage/device failure, old version and
corruption. Keep header-before-size validation and dependency tracking that fixed
the previous save crash. Save version changes belong to the feature changing the
layout, not a delayed M8 blanket bump. Destructive erase requires the normal player
choice; unsupported saves are never silently overwritten during inspection.

Review: identity visible, safe diagnostic fixture, every save-result message and
no stale prompt characters after state changes.

### M8e: tester README and support material

Write README-DEMO with exact supported emulator/version configuration and 4 MB
cart setup, start/load/save instructions, both controller layouts, shot skip and
menu/ocarina controls. List day-only Field, omitted enemies, destination boundaries,
2D VDP2 menus, current-shot skip and verified behavior differences honestly.
Meadow policy must match the human's eventual decision.

Include known issues with reproduction/impact/workaround, save-version policy,
and bug-report fields: build/hash, emulator/version/cart, scene/room, steps,
controller, expected/actual result, screenshot/registers and relevant save copy.
Explain how testers preserve backup data before sending/replacing files. Do not
publish source ROMs, private inputs or diagnostic save data as example attachments.

Review: another reader can boot the clean image and file a reproducible report
using only the README. M9 populates verified platform results and package hashes.

## Acceptance and release handoff

- Every menu is VDP2 with no menu-owned VDP1 texture/command cost; page, font,
  palette and prerender restoration budgets demonstrated, not assumed.
- Required transitions and sounds complete, with source coverage and bank-lifetime
  evidence. Clean image has no accidental developer UI or shortcut progression.
- Title/help identity, save error handling and crash report path are exercised.
- README matches delivered controls/scope/save behavior and observed emulator setup.
- Remaining gameplay blockers return to their owning milestone; M9 receives a
  concrete candidate and issue list, not an unbounded polishing task.

## Review and verification rules

Planning only; no implementation owner assigned here. Start code after preceding
milestone review and human owner assignment. Recheck current source and working
diff before taking files; M1/other active work stays with its owner. Dependencies
below describe required behavior, not permission for a parallel rewrite.

At each implementation checkpoint: focused host tests in separate processes,
**clean image only** per current human instruction, SGL map boundary, worst-room
VDP1 budget, cart bounds/heap high-water and audio bank bytes. Inspect changed
runtime hot paths for software float. Do not cut the malloc arena by guesswork.
Runtime checks use the project's non-focus-stealing workflow or human play;
report observed versus pending checks separately. No build/runtime checks were
performed for this draft. Source references are implementation research targets
unless explicitly marked verified; umbrella-plan actor lists are not spawn proof.

Record changed files, source parity, approximations, save compatibility, measured
budgets and deferred acceptance in OPUS_HANDOFF and VSLICEPROGRESS when code lands.
Code stays uncommitted for review unless human requests commit. Planning does not
complete a milestone or authorize the next one. All new actors include source
spawn/drop audits in the same task; characters use flat materials except faces.

All menus must use VDP2 for text, panels, icons, maps and cursors. Budget VDP2
storage/layers and restoration explicitly; no VDP1 menu textures or commands.
