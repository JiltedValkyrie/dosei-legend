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

## Playtest package

Build Clean, then run `tools/package_playtest.sh` in WSL with `OOT_SAT_REV` set.
Output goes to `playtest/` (gitignored). The package holds the disc (cue, iso and CD
audio tracks), the draw-cap-fixed Kronos with local paths blanked and the 4 MB
cart preset, and `README.txt` (template: `tools/playtest_readme.txt`). It ships no
BIOS. Agents build; the human launches
    Kronos/Saroo.

## oot-core specifics

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
