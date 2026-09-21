# Dosei Legend — vertical slice scope

> **Superseded for gameplay scope, 2026-09-21.** The human approved the full OoT
> opening progression: Kokiri Forest, Lost Woods, the Great Deku Tree and Gohma,
> through to the Kokiri Emerald, with real quest flags, backup-RAM saves, full
> cutscene playback, real ROM models and hearts/damage/death. The game now
> requires the 4 MB RAM expansion cart. See
> [game/docs/OOT_PROGRESSION_PLAN.md](game/docs/OOT_PROGRESSION_PLAN.md).
>
> The "Exclusions" section below no longer applies to bosses, dungeons or quest
> systems. Everything else here — the presentation baseline, the testing limits
> and the anti-overtesting rules — still stands.

## Goal

A playable Sega Saturn adaptation of the N64 Kokiri Forest baseline: recognizable
setting, controllable Link, characters to talk to, working menus, animation and
audio. This is a vertical slice, not a complete game or a launch-quality release.
Active implementation: `game/`. Keep `legacy/libyaul/` as the libyaul reference.

## Required experience

- Title artwork, prompt, music, and transition into forest gameplay.
- Explore Kokiri Forest as Link with usable controls, follow camera, collision
  and terrain handling. Near-camera textures must not make navigation unreadable.
- Link idles when stopped and animates while walking; interactions have visible
  feedback. Camera motion and character facing must be understandable.
- Kokiri NPCs populate the slice. Start with one complete proximity interaction:
  approach, prompt, open dialogue, advance pages, dismiss, resume movement.
- Functional menus: open, navigate, confirm/cancel, close and return to play.
  Do not build nonfunctional screens for excluded systems.
- Title/forest themes, gameplay/interaction sound effects and menu feedback.
  Music and effects coexist without losing controls or crashing.

Baseline match means recognizable N64 behavior/presentation within this area,
not pixel-perfect reproduction. Extend NPC coverage after one complete interaction;
do not claim all forest NPC scripting is done when only one conversation exists.

## Exclusions

Still excluded: the full overworld beyond Kokiri Forest, Lost Woods, the Great
Deku Tree and the Kokiri shop; anything after the Kokiri Emerald. No optimization
campaign, exhaustive soak tests, exact music-switch timing target, or launch-level
polish as prerequisites for the slice.

**No longer excluded** (superseded 2026-09-21): bosses, dungeons and quest
systems. Gohma and the Great Deku Tree are in scope, as is the quest-flag and
save infrastructure they need.

## Priorities

1. Fix near-camera texture warping to a playable level; the human reports it is
   almost unplayable. Hi-res is not a substitute for this fix.
2. Walk/idle animation and a complete NPC/dialogue interaction.
3. Functional menus, interaction animations and sound effects.
4. Short end-to-end playthrough and fixes for actual blockers.

## Hi-res experiment

Retain standard 320x240. Provide a separately built/launched native 320x480
interlaced variant with the same gameplay, assets and sound. Compare readability
in Kronos; hardware appearance is not established by an emulator. This doubles
vertical resolution only. It does not improve source textures or fix perspective
warping. Do not make it the default without the human's preference.

## Done enough

A human can start, explore as animated Link, talk to an NPC, advance/dismiss
dialogue, use the menus, and hear music/effects without a major playability blocker.
Missing polish is acceptable; record it plainly.

Default validation: build, focused tests and a short relevant runtime check.
Expand only at human request or for a major bug. Retain memory/capacity guards.
Update [VSLICEPROGRESS.md](VSLICEPROGRESS.md) as work lands; distinguish implemented,
observed working and still unverified.
