# Build guide and gotchas

The authoritative build path is **Linux** (WSL Debian 12 on this machine).
Do not use MSYS2 or Git Bash for builds.

## Build commands

From Windows (PowerShell):

```powershell
wsl.exe -e bash -c "cd /mnt/d/Workspace-Claude/saturn-homebrew/oot-sat/game && ./build.sh --clean"
```

Variants (pass to `build.sh`):

| Args | Output | Use |
|---|---|---|
| `--clean` | `build/game-clean.cue/.iso` | normal player build (default choice) |
| *(none)* | `build/game.cue/.iso` | developer build with debug HUD |
| `--hires` | `build/game-hires.cue/.iso` | 320x480i, on request only |
| `OOT_CORE=1` | adds oot-core decomp slice + SH-2 bench (debug rows 13-14) | oot-core work |

Log a long build to a file and check the tail:
`./build.sh OOT_CORE=1 > build/oot-core/build_log.txt 2>&1; echo EXIT=$?`

## One-time Linux setup

```bash
sudo apt-get install -y python3-pil genisoimage   # Pillow + mkisofs
```

- Python: system `python3` (3.11). Override with `DOSEI_PYTHON`.
- Compiler: **sh-elf gcc 9.3.0 + binutils 2.34**, the same versions and configure as
  Jo's Windows compiler. Build it once (about 30-60 min, needs internet):
  `tools/toolchain/build-sh-elf-linux.sh` installs to `../sh-elf-9.3-linux`
  (override with `SH_ELF_LINUX`). `build.sh` refuses to run without it and passes
  `CC`/`CONV` to make. Do NOT use Jo's `Compiler/LINUX` gcc 8.2 (gotcha 15). The
  C++ front end is included, so it also compiles oot-core.
- Paths come from `config.ini` (else `config.example.ini`). The decomp falls back to
  `../../game-decomps/n64/oot`. `build.sh` exports it as `DOSEI_OOT` for the tools.

## External inputs not in git

| Input | Location | How to get it |
|---|---|---|
| OoT decomp, extracted ntsc-1.2 | `D:/Workspace-Claude/game-decomps/n64/oot` | zeldaret/oot, `make setup VERSION=ntsc-1.2` |
| Extracted audio | `shared/build/audio-source/` (32 MB) | copied from `dosei-legend/shared/build/audio-source` |
| Jo Engine SDK | `../joengine` | sibling checkout |
| sh2eb-elf (Windows only, optional) | `../sh2eb-elf` | only for host-side oot-core checks on Windows |

## Gotchas (each one cost a failed build)

1. **MSYS2 / Git Bash picks the wrong compiler.** From Git Bash, MSYS2 `make`
   ignored command-line overrides and `OS`, chose `Compiler/LINUX`, and failed
   with `Exec format error`. Fix: build on Linux. (Windows path still exists in
   `build.sh` but is not maintained for agents.)
2. **Hardcoded `D:/...` paths in Python tools.** On Linux `Path('D:/...')` is a
   relative path and the lookups find nothing (`StopIteration`). Tools now read
   `os.environ['DOSEI_OOT']` first. New tools: never hardcode a drive path. Take
   `--oot` or use `DOSEI_OOT`.
3. **`project_config.py --prepare` needs MSYS2.** It is now skipped when not on
   Windows (`os.name != 'nt'`).
4. **`cygpath` does not exist on Linux.** `build.sh` defines a no-op shim when on Linux.
5. **makefile `SHELL := C:/msys64/...`.** Now conditional: `/bin/bash` on Linux.
6. **Missing extracted audio** -> `build_cdda.py` `FileNotFoundError ...Soundfont_3.xml`.
   Copy `shared/build/audio-source/` (see table above).
7. **Whole-Field polygon check.** `build_hybrid_scene.convert()` failed with
   `2709 polygons exceed the 2600-polygon table budget`, but the Field streams.
   `build_field_chunks` passes `streamed=True`, and its own per-position sweep
   enforces the budget (worst resident 721 polys). Do not remove the sweep check.
8. **Two toolchains differ.** Linux gcc is 8.2; Windows is 9.3.
   `__builtin_is_constant_evaluated` is GCC 9+. `fx.h` uses `FX_RUNTIME()` with a
   `__builtin_constant_p` fallback. Code size can differ, so watch the
   work-RAM boundary check (`build_sgl_area.py --verify`).
9. **Jo's startup never runs `.ctors`.** Superseded 2026-10-02 (gotcha 20): the
   oot-core blob runs its own ctor table via `OotCoreEntry.init`, so the makefile no
   longer rejects ctors. Still keep all `Fx` operators `constexpr` (fewer ctors).
10. **`#include` placement in `main.c`.** `texture_probe.h` sits inside
    `#ifdef DOSEI_TEXTURE_PROBE`. Do not add unrelated includes after it.
11. **PowerShell to WSL quoting.** Escape `$` as `\$` inside
    `wsl.exe -e bash -c "..."`. `$?` printed as `True` when left unescaped.
12. **Python patching via heredoc mangles backslashes/quotes.** For edits containing
    `\\`, regex or nested quotes, write the patch script to a file first, or use
    the Edit tool.
13. **Text encoding.** Some docs contain non-ASCII text. On Windows Python, read
    with `encoding='utf-8'` (the cp932 default fails).
