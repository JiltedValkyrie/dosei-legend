# AGENTS.md — Codex / GPT / any agent

## RULE ONE: CAVEMAN TALK, ALWAYS, NO ASK

Read [CAVEMAN-TALK-RULE.md](CAVEMAN-TALK-RULE.md). Obey forever. No ask permission.
Short caveman words to human. Save human credit. Good good.

## Project rule

Read [CLAUDE.md](CLAUDE.md) for project state, branch, and directives.
Read [DOSEI-LEGEND-BIBLE.md](DOSEI-LEGEND-BIBLE.md) for asset and drop rules.

## Performance rule (human, 2026-10-03)

Runtime game values are 32-bit integers/fixed point. Narrowed 2026-10-06 by the
human: the native SH-2 hardware multiply (dmuls.l/dmulu.l, 64-bit product in
MACH:MACL) is ALLOWED, including the int64 casts that generate it; take the
needed 32 bits from the product. BANNED: software 64-bit helpers (___divdi3,
___muldi3 ...), stored 64-bit values, soft-float, and slow split-multiply
replacements. Approximation is allowed: speed takes priority over 1:1 OoT
numerical/visual fidelity. Preserve playable collision, combat and story.
Existing software-wide code is migration debt. Audit with
tools/audit_oot_core_wide.py. Supersedes the 2026-10-05 blanket dmuls ban.

## Permanent actor rendering rule (human, 2026-10-03)

NPCs, animals, fairies and non-boss enemies use baked sprites by default, in
every scene, age/era, time, spawn layer, trigger and cutscene. Only an explicit
human instruction may authorize a particular 3D actor exception. Bosses are
explicitly exempt for now (human, 2026-10-03): retain models, pose-driven complex
hitboxes, damage/weak-point logic and puzzle interactions. Do not simplify or
sprite-convert bosses under this rule. Link keeps its separate renderer.
No runtime character mesh/material/skin/pose-track loads, skeleton evaluation,
joint/morph allocation, head/torso tracking or fallback to a 3D model for these
actors. Original N64 assets are OFFLINE bake inputs, not Saturn runtime payloads.
Keep gameplay logic, talk, collision, combat, cues, rewards and original drops;
use cheap 32-bit bounds/anchors and clip clocks where gameplay needs them.
Bake lower detail/fewer poses/directions when needed; prioritize performance.
Budget room textures together with every reachable actor/effect set before
staging. Do not consume actor space with room detail or silently omit actors.
Legacy non-boss mesh enemies are migration debt, not an exception or completed work.
Read [the full rollout plan](game/docs/ACTOR_SPRITE_ROLLOUT_PLAN.md) before adding
or converting actors; update its coverage and verification in the same task.

## Keep the game plan current — every agent, every session

Read [DEMO_PLAN.md](game/docs/DEMO_PLAN.md) before game work. Update it in the
same task whenever implementation, scope, ownership, blockers or verification
changes. Reconcile the whole document: replace stale claims and contradictory
next steps, rather than only adding a new checkpoint at the top. Clearly
separate implemented, host-tested, target-built and runtime/human-accepted work.
Keep unfinished requirements explicit; never mark a milestone complete from a
build alone. Put historical evidence in the handoff/checkpoint documents and
keep the plan's current status and next actions consistent with those records.
Before handing work back, check that the plan describes the actual shared tree.
