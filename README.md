# Dosei Legend — Kokiri Forest / Saturn Vertical Slice

Porting the Kokiri Forest scene from Ocarina of Time (N64) to Sega Saturn (libyaul),
as a vertical slice: one room, one character, real toolchain, real framerate numbers.

**Shared environment/toolchain/emulator setup, build fixes, and gotchas now
live in [`../README.md`](../README.md)** (the `saturn-homebrew` parent
folder) — that doc covers MSYS2, WSL, the SH2 cross-toolchain, libyaul, and
Kronos, since those are reused across every project in that folder, not just
this one. This file covers only what's specific to the Kokiri Forest port.

## Division of labor

- **Claude**: fixed-point math core, libyaul render/room code, host-side asset
  converter, build setup.
- **User**: profiles on real hardware (ODE), supplies the OoT ROM and Saturn
  BIOS, reports results back.

Claude has direct shell access into this machine (Windows, WSL, MSYS2) and
drives builds/emulator runs directly — see the parent README for how. Real
hardware (the ODE) is still user-only.

## Decisions locked in (2026-09-14)

- **4 MB expansion cart: yes.** Simplifies the room/asset loader for the slice.
  Base-hardware compatibility is a later concern.

## Step sequence (each gates the next)

1. ✅ **Toolchain closes.** DONE 2026-09-14 — SH2 cross-toolchain, libyaul,
   and Kronos all built from source; `vdp1-zoom-sprite` example renders
   correctly in Kronos with a real BIOS. See parent README for the full
   build/fix history. Real hardware (ODE) still unconfirmed.
2. **Fixed-point core**, isolated, no rendering: adapt libyaul's existing
   `gamemath` fix16 library (already ships `fix16_mat43` — rotation +
   translation, same shape as OoT's `MtxF`) to OoT's Vec3f/MtxF conventions,
   validate matrix concat + perspective transform against known N64 output.
3. **Model renderer** — one Link mesh as quads, SH-2 transform, per-poly sort,
   VDP1 draw. Make-or-break step for framerate.
4. **Room renderer** — Kokiri Forest geometry, quad conversion, sort against
   the model, VDP2 for ground/sky.
5. **Asset converter** (in parallel now that the decomp builds) — host-side
   tool, decomp extraction → Saturn quad meshes + palettized VDP1 textures.

## OoT decomp

Location: `D:\Workspace-Claude\game-decomps\n64\oot` (real
[zeldaret/oot](https://github.com/zeldaret/oot); was `main` branch as of
2026-09-14). Runs under WSL1, invoked from `/mnt/d/...` — see the parent
README's "Environment / shell notes" for the WSL DNS/sudo fixes that were
needed to get apt working there.

**Kokiri Forest scene identifier: `spot04`.** Confirmed via
`include/tables/scene_table.h`: `DEFINE_SCENE(spot04_scene, g_pn_31,
SCENE_KOKIRI_FOREST, SDC_KOKIRI_FOREST, 0, 0)`. Scene assets described at
`assets/xml/scenes/overworld/spot04.xml`.

**Baserom:** user supplied "Legend of Zelda, The - Ocarina of Time (USA)
(Rev A)" as a byte-swapped (v64) `.n64`. Despite the filename/folder it was
dropped in, it's actually **ntsc-1.1**, not ntsc-1.0 — confirmed by
byte-swapping to native z64 order (`dd conv=swab`) and matching md5
`721fdcc6f5f34be55c43a807f2a16af4` against
`baseroms/ntsc-1.1/checksum-US-compressed.md5`. Written to
`baseroms/ntsc-1.1/baserom.z64`.

**Build status: ✅ working end-to-end (2026-09-14).**
`make setup VERSION=ntsc-1.1` then `make VERSION=ntsc-1.1` — rebuilt ROM
checksum matches the original exactly (`build/ntsc-1.1/oot-ntsc-1.1.z64: OK`).
Two build issues were hit and fixed, both from the checkout sitting on the
Windows filesystem under WSL1 (the exact risk the decomp's own README warns
about):
- CRLF line endings broke `tools/preprocess.sh` and `tools/fado/find_program.sh`
  (Windows git `core.autocrlf` converting LF→CRLF on checkout). Fixed by
  renormalizing in place: `git config core.autocrlf input` (repo-local, not
  global) + `rm -f .git/index && git checkout -f HEAD`. If similar
  `$'\r': command not found` errors show up on some *other* script later,
  it's the same root cause.
- The `fado` tool (generates overlay relocation data — turned out **not**
  optional despite an initial "ignored" build failure) needed a manual
  `cd tools/fado && make` after the line-ending fix, since `make setup`
  doesn't retry tools that failed once.

Extracted Kokiri Forest scene data lives at
`extracted/ntsc-1.1/assets/scenes/overworld/spot04/` — this is what the
Saturn-side asset converter (step 5) will read from.

## Status (2026-09-14)

**Step 1 closed.** Chain verified end-to-end: SH2 cross-compiler (built from
source) → libyaul → example project → bootable ISO → Kronos (also built
from source) + real BIOS → rendering, confirmed visually. Full build/fix
history is in the parent README, not duplicated here.

**Step 0 (decomp) also done** — see above.

## Next up

1. **Same ISO on real hardware** via the ODE — the other half of the
   original step 1 gate. Emulator agreement ≠ hardware agreement.
2. **Step 2: fixed-point core**, per the step sequence above.
3. Then step 3 (model renderer) — the make-or-break framerate step.