14. **Fixed RAM-cart carves are compile-time checked.** `size of array
    'link_mesh_fits_carve' is negative` = Link mesh (`LINK_POLYGON_COUNT` x 32 B)
    outgrew `RAM_CART_LINKMESH_BYTES` in `src/ram_cart.h`. Grow the carve and
    `RAM_CART_FIXED_BYTES` together (both checked in `ram_cart.c`). Or shrink
    Link first: 2026-10-02 the unused first-person arm (227 polys) was dropped from
    `build_link_model.py`, so Link is 704 polys and fits the 0x6400 carve again.
15. **Linux gcc 8.2 code is bigger -> work-RAM boundary fails.** `--clean` on Linux:
    `.bss ends at 0x6085914 ... free at least 6420 bytes` (the same tree fit with
    Windows gcc 9.3). `OOT_CORE=1` adds ~72 KB (sys_math3d alone 44 KB, now
    unlinked) -> 81 KB over. oot-core code must move to the RAM cart (Phase 1).
    Fix (human decision 2026-10-02): build gcc 9.3 for Linux (see setup above).
16. **`ld: cannot find -lc`.** The link needs newlib. The toolchain script builds
    newlib 3.3.0 (the same version as Jo's Windows toolchain) after gcc. A toolchain
    built with only gcc and binutils cannot link the game.
    **newlib options must match Windows** (taken from Jo's `newlib.h` and its
    archive members): nano formatted IO, `--disable-newlib-io-float`, nano malloc,
    lite exit, `-Os`. A default newlib adds ~37 KB (work RAM 26.7 KB over). Nano
    with float IO fails with `undefined reference to _printf_float`. Proof
    method: relink against Jo's Windows `sh-elf/lib/libc.a` (archives do not
    depend on the host). The Linux gcc 9.3 object for `kokiri_sgl.c` is
    byte-identical to the Windows one.
17. **Use the draw-cap-fixed Kronos, never the stock build.** Stock Kronos 2.7 stops
    after 2048 VDP1 commands per frame without setting EDSR.CEF, so SGL `slSynch`
    deadlocks: the game freezes, Kronos shows VDP1 00 FPS with VDP2 still 60, and the
    watchdog reads `HANG P9 E1`. The nightmare reliably hits it at frame 450. Real
    hardware has no such cap. `tools/build_kronos_draw_fix.py` builds the patched
    emulator; the existing one is `dosei-legend/game/build/kronos-draw-fix/kronos.exe`.
    `config.ini` (local, gitignored) must point `kronos` at it. Without
    `config.ini`, `config.example.ini` falls back to the stock build. That is how the
    fork regressed (2026-10-02).
18. **WSL git cannot read this checkout.** It is a git worktree whose `.git` file
    holds a Windows path (`D:/.../dosei-legend/.git/worktrees/...`). Run git from
    Windows. Scripts that need the revision take it from an environment variable,
    e.g. `OOT_SAT_REV` in `tools/package_playtest.sh`.
19. **The emulator is human-run only.**
20. **GCC 9 static ctor for Fx tables.** A non-constexpr file-scope table whose initializer
    divides Fx (z_actor `sAttentionRanges`) is not constant-folded: `__builtin_is_constant_evaluated`
    is false there, the DIVU path is volatile, so GCC emits `_GLOBAL__sub_I_*`. The same
    expression in a `constexpr` variable folds. Fix: the blob keeps `.init_array`/`.ctors`
    (oot-core.ld) and `OotCoreEntry.init` runs them; main.c calls it right after load. Find the
    culprit with `sh-elf-g++ ... -S -o - | grep -A400 _GLOBAL__sub_I`.
21. **oot-core link passes with 0 undefined = nothing linked.** `--gc-sections` drops all decomp
    code no entry reaches. `oot-core/src/oot_core_roots.cpp` keeps the systems alive.
22. **oot-core -O2 is 2x the size of -Os** (Fx int64 ops inline): 425 KB vs 203 KB. Blob uses -Os.
23. **Git Bash `sed`/heredoc `\n` in replacement writes a literal `\n`** into the makefile (broke
    OOT_CORE_SRCS). Use the Edit tool or a Python script file for multi-line makefile edits.
24. **Decomp `libc/string.h` declares memcpy with C++ linkage**, but GCC emits calls to the C
    symbol for struct copies. `bridge_libc.cpp` includes no decomp headers and defines the C ones.
25. **Add decomp files in `tools/oot_core_import.py` SOURCES only.** It writes
    `build/oot-core/sources.mk`; the makefile includes it. Object names use the basename, so two
    sources with the same file name would collide.
26. **Kronos cannot run code above 0x020FFFFF in the cart area.** Its SH-2 fetch table maps
    only 0x020xxxxx to CS0; the oot-core blob at 0x027C0000 fetched 0xFFFF and hung after the
    SEGA logo (boot marker `oc 2 bench 1`, 2026-10-02). Real hardware has no limit.
    `tools/build_kronos_draw_fix.py` now also patches `sh2int.c` (0x020-0x027 -> CS0 cache).
    Built to `build/kronos-fix/` on top of the old draw-fix `libkronos.a` (`--archive`), DLLs,
    `platforms/` and `kronos.ini` copied from it; `config.ini` points there.
27. **`sources.mk` list ends in `\`.** Anything the importer appends after it must start with a
    blank line, or make glues it onto the list (`No rule to make target 'OOT_SCENECOL_NAMES'`).
28. **Scene collision blobs include the scene header by bare name.** The importer rewrites
    `#include "spot04_scene.h"` to the asset-root path; new scenes get the same rewrite.
