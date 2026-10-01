# M2c review: sword, guard and evasion

Claude, 2026-09-27. Uncommitted. Human Kronos checks run in bulk after M2.
Source: `ovl_player_actor/z_player.c` (ntsc-1.2 decomp), `z_en_nutsball.c`.

## Input precedence (one 30 Hz step)

Checked in this order; the first that claims the step wins.

| # | Input / state | Result | Source |
|---|---|---|---|
| 1 | Start, open text box, chest | world frozen, no combat | pause / talk |
| 2 | Blade AT_BOUNCED last pass | rebound (phase 8) or stab ends | func_80842DF4 -> func_80842D20 |
| 3 | Shield AC_BOUNCED last pass, guarding | guard recoil (phase 9) | Player_UpdateDamage -> 808435C4 |
| 4 | Charging (phases 3-5) | charge / release spin / cancel | 80844E68, func_80844BE4 |
| 5 | Crouch stab running (phase 7) | stab clip | Player_Action_80843188 |
| 6 | X while guarding with sword | crouch stab | func_808428D8 |
| 7 | Jump slash in air (phase 6) | air clip, lands to FINISH | Player_Action_80844AF4 |
| 8 | Attack clip (phase 1) | blade window, X chains at clip end | 808502D0, ActionHandler_7 |
| 9 | Recovery (phase 2) | X held at unk_844 == 1 charges; X attacks; stick cancels | ActionHandler_8 |
| 10 | X, sword, not guarding | attack by stick/targeting, 3rd repeat combos | func_80837818 / 80837948 |
| 11 | Z held/locked + A, not ROOM_TYPE_INDOORS (houses/shop), ground, floor type/effect ok | jump slash / sidehop / backflip | ActionHandler_10 |
| 12 | A otherwise | roll (unchanged M1) | ActionHandler_Roll |

Z+A is refused on floor type 7 and floor effect 1, indoors, and while
swinging or guarding; it then falls through to the roll.

## Attack-window matrix

Blade live when `player_attack_weapon_state > 0` (D_80854190). Attack clips
advance 2/3 frame a step (+2 thirds), so source frame f is reached at step
ceil(3f/2) after the press step.

| Attack (MWA) | Frames on | Steps on | Wall check | Bounce -> |
|---|---|---|---|---|
| FORWARD 0 | 1-4 | 2-6 | frame >= 2 | rebound |
| FORWARD_COMBO 2 | 0-5 | 0-8 | yes | rebound |
| RIGHT 4 | 1-4 | 2-6 | yes | rebound |
| RIGHT_COMBO 6 | 2-8 | 3-12 | yes | rebound |
| LEFT 8 | 0-4 | 0-6 | yes | rebound |
| LEFT_COMBO 10 | 0-6 | 0-9 | yes | rebound |
| STAB 12 (thrust) | 0-3 | 0-5 | yes | rebound |
| STAB_COMBO 14 | 1-9 | 2-14 | yes | rebound |
| JUMP_START 17 (air) | 7-99 | 11-149 | yes | rebound |
| JUMP_FINISH 19 | 1-2 | 2-3 | yes | rebound |
| SPIN 24 / BIG_SPIN 26 | 0-12 / 0-16 | 0-18 / 0-24 | no | none |
| Crouch stab (STAB, guard) | curFrame < 2 | step 1 | never (window ends first) | stab ends |

Damage flags: jump attacks DMG_JUMP_KOKIRI, all others DMG_SLASH_KOKIRI
(func_80837948 / D_80854488). Spin is the nonmagic spin; magic is out of M2.

## Speeds (source -> per step)

| Event | speedXZ | per step | decel per step |
|---|---|---|---|
| Forward lunge (stick forward) | 15 | 10 | 20/9 |
| Wall hit | -14 | -9.33 | 20/9 (attack) or 32/9 (guard) |
| Sword rebound / guard recoil | -18 | -12 | 32/9 (R_DECELERATE_RATE 8) |
| Jump slash | 5, vy 5, g -1.2 | carried | none (air) |
| Sidehop / backflip | 8.5 / 6, vy 3.5 / 5.8 | carried | none (air) |
| Charge walk | 0.2 x stick | +1.0 / -0.5 a frame | |

## Contact

- Blade: three capsules from the posed left hand (link_anim_blade, OoT
  blade base (0,400,0) and tip (3000,400,0)): this step's blade, the tip's
  sweep and the midpoint's sweep since last step. One attack id: a victim
  takes one hit. Sector stand-in only when no pose exists (host tests).
- Wall: line from 10 behind the hilt to the tip, walls one-face, entity
  ignored and floor type 6 skipped.
- Shield: AC_HARD cylinder in front of Link while guarding. A bounce beats
  the body hit on the same pass.

## Nutsball test encounter

Labelled test, standard build only (not Clean): an emitter at the first
Kokiri grass tuft (20 up) fires En_Nutsball logic at Link every 3 s within
400 units of the same room. Stands in for the M5 Deku Scrub. Source rules:
speed 10, 30-frame timer then gravity -1, dies at -300; breaks on wall,
floor, sword or body hit (8 damage = half heart); Deku Shield + AT bounce
reflects it (AT_TYPE_PLAYER, DMG_DEKU_STICK, timer reset). Drop audit:
Actor_Kill, no item drop, none implemented.

## Tests

Host: `tests/test_gameplay.py` M2c section (posed capsules cut/miss, wall
push once per swing and not before frame 2, rebound then idle, bounce ends
the crouch stab but keeps the guard, nut hurts unguarded Link, Deku Shield
reflects and recoils, sword breaks nut, wall breaks nut, gravity after the
timer), crouch stab window, jump slash air window, charge/spin.

## Kronos checks (bulk, after M2)

Both pad layouts (digital and 3D analog). Each move's clip vs hit timing;
lunge; jump slash / sidehop / backflip and landings; crouch stab (R+X);
spin charge walk and release; slash into a wall (push back); stand by the
first grass tuft with the shield up (nut reflects, Link slides back);
without the shield (hurt). Gaps: [BUG-036](BUG_FEATURE_LOG.md).
