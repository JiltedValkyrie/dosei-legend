# Next step: forest gameplay

Opus, human want this next. Good good.

This file be plan. Work below still need gameplay proof.

## Latest human ask: usable gear and fairy dialogue

This section come first. Older work order below now history where work landed.
Current branch already `gameplay-baseline`. Keep branch. Keep dirty work safe.
Next work order: fairy dialogue first. NPC bodies parked. Gear art follows
source/importer check and measured budget; no promise all variants fit yet.

### What exist now

- Human report: real OoT sword/shield icons visible through VDP1 sprite path.
  Sword at (-537, 28, 194). Shield at (35, 28, -418).
- Walk within 44 units collects and auto-equips. HUD `sw1 sh1` shows gear state.
  No manual equip menu needed for this baseline.
- Local `game/src/gameplay.c/.h` already hold owned/equipped bits, targeting,
  swing timing, shield state, and grass-cut rules. Extend these. No second system.
- Human report: Link gear geometry always drawn. Equipped bits alone no make
  proper visible combat. Current swing timing says approximate in source.
- Human report: 242 tests pass, 1 skip; both images rebuilt. Me no rerun here.
  Last reported spare RAM 3,312 B, VDP1 VRAM 6,944 B. Check budget as assets grow.
  Dialogue still needs text/font/box budget. Reuse existing font where possible.

### After dialogue: make equipped gear usable and visible

1. Keep pickup auto-equip. Owned and equipped state drive both actions and art.
   Before pickup, no sword swing or shield guard. Sword and shield work alone too.
2. Trace real OoT player draw and equipment display-list selection. Opus's
   limb-19 SHEATH lead came only from `PLAYER_LIMB_SHEATH = 0x14` minus one.
   Draw code not checked for that claim. Lead only, no established design.
   Opus reports OoT swaps display lists for hand/back gear states. Verify exact
   lists and importer support. Whole-limb hiding cannot put sword in hand.
   Sheath and shield sharing one limb also unverified. Check separability,
   preserve per-vertex matrix ownership, and measure added RAM/VRAM before
   committing to variant scope. No assume variants fit current spare budget.
3. Support empty hands, gear on back, sword in hand during attack, shield in
   hand during guard. No duplicate sword/shield on back and hand. Use real gear
   geometry and source-backed hand/sheath variants.
4. X starts sword action with equipped sword. Play draw/attack/recovery poses;
   return to valid idle/move pose. R held raises equipped shield; release lowers.
   Keep L targeting compatible with both. Physical Z still look mode.
5. Read actual N64 attack and guard code. Record source functions and animation
   names. Match active blade window to animation; cut grass only during that
   window. Keep sword sweep, visual pose, and sound event on same fixed timeline.
6. Play sword/guard effects and Link action voice once per matching event.
   Check shield and attack overlap against source. No stuck pose after release.

Player path: find icon -> walk over icon -> gear auto-equips -> X swing,
R guard, L target. Add short on-screen pickup hint so human know controls.

### First: talk to fairy now

Human want dialogue. Fairy can be talk partner while NPC body missing or hidden.
NPC model work must not block talk.

1. Give each placed NPC fairy stable speaker/owner ID and dialogue entry.
   Use owner position for interaction, not fairy bob height. Ambient fairies
   need no invented NPC identity.
2. Near fairy, show `A: Talk`. Prefer current valid targeted fairy; otherwise
   choose nearest valid fairy in front. Check distance and walls. No talk through
   hut. Keep chosen speaker stable once conversation starts.
3. A opens readable text box with speaker name. For NPC proxy fairy, identify
   its owner. Use local OoT message IDs/text where available; label any new
   tutorial lines as authored in source notes. Adapt button hints to Saturn.
   Extractable speaker text in local decomp still unconfirmed. Check first;
   if absent, use short authored lines and report them as authored dialogue.
   Working dialogue no mean original N64 wording verified.
4. Ship actual short conversations for placed speakers. Include useful sword,
   shield, targeting, and grass practice hints. No empty box or debug counter.
5. A advances pages; A on final page closes. B closes early. Consume each press
   once. Opening press must not also skip first page. Holding A must not skip all.
6. While box open, route input to dialogue. Stop movement, attack, jump, and
   guard actions; B must not toggle walk/run. Keep music and world rendering.
   Close cleanly; no leftover button edge causes swing, jump, or instant reopen.