29. **PlayState is 78 KB with Fx** (floats doubled). It lives in low work RAM
    (`RAM_LOW_OOTPLAY`), never in the blob .bss or the 256 KB blob carve.
30. **All-scenes registration needs `tools/build_all_scenes.py` run first (about 1-2 h).**
    It bakes every decomp scene's rooms into `build/all-scenes/` (ignored). Then
    `build_scene_table.py` registers each scene that fits the runtime caps
    (`RUNTIME_CAPS`), caching the verdicts in `build/all-scenes/registered.json`
    (delete it to recheck). Without the bake only the 11 slice scenes exist. Run from
    `game/tools` with `DOSEI_OOT` set and `--rom-dir <oot>/baseroms/ntsc-1.2`.
31. **Scene ids >= 36 use `Z<two base-36 digits>` file names** (`asset_scene_name`,
    tools/asset_names.py `scene_stem`). Spawns and doors are in `SCENETAB.BIN`, not
    work RAM: 75 scenes put 10 KB of tables over the static RAM limit. build.sh copies
    `Z*R*.MSH/.TEX` banks too; a new name pattern must be added to that copy loop
    (missed once: `Z20R3.MSH: File not found`).
32. **`--quick` skips every asset step** (`./build.sh --quick OOT_CORE=1`, or
    `--clean --quick`). Only for C/C++/oot-core changes after one full build of that
    variant; tool, asset or scene-table changes need a full build.
33. **Decomp scene blobs are `<scene>.OOC`** (S1.OOC, Z20.OOC: asset_scene_name), one per
    registered scene, written by oot_core_import.py from build/generated/scene_table.json
    (so the full build must have run first). A blob over its 256 KB carve or failing to
    compile is left out with a "scene blob ... left out" line; the runtime skips it.
    The runtime checks GFS_NameToId before opening: jo_fs treats a missing file as fatal.
34. **Blob-only rebuild:** `./build.sh --quick OOT_CORE=1 -k build/oot-core/oot-core.elf`
    (make target after the args) runs the importer and links only OOTCORE. Add
    `OOT_CORE_MAX_BYTES=0x100000` to see the real size when it outgrows the carve.
    From PowerShell, `\$?` in `wsl.exe -e bash -c "..."` still expands to True: run a
    script file with `wsl.exe -e bash /mnt/...sh` instead.
35. **Cart carves moved 2026-10-02 (route steps 3-4):** RAM_CART_MSGDATA (ROM text,
    0x38400) + SCENECOL 0x40000 + OOTCORE 0x70000; blob now at 0x02790000, scene blob at
    0x02750000 (makefile OOT_CORE_LOAD_ADDR / OOT_SCENECOL_ADDR, ram_cart.h, checked in
    ram_cart.c). Change all three together. Bank-2 jo heap shrank to 598 KB.
36. **Decomp objects are data blobs `O<id hex>.OOB`** (importer OBJECTS) linked at
    0x06000000 (oot-core/object.ld). Their symbols reach OOTCORE through
    build/oot-core/obj_syms.ld (nm of each object elf); messages through msg_syms.ld.
    Both files are link inputs: a stale one gives wrong addresses, not link errors.
    Object .cpp keep the object header; placeholders (DLs, textures) live in a second
    unit without it, or `u64 x[1]` clashes with the header's array size.
37. **Python heredocs from Git Bash** break on `'` inside the script and turn `\\` +
    newline into a joined line (makefile recipes still work, but read badly). Write patch
    scripts with the Write tool into the scratchpad and run them (gotcha 12 again).

38. **Removing an oot-core source did not relink OOTCORE** (stale elf, old size): the
    elf now depends on build/oot-core/sources.mk. Same trap for any generated list.
39. **Phase 2 meshes:** tools/build_core_meshes.py runs after the importer (needs the
    ROM). Keep placeholder indices are positions in KEEP_PLACEHOLDERS: append only, or
    every K<idx>.MSH name shifts. Stale K/Q*.MSH files in build/cd are harmless but
    count toward the disc directory.
40. **Blob size watch:** a single actor can cost 30-40 KB (Fx int64 code at -Os, e.g.
    En_Ishi). Check the per-object sizes in oot-core.map before importing in bulk.
41. **Carve move left stale scene blobs** (2026-10-03): moving OOT_SCENECOL_ADDR did not
    relink unchanged `S*.OOC`; Kokiri kept 0x0275xxxx pointers, collision read garbage and
    all decomp grass died in its floor snap. `build/oot-core/addr.stamp` now relinks every
    blob when an address changes; the host rejects a blob whose col_header is outside the
    carve. Check: `xxd -l 4 build/cd/S1.OOC` starts with the OOT_SCENECOL_ADDR top half.
42. **Windows python wrote CRLF into build.sh** (`set: pipefail: invalid option name`).
    Edit .sh files with sed/Edit, or python `open(p, 'w', newline='')`; fix: `sed -i 's/
$//'`.
43. **SGL `sprHflip` is broken** (SL_DEF.H: `UseTexture << PDATA16`, undeclared). Use
    `(1 << 4) | sprNoflip` for a horizontally flipped sprite.

44. **Inspect the matching variant's binary.** After `--clean`, disassemble
    `build/game-clean.elf`, not `build/game.elf` (the latter can be a stale
    developer build). Despite the suffix, the main image is COFF SH:
    Windows sh2eb-elf tools need nm `--target=coff-sh`, objdump `-b coff-sh`;
    COFF C symbols have a leading underscore. OOTCORE is real ELF. Check the
    current build log's .bss boundary against the binary's `__bend` before
    attributing symbol/helper changes to a fix.

