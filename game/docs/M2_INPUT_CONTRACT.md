# M2a input checkpoint — 2026-09-26

Status: input foundation implemented, broader M2a still in progress. Source
tables, allocator profiling and actor identity now have their own checkpoint in
[M2_SOURCE_CONTRACT.md](M2_SOURCE_CONTRACT.md). Human
authorized continuation after water runtime acceptance. No new sword moves,
enemies, inventory fields or save format are introduced at this checkpoint.

## Ownership and timing

- VBlank samples physical X press, hold and release. The mapper consumes edges
  once; title/dialogue input does not leak into play. Raw hold remains visible
  so cancellation can require a physical release before rearming.
- `combat_input.h` retains edges between rendered frames and 30 Hz simulation
  steps. Catch-up steps consume each edge once; a tap between steps preserves
  both press and release. Same-kind edges coalesce, as with `input_edge`.
- Scene changes, menus, dialogue, cutscenes and look mode cancel queued combat.
  A cancelled hold must release before a new attack can begin. This is an input
  latch, not a combo buffer or charge timer.
- Step-up, jump-start, hang, pull-up, ladder/vine climb, crawl, push, bonk and
  slope-slide own their pose. They reject land attack/guard starts. Swimming
  routes X to stroke and rejects land attack/guard. Existing ordinary land/air
  sword behavior is retained; release/hold are available for later M2 attacks.
- `demo_update` remains the simulation owner. Combat must not add a second
  movement integrator or independently advance animation time.

## Next source and budget work

Trace `z_player.c`'s `D_80854190`, `Player_UpperAction_Sword`,
`func_8084285C` and charge/release actions before defining attack windows.
The final two row fields must not be guessed to be active-frame endpoints.
`Player_CanSpinAttack` detects stick rotation; it is not the charged-X timer.
Use TRAVERSAL_TIMING.md for 20-to-30 Hz conversion, including animation cadence.

Measure live heap high-water before actor/contact/animation expansion. Current
arena is 51,200 bytes; free space below SGL is not free heap. The pre-checkpoint
Clean gap was 16,592 bytes. No arena reduction is authorized by this document.
Keep all menu rendering on VDP2. Audit cart, audio and VDP1 budgets with the
actual assets before M2 enemy integration.

Stick rewards require explicit persistent inventory and a versioned save
migration/rejection decision when introduced; do not enlarge v2 silently or
reuse unrelated fields. Karebaba rewards must follow its source item grant.
Shield/contact precedence, attack identity, multi-victim contact handling,
damage/death and charge cancellation are still M2 work, not supplied here.