7. Draw box in clean player image too. Keep text inside screen; wrap lines and
   bound page/text buffers. Small text sounds okay; no spoken dialogue required.
8. Later NPC body shares same speaker and dialogue state. Fairy talk still works
   when body culled. No duplicate conversation from fairy plus body.

### Focused proof for this next step

Dialogue checks come first. Gear checks below apply when gear-art work lands;
unfinished gear art must not block delivery of fairy talk.

- Start empty. Collect sword only, shield only, then both. Check visible gear
  and allowed actions match equipped bits. Collected icons stay gone.
- Swing while free and targeted. Guard while targeted. Watch hands/back,
  blade timing, grass cut, sound and recovery. Friendly speakers take no damage.
- Talk to two different fairies. Check correct speaker, all pages, A advance,
  B close, held buttons, movement lock, and control return. Test hidden NPC body.
- Test relevant state/input rules, build standard and clean images, then short
  in-game check. Report actual visual/audio proof separate from host tests.

Only plan updated here. Combat art and dialogue not implemented by this note.

## First: new branch

- Check current branch, commit, and dirty files. Keep human work safe.
- Make new branch from current HEAD. Name suggestion: `gameplay-baseline`.
- Do gameplay work there. Active game live in `game/`.
- Read `CLAUDE.md`, `DOSEI-LEGEND-BIBLE.md`, and current controls in
  [OPUS_HANDOFF.md](OPUS_HANDOFF.md). Keep working movement, camera, music.

## Put Kokiri people in forest

- Populate level with other NPCs. Existing fairies show where people belong.
- Match fairy spots with real N64 actor placement data. Check identity, facing,
  and ground height. No guessing random spots.
- Show NPC bodies only when Link close. Hide bodies when far.
- Human allow pop-in. Dither fade okay. Keep near/far change stable.
- Keep fairy and owner together. Hidden body must keep its gameplay state.

## Give Link inventory and gear

- Make small baseline inventory: owned items, equipped sword, equipped shield.
- Put findable sword and shield in level. Both reachable by Link.
- On pickup, add item once. Auto-equip right away. Remove collected pickup.
- Show gear on Link. Give clear pickup feedback. No duplicate pickup each frame.
- Keep ownership through NPC hiding and room changes during play.

## Let human practice combat

- Use local real OoT code as reference:
  `D:/Workspace-Claude/game-decomps/n64/oot`.
- Trace player, targeting, camera, equipment, and grass behavior before porting.
  Record source files/functions used. No claim N64 parity from guesswork.
- L does N64 Z-target/recenter. Physical Saturn Z still be look mode.
- Add target acquire, hold/release, facing, and camera behavior for practice.
  Use proper target rules. No sword damage to friendly Kokiri.
- X swings equipped sword. R uses equipped shield. No gear means no gear action.
- Use real attack animation timing and active hit window. Prevent held-button
  spam and repeated hits from same swing unless source behavior needs them.
- Keep A interact, Y jump, B walk/run, C+D-pad items, Z+D-pad look.
- L+R must allow targeting plus shield together.

## Sound and cuttable grass

- Play action sound effects and Link voice with matching actions.
- Trigger sounds on action/animation events. No replay every rendered frame.
- Keep current music working. Use existing audio path and available assets.
- Add grass in forest. Use N64 placement/behavior where source gives it.
- Sword active hit window cuts nearby grass. Cut once, show cut result,
  play cut sound. No cutting by walking or by idle sword alone.

## Work order and proof

1. New branch. Check existing actor, input, asset, and audio hooks.
2. NPC placement and near-distance visibility.
3. Inventory, sword/shield pickups, auto-equip, visible gear.
4. Targeting, sword, shield, action sounds and Link voice.
5. Grass placement and sword cutting.
6. Build. Run focused checks. Short in-game practice pass.

Use integer/fixed-point math on Saturn. Keep asset and memory guards.
No broad renderer rewrite for this work. Existing render bugs stay recorded.

Proof: approach NPC, walk away, approach again. Find both items. See both equip.
Target, swing, shield, release target. Hear actions. Cut grass with sword.
Check movement and camera still work. Check pickups stay collected.

Update [VSLICEPROGRESS.md](../../VSLICEPROGRESS.md) and
[OPUS_HANDOFF.md](OPUS_HANDOFF.md) when work lands. Say what built, what tested
in game, what still missing. Build alone no prove gameplay good.