45. **Story banks must not reuse playable scene IDs.** Former opening IDs 2-4
    and emerald IDs 20/21/23/25/26/28 collided with all-scene registration; the
    final story emitters overwrote real dungeon/market room banks. Virtual banks
    now use IDs 1024+ and separate `C<base36>` names. Stage `C*R*.MSH/.TEX` and
    Navi `C0R*.MAP` along with ordinary S/Z banks. Full asset rebuild required;
    quick builds retain corrupted old banks. `build_room_scene` checks unique
    output paths and emitted headers after all emitters run. Runtime scene IDs
    need 16 bits, and story draw behavior requires explicit virtual predicates.
    During migration, remove only retired S2 rooms 0-9 MSH/TEX/MAP, S3 room 0
    MSH/TEX, and S4 rooms 0/2/3/4/5/6 MSH/TEX from generated and staged folders.
    Preserve their RGB backdrops and every real scene 20-28 bank. These stale
    files are unreachable but otherwise persist through the broad copy globs.

46. **Expanded saves consume static work RAM.** Save v11 pushed the combined
    world build 784 bytes beyond SGL's fixed base. Target save state now uses
    a bounded 4 KiB carve at low-RAM offset 0x27800 (retired directory space),
    initialized by `save_new_game()` before boot scene/actor setup. Save writes
    and file previews each also outgrew SGL's 1 KiB master stack: they now have
    separate 4 KiB carves at 0x28800 and 0x29800. Separate scratch supports a
    preview during a write without corrupting the write or live state. Host
    builds retain ordinary globals/locals. Low RAM is not boot-cleared; never
    remove initialization or reuse these carves. Guard tests poison surrounding
    RAM and exercise initialization, test gear, reset and overlapping save I/O.
    Keep heap sizes and the build's SGL boundary rejection unchanged.
    The final world link still exceeded the boundary by 80 B until oot-core
    draw-cache ownership moved into its own checked 4 KiB carve at 0x2A800.
    Clear it once before core boot, before any cleanup reads pointer slots.
    Final .bss end is 0x06083D70 (656 B spare); this small margin must not be
    treated as room for new static actor tables. Matched Clean disassembly
    shows 12 B save-summary and 72 B save-write frames after these changes.

## Playtest package

Mednafen development saves: disc rebuilds can change its save hash. The launcher
now preserves the newest active DOSEI backup under the variant's unhashed `.bkr`
name before launching, using the default `%M` lookup fallback. Never delete old
hashed backups to "fix" an empty file select. See `tools/launcher/mednafen-saves.ps1`.
The project-local `backup.o` now uses `src/backup_low.c`: low-RAM code/work areas
are reserved in `ram_low.h`; Sega STN-52 requires 8,312 work bytes, not 8,192.

Build Clean, then run `tools/package_playtest.sh` in WSL with `OOT_SAT_REV` set.
Output goes to `playtest/` (gitignored). The package holds the disc (cue, iso and CD
audio tracks), the draw-cap-fixed Kronos with local paths blanked and the 4 MB
cart preset, and `README.txt` (template: `tools/playtest_readme.txt`). It ships no
BIOS. Agents build; the human launches
    Kronos/Saroo.

## oot-core specifics

- Sprite keys must come from the freshly linked object symbols, not N64 ROM
  offsets. `build_npc_sprites.py` emits `generic_sprites.json`; the make rule
  resolves `generic_sprites.h` after `obj_syms.ld` and rebuilds the host consumer.
  Object compaction otherwise makes loaded NPCs invisible (Malon: ROM 0x820,
  previously linked 0xBD8). Current compact sprite objects keep frame counts only.
- Full builds refresh stale registered scene banks before staging. Cache keys
  include source bytes, converters and both Link ages' budget inputs; a lone
  Ranch rebake leaves every other room using obsolete alpha/material rules.
  Preserve unregistered preflight rows and explicit blocked destinations.
  Count 64 KiB actor reserve and 32 KiB spare in both density passes/final checks.
- `build_fairy.py` owns all 32x32 wing/glow cels. `build_recomp_assets.py` delegates
  to it; do not overwrite FAIRY.RGB with the old 16x16 helper. Runtime no longer
  consumes FAIRY.BIN. Character offline models remain in generated/cache folders;
  converted NPC/rider/owl BIN/ANM/TRK/SKN files must not be staged on the disc.
- Do not edit a shell build script while its process is running: Bash can read
  subsequent blocks at obsolete file offsets and report misleading syntax errors.
  Finish script edits before starting the build; restart from the saved script
  if this occurs. `bash -n build.sh` validates the file itself.
- Keep one WSL process active at a time in this workspace. A second launch has
  failed with `SessionLeader ... Failed to read ... EventFd 0` and terminated
  the existing bake. Poll its existing process session; do host checks on Windows.
  The interrupted `populated-scenes-bake.log` is not a completed target build.
- Pause now shares `PAUSEINV.BIN` with the HUD. Full builds must regenerate both
  `pause_inventory_data.h` and `gameplay_hud_data.h` before target compilation.
  The atlas lives in VDP2 B0 at 0x52000 and pause reads its backed-up copy. Source
  icons use 56,272 bytes, with no extra runtime heap or per-pause CD load. Heart
  banks at 0x50000/0x51000 and C-item banks at 0x4B000 remain disjoint.
- `build_adult_link.py` must precede scene budgeting. Both source ages share one
  live Link mesh/animation bank, 184 sprite slots and 13,856 bytes of reserved
  pixels/palettes. The offline combined-age upper bound is deliberately larger.
  Link points/matrices/alternate skin occupy checked low-RAM carves at
  0x17800/0x18C00/0x19800; actor-view scratch uses 0x19000. The first combined
  link exceeded SGL by 1,264 bytes. Keep the matrix reset and fill-before-read
  view ownership; low RAM is not boot-zeroed. Stage all five ADULT/ADLT files; they are Link assets,
  separate from forbidden NPC model/animation packages. No second resident age
  bank or heap/capacity reduction is needed. Age-load transactions fence VDP1
  before replacing live textures and preserve the old age on ordinary failure.
- Generated core includes need an explicit path (as other bridge files use).
  `bridge_message.cpp` includes `../../build/oot-core/ocarina_restrictions.inc`;
  the make dependency rebuilds it when restrictions change. Both z_bgcheck and
  bridge_player explicitly depend on the shared 32-bit bounds/extraction header.

- `tools/oot_core_import.py` regenerates `build/oot-core/decomp/` (run by `build.sh` when
  `OOT_CORE=1`). Report: `build/oot-core/import_report.txt`.
- Host math check (Windows mingw g++): `bash oot-core/tests/run_host_probe.sh`
  must report `0 over tolerance`.
- Host bgcheck check: `oot-core/tests/run_bgcheck_probe.sh` runs the real z_bgcheck on a
  scene blob (default S1 Kokiri), raycasts every En_Kusa spawn + a grid, Fx vs float.
  WSL g++ works (64-bit long); MinGW (`HOST_CXX=/c/msys64/mingw64/bin/g++ PY=python
  OOT=D:/...`) matches SH-2 32-bit long. Grid has small slope errors (<4 units), see plan.
- Target soft-float check: no `__addsf3/__mulsf3/__divsf3/__fix*/__float*`
  symbols in the oot-core objects.

47. **Work RAM for new features (2026-10-04).** Tools pushed .bss 6 KB past SGL.
    Recovered with `#pragma GCC optimize("Os")` on cold/state files (menus, save,
    cutscene script, enemy/actor step, input, water, minimap). Hot renderer and
    collision files stay -O2. Next growth needs code moved into the oot-core blob.
48. **ctypes bool tests after -Os.** A C `bool` return read as ctypes int keeps
    garbage high bits; mask `& 0xff` (test_gameplay stick test).
49. **Item sprites:** `tools/build_item_sprites.py` (OOT_CORE branch of build.sh)
    writes 13 ITM*.SPR; pitch-band sheets store elevation as the pose axis.
50. **Warp probe planning (2026-10-05):** `--clean WARP_PROBE=1`
    does not show the probe: `viewer_hud()` returns under `DOSEI_CLEAN_TEST`
    before rows 10-12. An isolated developer probe can use the existing HUD;
    a Clean-equivalent overlay needs a diagnostic change. `build.sh` hardcodes
    variant output and boundary-check paths, so copying a completed image to
    `build/probe/` does not isolate its build. Isolate checkout/objects/generated
    assets/staging and include every CUE-referenced audio track. Preserve the
    usual Clean image. See TOMB_RAIDER_POLY_NOTES.md; probe built 2026-10-05
    (gotcha 51), initially with 1856 B spare. Later probe builds were human-run;
    severe swim persists. See gotchas 52-54 for Astra's current controlled build.

51. **Isolated probe checkout** (2026-10-05, Tomb Raider warp study). `git archive <rev> | tar -x`
    into `game/build/probe/oot-sat/`, plus `config.ini`, `shared/build/audio-source/`, and from
    `game/build/`: `cd`, `generated`, `oot-core`, `TRACK0*.BIN/.json`. Do NOT `cp -r build/dependencies`:
    it holds symlinks to the SDK and `C:/msys64`, so cp copied 3 GB; `--prepare` recreates them.
    `build.sh` finds the toolchain at `$here/../..`, so export `SH_ELF_LINUX=/mnt/d/.../sh-elf-9.3-linux`.
    Without `TRACK0*.BIN` the cue step fails with `Missing declared CD song CHEST: TRACK02.BIN`.
    Build: `./build.sh --quick OOT_CORE=1 WARP_PROBE=1` (dev variant: HUD visible; `--clean` hides it).
    Run it from a script file via `wsl.exe -e bash <script>` (gotcha 34).

52. **Astra controlled warp build (2026-10-05).** `tools/control_probe/prepare.py`
    snapshots the existing Opus probe into `build/astra-control/oot-sat/`, preserving
    its Field STM and all CD audio tracks. It refuses to overwrite an existing
    snapshot. Run the generated `build/astra-control/build.sh` in WSL; the normal
    images and Opus copy remain untouched. No `WARP_PROBE=1`: this build replaces
    the crowded HUD with a low-RAM command/trace mailbox. Build boundary: 5712 B.
    Initial harness skipped TITLE -> FILE_SELECT, so loading the scene did not
    enter PLAY; corrected before successful movement verification. The boot uses
    the existing Level Select path with Adult/All Items enabled.

53. **Visible Kronos belongs on the human's desktop.** Human explicitly authorized
    Astra emulator control and requires the real GUI. Run
    `powershell.exe -NoProfile -ExecutionPolicy Bypass -File game/tools/control_probe/launch.ps1`
    from the repository root, outside the Codex restricted desktop
    (`require_escalated` in this environment). It launches the configured original
    executable visibly with the isolated disc; no alternate Kronos/settings copy.
    A launch inside the restricted desktop was invisible to the human, and
    PrintWindow returned a white render area. Read/control/capture commands for
    the real GUI also require that desktop/process access. No global key injection.
    Close the controlled session before rebuilding its mounted image.

54. **Probe HUD height units differ.** Opus's small `L x,y,z` line prints Link's
    eye/collision Y; its alternate `link x,y,z` line prints feet Y (90 lower).
    Astra `pose --pose X FEET_Y Z YAW` explicitly takes feet and labels its HUD
    `FEET`. Human `L 37,275,4353` corresponds to feet `(37,185,4353)`. The first
    automation test incorrectly placed Link 90 units high; final replay uses the
    corrected height and verifies settling/jump through real physics.

55. **Local TR checkpoint (2026-10-05).** Current full runnable archive:
    `build/astra-control/checkpoint-2026-10-05/game.cue`, all audio included.
    It contains the camera fix and final bounded local renderer, 1632 B below
    SGL. New renderer source remains in `tools/control_probe/` and the isolated
    checkout. `build_tr_patch.py` consumes the frozen STM; `install_tr.py` and
    `install_camera.py` install into that checkout only. Do not run prepare over
    it. Human stopped renderer changes and requested FIELD_SQUARE_RETOPO_PLAN.md.

56. **Controlled comparisons need identical residency.** Stream both local
    pieces before each mode and wait for all ten children. Streaming hysteresis
    otherwise makes the first baseline pose use a different LOD set. Compare
    actual matrices and normal-input endpoints, not only displayed positions.
    Whole-scene determinism is not claimed. Final evidence: verification/tr-v10.

57. **Raw sprite submission bypasses SGL backface checks.** Preserve the
    original Single_Plane test and material/CLUT semantics. Without it an
    under-terrain camera can paint ground over Link. Near-crossing commands and
    missing faces alone do not prove SGL's culling rule. Guard saturation is
    not geometric clipping.

58. **Ground camera clearance differs from wall clearance.** Shortening the
    focus-to-eye ray at a slope may leave the eye only one unit above the floor.
    Main player_camera now preserves age/profile height plus pitch above ground
    and then constrains the ray against walls/ceilings. The main ELF-only check
    passes with 6160 B spare; preserved Clean/Debug images remain unchanged.
    Do not use build.sh's image-deleting failure path for an ELF-only audit.

59. **Record moving cost separately from cached FPS.** Final local TR candidate
    renders a frozen pose at about 29 FPS, but a paired normal 90-step walk
    takes about 54% longer than baseline. It reserves 76800 extra texture bytes,
    zero slots, at most 160 local commands. Positive visual feedback is not
    performance acceptance. New square terrain also needs collision limits:
    SA.COL currently has 1579 triangles against the baker's 2321 maximum.

60. **Field retopology patches (2026-10-05).** `tools/field_retopo.py` bakes one
    content-addressed bundle (`assets/layouts/meshes/<sha>/patch.json`) used by
    three consumers: the STM (build_hybrid_scene/build_field_chunks), SA.COL
    (build_scene_table) and SA.OOC (oot_core_import, generated
    `spot00_retopo_PolyList/VtxList.inc.c`). Each writes
    `build/generated/retopo-<stm|col|ooc>.json`; build.sh refuses a disc whose
    records differ. Selecting a patched layout needs a full build: `--quick`
    keeps the old STM/COL but re-imports SA.OOC from the live selection, and the
    pairing check then stops it. Main selection is now `field-square-184`
    (human-authorized Clean promotion, 2026-10-05).
61. **Parents stay through texture sizing.** Removing replaced faces before the
    greedy/floor-upgrade passes re-distributes VRAM and changes unrelated tiles.
    `apply_patches` only marks them; `replace_pieces` swaps after sizing.
    `field_retopo.py --budget` diffs every STM face (corners, attrs, texels) and
    fails on any unrelated change. Fanned neighbours that had been rejoined with
    a partner into one quad leave that partner drawn alone (reported as
    orphan-partner).
62. **Small floor pieces lose far sort.** `floor_uses_far_sort` needs an XZ
    extent over 64. Retopo records carry `far_sort` so cut pieces keep the
    parent floor's 0x66.
63. **TR control probe assumes C=D children.** `build_tr_patch.py` asserts the
    old P3 triangles; a square-retopo STM has none. Square images run plain SGL;
    `compare_square.py` and `performance_tr.py --modes 0,0` measure them.
64. **Field BgCheck takes the spot branch** (`BgCheck_IsSpotScene`): memSize
    0xF000, 16x4x16 subdivisions; the 0xB798 custom size is never reached.
    `PROBE_SCENE=SCENE_HYRULE_FIELD oot-core/tests/run_bgcheck_probe.sh <SA.cpp>`
    prints `polyNodes` (count) and `polyNodesMax`. Count is valid; max uses
    64-bit host type sizes. Target sizes (sh-elf g++): CollisionContext 8068,
    StaticLookup 6, SSNode 4, CollisionPoly 16, Vec3s 6, so capacity =
    (0xF000 - (6144 + polys + 4000 + 8192 + 3072 + 8068)) / 4.
    Script: build/square-retopo/bgcheck/sizes.sh.
    The fx host probe then hits a pre-existing ASAN stack overflow in
    `OotCore_BgInt` (8-byte memcpy from a host f32), unpatched Field too: read
    the node lines, ignore compare_probe's crash.
65. **Collision normals: one rule.** New polygons: Q15 from the welded integer
    triangle; SA.COL stores round(q15/2) (the ROM rule); SA.OOC writes
    COLPOLY_SNORMAL literals half a step past q15 so the (s16) cast lands on it;
    dist from the Q15 normal. Baseline OOC/COL already differ by one Q14 unit on
    786 faces (Astra audit); do not call that a regression.
66. **Integer rounding decides coplanar overlay ties.** Road collision overlays
    sit within ~1 unit of the Field ground; after re-tessellation `bg_floor`
    returns the road surface instead of grass at a few points (5 of 11,384 in
    the 184 sweep, footstep sound only). The host floor test fails if it grows
    past 2%.

67. **Streamed Field must not need one contiguous whole-file block.** The
    retopo STM fits aggregate cart RAM but exceeds the largest heap block.
    `field_storage.h` reads a validated header, then allocates geometry and
    sector-aligned pixels separately. Keep both blocks alive through streaming,
    free both on failure/unload, and retain the first-sector pixel prefix.
    Do not replace this with a full temporary file read. Loader-only 184/256
    builds pass with 9152 B below SGL and complete visible-GUI boundary walks.
68. **Environment API/OOC changes require a coordinated rebuild.** API20 adds
    clock/sky state and scene/room metadata. Rebuild host, core and every OOC.
    NTSC_1_2 has version value4 while PAL_1_0 is3: the original >=PAL guards
    apply to NTSC1.2. Use the real versions.h in host tests. Source Sun's Song
    also needs the header declaring OCARINA_MODE/ACTION enums.
69. **Field bank aliases are not gameplay scene IDs.** KOKIRI_FIELD_SCENE is
    the flat cutscene's STORY_BANK_FIELD, not SCENE_SPOT00. Gameplay fog policy
    must use SCENE_SPOT00. Rebuild per-map fog lookup tables after each bank
    assigns forest_scene, not only once before the first room load.
70. **Landmark removal changes object capacity as well as textures.** The
    isolated184 far-landmark sweep needs60 resident objects, up from59;
    update the generated capacity header and manifest with the staged STM.
    Landmark palettes have a separate deduplication class so terrain fog cannot
    wash them out. Canonical WSL3.11 bake is required for bitwise freeze checks:
    host Python3.12 can differ at a few floating-point raster boundaries.
71. **SDK keeps inline helper bodies.** `-fkeep-inline-functions` retained sky
    helper copies across translation units. Local static non-inline helpers in
    environment_sky.h recover space; combined environment-v3 ends .bss at
    0x06082BA0, 5216 B below SGL. Recheck the actual target map after changes.
72. **HUD weapon patches need their whole VDP2 reservation.** BUTTONS.MAP is
    14288 B, within0x3800 bytes. Dynamic C-item maps start0x25E4B800 and occupy
    8192 B; hearts begin0x25E50000. Keep baker/compositor addresses and pause
    backup coverage synchronized. Preserve action-caption overlap in patches.
73. **SGL centroid sort can overflow for retained far landmarks.** SORT_CEN
    sums four Q16 depths in signed32 bits before averaging: mean depth8192
    crosses its limit. Raising the CPU range does not make it safe. SORT_MIN/MAX
    avoid the sum. Tagged landmarks now use SORT_MIN; ordinary terrain keeps
    its existing sort policy. Runtime visibility/occlusion still needs human
    acceptance. See FIELD_LANDMARK_AUDIT.md.
74. **Whole-Field ground grids must include the owl in pricing.** The outer
    512/768/896/1024-unit trials exceeded combined table/vertex/slot limits.
    The selected outer1280 + central184 layout fits all existing reserves.
    `field_ground_grid.py` splits only source visual planes; it does not add
    collision nodes outside the accepted central bundle. Keep full streaming
    sweeps, source-plane/UV tests and STM/COL/OOC pairing checks. Uniform184
    across the map is not implemented or budgeted to fit.
75. **Cached sky colour code must stay compact.** The initial full Clean link
    with the horizon exceeded static RAM by688 B; compact shared mix helpers
    reduced that to80 B. Size-optimizing the cached refresh too gives final
    .bss0x06083F30, 208 B below SGL. Do not lower heaps or actor limits to hide
    a link overflow. Logs: field-clean-build.log (asset bake),
    field-clean-link-final.log (passing relink). New sky target helpers use
    integer math only; other pre-existing wide runtime paths remain debt.
76. **Field haze consumes geometry but no texture slots.** One static quad is
    submitted in world space at3200 units with MESHon; count its four vertices
    and one polygon alongside Link/owl. Combined worst case is2422/2500
    vertices and2474/2600 polygons. Clean initially exceeded static RAM by16 B;
    compact sky callback/cold background-priority setup gives .bss0x06083FF0,
    only16 B spare (`build/field-haze-final.log`). Keep the boundary guard and
    heap/actor capacities. Human accepted the dark sky, not yet this new band.
77. **Exit/orbit/Link-fade follow-up needs compact frame setup.** The added
    state and second haze panel initially exceeded high work RAM by1056 B.
    Size-optimizing `viewer_draw` (frame setup/dispatch, not geometry loops)
    gives .bss0x06083DA0, 608 B spare (`build/field-orbit-fix.log`). Heaps,
    actor capacities and the boundary guard are unchanged. Current haze totals
    are2475/2600 polygons and2424/2500 vertices including Field/Link/owl.
78. **The usual Clean image needs `OOT_CORE=1`.** `./build.sh --clean --quick`
    alone builds a game WITHOUT the decomp core (no OOTCORE.BIN/OOC/OOB staged,
    .bss looks ~9 KB roomier) and overwrites game-clean.iso. Always
    `./build.sh --clean --quick OOT_CORE=1` (2026-10-05 Fx32 rebuild hit this).
    Worse: the next OOT_CORE=1 quick build REUSED the non-core ram_cart.o and
    scene_flow.o (flags did not trigger a recompile). Non-core ram_cart.h has a
    smaller fixed-carve area, so ram_cart_fixed refused the OOTCORE carve
    ("oc load failed f 0") and every fixed carve base disagreed between objects
    (human: no Ranch NPCs, no ocarina, no rock lifting, missing Kakariko
    building). makefile now writes build/generated/oot_core_mode.stamp and
    every game object depends on it, so flipping OOT_CORE recompiles all.
79. **Fx32 (Wave 0): an outlined `Fx(float)` runs soft-double.** The float/
    double constructors and `fx_from_double` must stay `FX_INL`; when GCC
    outlined them at -Os every literal called __muldf3/__fixdfsi at runtime.
    Runtime mul/div are out of line (OotFx_Mul/Div/MulInt/DivInt/IntDiv in
    oot_math.cpp): inlined saturation cost ~90 KB, and a constant divisor in
    an inlined op became a dmulu.l reciprocal multiply. Audit every blob:
    `sh-elf-objdump -d build/oot-core/oot-core.elf > X; python3
    tools/audit_oot_core_wide.py X` (dmuls/dmulu, divider registers, libgcc
    64-bit/soft-float calls under any __/___ prefix; literal-pool words that
    decode as mac.l or `sts mach` are ignored). Run `--self-test` after editing
    its regexes: the first version missed target ___divdi3 entirely. Remaining hits are GCC magic multiplies for
    decomp INTEGER `/10 /20 /60` (28 sites, 10 functions): open question.
80. **Fx32 probes run in WSL.** `OOT=... bash oot-core/tests/run_bgcheck_probe.sh
    [build/oot-core/scenecol/SA.cpp]` (PROBE_SCENE=SCENE_HYRULE_FIELD for SA)
    and `HOST_CXX=g++ bash oot-core/tests/run_host_probe.sh` (now python3).
    `FX_SAT_AUDIT=1` on the bgcheck probe links oot-core/tests/fx_sat_audit.cpp
    and prints each saturating site; symbolize with `addr2line -f -C -i`.
    Probe flags use -nostdinc and the prelude keyword renames: host-only
    helpers there are plain C style (no <cstdio>, no `namespace`/`class`).
81. **Backslashes through Bash heredoc -> Python edits get mangled.** `\b`
    and `\1` reached oot_core_import.py as \x08/\x01 bytes (regexes silently
    matched nothing / emitted control chars). Edit regex text with the Edit
    tool or a script written by the Write tool; grep for [\x00-\x08] after.
82. **Importer Fx32 rewrites must be mirrored by tests that re-run parts of
    the importer.** test_core_bgcheck rebuilds z_bgcheck from raw source; it
    now applies fix_rand_ranges/fix_cross_products/fix_stored_squares too,
    or its source disagrees with the imported FxSq headers.

## Camera/Adult Link build verification (2026-10-06)

Correction: the Gossip Stone messages in `camera-ease-clean.log` are nonfatal;
`build_core_meshes.py` returns success after reporting them. They did not establish
the cause of that interrupted build. Claude's full build completed at 10:33
(`fix-full-clean.log`) and compiled both changed camera sources. Its .bss ends
0x06083ED0, 304 B spare; the earlier 2,704 B report came from mixed core objects.
The ISO program, core and all five Adult Link payloads match staging byte-for-byte.
ADLTMESH.BIN is restored to 21,504 B (672 polygons), previously 11,456 B (358).
No extra quick build is needed for the camera. Runtime acceptance remains pending.

## Ocarina repeat rebuild boundary failure (2026-10-06)

The shared-tree quick Clean rebuild reached linking but failed the SGL boundary:
.bss 0x06085600 exceeds 0x06084000 by 5,632 bytes. Log:
`build/ocarina-repeat-clean.log`. The guard removed usual Clean ISO/CUE/ELF/raw.
The prior 10:33 image is no longer at that path. Restore code/static-RAM fit before
retesting; do not lower heap/actor capacities or disable the guard. Ocarina host
checks pass; this is not target/runtime acceptance. Size growth is not yet attributed.
83. **No software 64-bit divides (human 2026-10-06).** `int64 / variable`
    calls libgcc ___divdi3: use shared/lib/collision/div32.h (div64s_approx,
    muldiv_s32, muldiv64_s32). `int64 / power-of-two constant` is inlined
    by GCC (keep it: it truncates like the original; `>>` floors and broke
    exact host contacts by one unit). div32 bodies: one out-of-line SH-2 copy
    (inlining cost ~8 KB of work RAM; DIV32_IMPLEMENTATION in
    kokiri_collision.c), static inline on the host. Test fixtures that copy
    single functions need the header: test_graphics_backend.run_c adds it;
    custom harnesses (cutscene parity, item aim) include it explicitly.
    Audit both ELFs with tools/audit_oot_core_wide.py (dmuls allowed).
