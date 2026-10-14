# Build guide and gotchas

The authoritative build path is **Linux** (WSL Debian 12 on this machine).
Do not use MSYS2 or Git Bash for builds.

## Build commands

2026-10-13 child-route batch part 3 (Claude): matched Debug built (md5
11244013) with per-layer scene objects (format 5, API 36), Player bank split,
Gohma CVQ1, 32 KB music level chunks and cold loaders in HOSTCOLD `.cartt`
(BUILD.md 115-121). `tools/heap_peak_model.py` FITS on the staged disc.
Old Debug images preserved (`build/preserved-debug-2026-10-12/`, `-10-13/`).
OAP v2/96-byte header/services ABI2 unchanged; rebuild core + packs + OOCs together.
Full status and resume order: [stop handoff](CHILD_ROUTE_STOP_HANDOFF_2026-10-13.md).

Current baseline: candidate 10 passed its target boundary (Debug 496 B
spare, Clean 5,968 B), audits, budget and ISO/staging comparisons. The old
112 B overflow was resolved by candidate 8; it is not a current blocker.
Human has tested candidate-10 Clean and reports improved performance.
Gameplay repair is now active; preserve baseline images while validating
its temporary Debug candidate. See [handoff](PERFORMANCE_HANDOFF_2026-10-12.md).

Authorized Mednafen test variant (2026-10-12):
`./build.sh --perf-kokiri --quick OOT_CORE=1` builds
`build/game-perf-kokiri.cue` with private host objects. It enters child Kokiri
room 0 via the ordinary unsaved Play Test path after boot initialization;
current source uses Kokiri spawn 9 outside Mido's house for a clear short test
route, only in this temporary variant. Ordinary entries stay unchanged;
three hearts and starter slingshot match the gameplay test. It neither binds
an adventure save slot nor changes the usual Debug/Clean images. The temporary
build stages its own host/core/assets; restore the entire preserved Debug
staging directory after verifying the test ISO so all usual payloads remain
consistent. Restoring only 0.BIN is insufficient after core/asset changes. Emulator tests are
now explicitly authorized by the human. Compare M/P/C on the same route;
restore any temporary keyboard bindings when closing the test session.

Earlier 2026-10-12 performance batch used Debug only; human subsequently
authorized candidate-10 Clean once. Gameplay repairs now use a temporary
Debug image first; preserve the accepted Clean until repair validation. Use `./build.sh --quick OOT_CORE=1` for this code-only batch;
do not pass `--clean`. `CART_ACTOR_POOL=1` restores the old reserved cart pool
for diagnosis; default high-WRAM pool is included in the mode stamp and RAM
boundary check. Intact signs now use SIGNALL.BIN (14 points, 19 faces); the
current candidate retires SIGN0.BIN through SIGN10.BIN and fragment simulation.
Stage the new intact asset even on --quick builds; remove those exact retired files.
Rendering follow-up also uses this Debug-only command. Cel DMA waits before
and after each transfer, retaining CPU fallback. Master-prepared forest tables
are followed by a queued slave cache purge before possible SGL slave transforms.
Mode 1 in-place packing uses dead depth/side scratch and remaps all polygons.
Mode 2 uses a 512-point high-WRAM cache plus a full-bank-capacity Low RAM spill, temporarily
remaps only visible indices and restores them before the next prepare. Hidden
faces/source points stay unchanged. Every legal bank fits; never truncate
geometry. The Low RAM CD directory reservation is 0xA000 (tables still 0x9DB0),
with its old unused 0x6000 tail at 0x253500 used for spill points. Both C and
linker guards prevent overlap; fs_low_init clears only the directory reservation.
File/directory capacities and addresses stay unchanged. Check the SGL boundary
as well as .lowfs size on every build.
Player anchor-only walker replaces discarded flex-limb matrix/display output;
importer and core must rebuild together, including CRC-bound actor packs.
Fx header changes must likewise rebuild the core and CRC-bound packs. Verify
the target division loop as well as host arithmetic tests: current fx_div_u
has one initial divide and no calls in the fractional loop. Latest Debug
6117a58c: 151 tests pass, both math audits clean, all 1,434 ISO files match
staging; .lowfs is 0x9DB0 and .bss ends 0x06082FC0 (4,160 B below SGL).
That ordinary image stays preserved while temporary candidates are tested.
Last successful --perf-kokiri 6f806172: 202 focused tests, zero math-audit failures,
1,424 payloads matched, .bss ends 0x06083EB0 (only 336 B spare); core .lowbss
0x9130 fits 0xA000. Changes also require fresh SP2 archives and their parser:
sprite archive pixel starts and allocations are 16-byte aligned; legacy
contiguous files still load. makefile explicitly tracks oot_sprite_archive.h
and the included Player decoder C source. New matrix/IK angle importer changes
must rebuild the core and every CRC-bound actor pack. Verify saved candidate
staging independently with `python3 tools/check_forest_budget.py --cd PATH`;
normal staging is restored to the preserved Debug after isolated builds.

2026-10-12 exit follow-up: host/core API32 adds entrance spawn to `play_init`;
OOC format `0x4f4f4303` appends original per-layer exit lists. Rebuild all OOCs
and CRC-bound packs with the usual wrapper; API31 cores/format-2 blobs cannot
be mixed into this image. Scene prep watchdog now measures lack of progress,
not total duration; its progress value is diagnostic, not a frame-time metric.

Field actor packs (2026-10-08): `SA.OAP` must relink against the exact
`OOTCORE.BIN` CRC. Build all four actors plus six source effect objects; omitting
the effect objects leaves undefined profiles. Keep pack ELF/map/JSON evidence
under `build/oot-core/field`, staging only the OAP. The make rule checks the
combined Field OOC, all six OOBs and pack memory against the unchanged 256 KiB
scene carve. New enemy SFX exporter is `build_field_enemy_audio.py`; the existing
`build_field_audio.py` remains the Field music exporter.

The expanded renderer initially linked but exceeded the fixed SGL base. Never
treat a successful raw/ELF link as the boundary check. The existing 48,128-byte
non-cart heap is redistributed as 35,840 high-WRAM bytes plus 12,288 low-WRAM
bytes (previously 39,936 + 8,192); total capacity is unchanged. The low zone is
initialized by the existing allocator boot path. Effect views use the unused
0x19200..0x197ff low-WRAM span, with a compile-time size check, rather than a
1,408-byte local array on SGL's 1 KiB stack. Caps and command tables stay fixed.
The earlier isolated target check ended .bss at 0x06083400; current boundary
evidence is recorded with the Debug batch above.

Run Linux host tests with `DOSEI_OOT` set before importing tooling. Broad legacy
test discovery currently includes stale decimal room filenames, Windows compiler
defaults and shared-library probes lacking `-fPIC`; a failed broad run must not
be reported as a green suite. Field's focused tests and actual source probe are
recorded separately in the Field handoff.

Water Temple isolated probes: actor translation units need their corresponding
imported actor-directory include path (Ruto includes cutscene data there).
Run `oot-core/tests/run_water_temple_probe.sh` under Bash in WSL; it imports
original water-controller actions and links the actual Fx math implementation.
Its deterministic engine I/O does not establish live camera/ocarina integration.
ABI26 support compiles, but is not in the accepted ABI25 Field ISO. Keep that
image intact while Kronos is running. Transition-list OOCs now carry format
0x4f4f4302; old blobs fail admission. Building only game-clean.raw does not rebuild
all OOCs/OOBs: explicitly build data targets or use the full wrapper before
mastering the next image. Current isolated support .bss ends 0x06083470.
Stinger offline segment 8 is ACTOR_SETUP_OPA_DL (material commands), not a texture.
Shell Blade display lists use ModifyVertex signed ST edits: update cached UVs
without applying a limb transform again. Water sprite bakes currently remain
isolated under build/water-temple/sprites until complete pack admission.
Keese DLs use LERP(TEXEL1, TEXEL0, ENV_ALPHA, TEXEL0): the shared DL walker uses
tile 0 unless a baker sets `env_alpha`; set it from the source Draw env colour.
Spikes DLs call segment 7 (func_8002EBCC/ED80 reflection setup): bind it to an
end-DL offline. Skeleton-less sprites use `STATIC_SPRITES` in
water_temple_sources.py and share one cel layout across variants.
Raw-target check without mastering: build/water-temple/target-raw.sh (Clean,
--quick, OOT_CORE=1, target game-clean.raw). A failed boundary check deletes
the usual ISO/CUE: back them up before any raw build.

Human-accepted texture density (2026-10-08): use
`./build.sh --clean OOT_CORE=1` in WSL for the usual
`build/game-clean.cue/.iso`. Clean defaults to `DOSEI_TEX_HALVE=2`;
explicit `0` restores original density. Standalone tools and other build
variants still default to `0` when unset. Explicit `1`
halves room and actor mesh TEX tiles, including LINK/ADULT/LGEAR; `2`
halves rooms only. The human clarified TEX tiles only: baked SPR sheets,
HUD and get-item sprites keep their existing dimensions. No runtime caps or
command-table allocation change. Human accepted the reduced look and reported
better performance; the screenshot shows VRAM 49% and CPU~ 79%. No paired
FPS/load-time benchmark was captured. The existing accepted image already uses
mode 2; changing the wrapper default requires no new asset bake for that image.

Use a **full build when switching modes**. The all-scenes fingerprint includes
the mode; `--quick` skips room regeneration and cannot switch texture density.
The first bake after converter changes is slow. Preserve its preflight cache
and resume with the same full command after interruption. The initial WSL
process ended with exit 1 mid-room and no Python/compiler error during this
task; the cause was not established. Do not treat a partial bake as an image.
Descriptors and pixels must be rebuilt together. NAVIPOOL deduplicates already
halved flight-bank tiles; do not halve it again. Field's complete pool, including
near/far/landmark tiles, is halved once before its residency sweep. CLUTs retain
all 16 entries and their existing alignment; eight-wide tiles save less than 75%.
The pass precedes the old room pixel cap: a room already reduced by that cap
need not become exactly one quarter of its previous output. Compare actual
TEX files, not just source dimensions. Room IDs are base 36, including letters;
include every S/Z/C room name and the panorama banks staged directly to CD.
Three old story banks survived under current image-backdrop IDs: `SNR0`
(`entra_n`), `SPR0` (`market_alley`) and `SQR0` (`market_alley_n`). They were
not rebaked and falsely inflated the measured maximum. Density builds now
prune MSH/TEX only for registrations whose shape is `image`; the runtime uses
their RGB or separate C2 panorama instead. RGB, collision, real mesh scenes
and virtual story/panorama banks remain. Mode 0 does not prune. The removal
ledger is `build/generated/obsolete_image_banks.json`; the experiment retained
old files in `build/tex-halve/before-banks`. Report these as removed obsolete
banks, not texture-halving savings. Do not infer texture VRAM from stale files.

Measure before overwriting staging with
`python3 tools/measure_texture_halving.py --out build/tex-halve/before.json`,
then compare after the full build with
`python3 tools/measure_texture_halving.py --before build/tex-halve/before.json --out build/tex-halve/after.json`.
The second command also writes a per-room CSV. Its bank bytes include CLUTs and
alignment; free-after-residents additionally reserves worst-age Link, existing
runtime sprites and 64 KiB actors. This is capacity accounting, not measured
runtime allocation, visual quality or load latency.

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
30. **All retail maps require a complete room bake.** The full build runs
    `build_all_scenes.py --retail-only --refresh-stale` and then
    `build_scene_table.py --require-retail`. All 101 retail scene prefixes must
    register; a blocked map fails the build. Nine `DEBUG_ASSETS` entries have no
    payload in the retail inputs. Room banks live in `build/all-scenes/`;
    `registered.json` fingerprints both the registration tool and preflight
    contents, so changed caps cannot reuse stale exclusions. Fresh full bakes
    are expensive; converter fingerprints permit unchanged banks to be reused.
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
47. **CORE_COLLISION flips need a full rebuild; CRLF breaks WSL scripts.**
    `CORE_COLLISION` (default = `OOT_CORE`) swaps the C collision library for
    `src/bg_core_shim.c` + `src/bg_core_link.c` and widens `BG_DYNA_MAX` to the
    core's 50 bgIds, so it is part of `oot_core_mode.stamp` (`1c1`, `1c0`, `0`).
    On Windows, Python `Path.write_text()` and `git stash -u`/`pop` (with
    `core.autocrlf=true`) rewrite files as CRLF: `.sh` scripts then fail in WSL
    with `$'\r': command not found`. Write with `write_bytes`/`newline='\n'`
    and check `grep -c $'\r'` before running WSL scripts.
48. **Swap game sources before line `SRCS =`.** jo_engine_makefile expands
    its target's objects from SRCS when it is included, so a later
    `SRCS := $(filter-out ...)` still leaves `No rule to make target
    src/recomp_collision.o`. `COLLISION_SRCS` is chosen before SRCS for that
    reason. The div32 helpers have one definition: kokiri_collision.c with
    the C library, src/bg_core_link.c with CORE_COLLISION.
49. **PLAYER_SOURCE needs the frame bank first.** build.sh regenerates
    `build/player-migration/bank_full` (ALL.PFB + ids.json) when its tools
    change; oot_core_import.py reads ids.json for the anim headers and the
    makefile copies ALL.PFB to `PLAYANIM.PFB`. The stamp now includes
    `p$(PLAYER_SOURCE)`. `./build.sh --clean --quick OOT_CORE=1
    build/oot-core/oot-core.elf` (or `oot-scene-packs`) link-checks the core
    and packs without mastering a disc; the game ELF target does not relink
    the core.
50. **Disc directory holds 1536 entries.** The 63 scene packs pushed it to
    1540. Core-collision / real-Player builds park files they no longer read
    (all `.COL`, LINKANIM.BIN, ADULTANM.BIN) in `build/disc-retired`;
    build.sh restores them first so the Field pairing check, host probes and
    rollback builds still find them. build.sh's first "boundary" line reads
    the previous map; trust the last one. Real-Player Clean: .bss ends
    0x06078380, 48,256 B spare (C Link physics no longer linked in).
51. **Host .text counts against the SGL boundary (2026-10-12).** Code, data
    and .bss are contiguous from 0x06004000, so a code-only change can fail
    the `.bss ends ... above the SGL work area` guard (candidate 9: +3,200 B,
    mostly scene_prepare at -O2). The LTO map has no per-object sizes: rerun
    the logged sh-elf-gcc line for one file with `-flto` replaced by
    `-ffunction-sections` and `-o /tmp/x.o`, then `sh-elf-nm --size-sort -S`.
    Cold helpers take `optimize("Os"), noinline`; master-only snapshots can
    move to a bounded Low RAM carve. Do not cut gameplay capacities.
52. **Mednafen private-desktop helper: launch from the PowerShell tool.**
    `mednafen-test-control.ps1 -Action launch` started from a bash-spawned
    `powershell.exe` creates a desktop the later PostPrivate calls cannot use
    ("Private desktop operation failed"). Launch and close with the
    PowerShell tool; press/capture driver scripts may run from bash.
    Close every session (`-Action close`) to restore mednafen.cfg.
53. **Clean rebuild with the SIGNALL staging (2026-10-12).** Like the
    `--perf-kokiri` scripts, `build/clean10-build.sh` runs build_sign_intact,
    retires SIGN0-10.BIN from staging, builds `--clean OOT_CORE=1`, audits,
    verifies all ISO payloads, then restores ordinary Debug staging. It backs
    up the previous Clean image to `build/mednafen-test/clean-c3f29128/`.

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
84. **Player migration SH-2 audit is WSL-only.** `TARGET=1 OOT=/mnt/d/.../oot
    bash oot-core/tests/check_player_migration.sh` uses Linux sh-elf 9.3
    (`SH_ELF_LINUX` overrides) and compares against `build/obj-clean/oot-core`
    (build Clean first or pass `--live`). Write WSL helper scripts with LF
    endings: a CRLF `.sh` fails on `$'\r'`. Git Bash `python3` may be the
    Windows Store stub (permission denied): use `python` there.
    Optional `player_migration_symbols.py --gc-ld <toolchain>/bin/sh-elf-ld
    --nm <toolchain>/bin/sh-elf-nm --size <toolchain>/bin/sh-elf-size
    --out build/player-migration/memory.json` measures isolated relocatable
    section-GC and header-unassigned Low RAM gaps. This is not a resolved link
    or runtime-free-memory reading. Overlay entry symbols are C++ mangled;
    rooting `_Player_Update` would silently omit the real function without the
    tool's explicit root checks. Gameplay roots still retain native Player_Draw.
85. **Standalone Player GC omits newly retained engine dependencies.** Run
    `OOT=/mnt/d/.../oot bash oot-core/tests/measure_player_placement.sh` after
    the target gate. It rebuilds bridge copies without duplicate definitions,
    retains all current core objects + Player + libgcc, then adds real source
    animation headers. Only `build/player-migration/placement` is written.
    Baseline size must match the existing ELF. This is a relocatable lower-bound
    probe; missing engine/skeleton/frame implementations remain unresolved.
    Original three-region capacity already fails by 3,884 B. Proposed retired
    music/fairy reservations add 24 KiB without shrinking heap; actual linker
    partitioning, per-region loading/zeroing and final fit remain unimplemented.
86. **Shell/compile traps in host probes.** `export OOT=/x DOSEI_OOT=$OOT`
    expands `$OOT` before it is set: DOSEI_OOT ends up empty and the importer
    silently falls back to the Windows path. Use two exports. The core flags
    start with `-x c++`, which also swallows following `.o` files: put
    `-x none` before objects. Host `s32` is 64-bit `long` on Linux; give
    C headers `int`-based int32_t, never `s32`.
87. **W0a sprite archives need a full asset rebuild.** Run
    `./build.sh --clean OOT_CORE=1` when moving from old generic SPR staging.
    The baker writes intermediate clips under `build/generated/generic-sprites`;
    after object linking, `build_sprite_keys.py` resolves skeleton/animation
    addresses through `obj_syms.ld` and stages object+skeleton `.SP2` archives
    plus scene manifests. Old `G?????.SPR` staging does not satisfy the new
    loader. A quick-only code rebuild against that old staging is insufficient;
    use `--quick` only after the matching full asset build.
88. **Actor packs belong to one exact resident core.** W0a introduced core API23 and
    OAP1, linked at the fixed top of the scene carve. `build_actor_packs.py`
    verifies that `--core` ELF converts exactly to `--core-bin`, then binds the
    pack to that binary's CRC. Rebuild host/core together for API changes and
    rebuild every pack after any core change; old symbol addresses or CRCs
    cannot be reused. After a full Clean build, the standalone infrastructure
    target is `./build.sh --clean --quick OOT_CORE=1 oot-actor-pack-test`.
    Its `build/oot-core/pack-test/TEST.OAP` exercises linking/constructors only,
    imports no actor, and must stay off the disc. Building this target alone
    does not refresh the game ISO or prove runtime acceptance.
89. **Gameplay/drop host harnesses now run in Linux.** `test_gameplay.py` and
    `test_item_drops.py` find host `gcc` on PATH and build position-independent
    shared libraries. Run them in WSL with `DOSEI_OOT` set to the Linux decomp
    path and generated tables present; a skipped test is not a passing probe.
    The historical Windows compiler path remains a fallback in these harnesses,
    not the authoritative build workflow.
90. **W0a shared services must fit the existing RAM boundaries.** The first
    W0a link crossed SGL by 1,600 B; its guard removed the unsafe output.
    Cold scene/SPR2 validation and preload now execute in the cart core.
    Dynamic collision owner records share the existing 4 KiB low-RAM draw
    carve, with a target `sizeof` assertion and explicit boot/reset ownership.
    Do not grow heaps, reduce actor capacities or move the SGL boundary to
    bypass the check. Final measurements are in
    `ENEMY_W0A_HANDOFF_2026-10-08.md`; rerun Player retention/partition checks
    against this core before using any older free-space estimate.
91. **Map registration must preserve old IDs.** Keep the original eleven native
    entries and `LEGACY_GENERIC_ORDER` fixed; append newly admitted maps. Sorting
    the entire table by source ID changes filenames and old save destinations.
    Full asset generation is required: scene entries (26 bytes) and portals
    (20 bytes) now share the loaded `SCENETAB.BIN` allocation with names, spawns
    and doors. Generated C holds pointers, with target size assertions. Never
    combine a new binary table with stale generated C/headers or a quick-only
    build. `test_level_select` checks binary fields and menu rows;
    `test_all_map_registration` rejects incomplete final staging.
92. **Large dungeon collision uses exact allocations.** The maximum is 5,096
    triangles (194,520 decoded bytes), with a 20 KiB XZ index. The raw `.COL`
    read borrows existing load scratch; do not free that pointer. Decode and
    validate into a new allocation before publishing, then release the old
    mesh. Allocation/read/decode failure must retain the previous world. This
    temporary C path remains until Player/core collision cutover; global heap
    capacities and actor counts are unchanged. Test actual decode/index fit
    for every staged map and rollback/shrink through the production loader.
93. **Source-empty stages are explicit.** `hiral_demo` has an empty source room
    display list. Its KRM1 flag admits only a 32-byte bank with all counts zero;
    the loader clears previous geometry and the renderer skips submission.
    Arbitrary empty conversion results still fail. Scene discovery must match
    `<prefix>_room_`, not the word `room` anywhere in a name (`moribossroom`).
94. **Old core resources must unload before native scene assets.** Deferring
    archive/tool/dynamic-copy/mesh release to the next core frame made the
    Ranch-to-Gohma allocation peak exceed the entire heap. `scene_flow_load`
    releases them after successful collision admission and before room/native
    actor loading. Destroy source actors before freeing their resources or code
    pack; frontend reset must first detach the previous save mirror. Dynamic
    registrations must be removed before their triangles are freed, including
    frontend teardown that precedes collision reset. Idle music-cache trimming
    frees only non-current area tables and does nothing during fades/swaps.
    Keep these lifetimes in Player and actor budget models. Focused production
    host regressions: `test_scene_resource_lifetime`, `test_music_area_trim`.
95. **Tool views require matching API24 host/core.** Inventory repairs add source
    sweep endpoints and fallback damage to `OotCoreToolView`. Rebuild both sides;
    rebuild actor packs against the resulting exact core binary as in rule 88.
    `oot_core_init` must set `R_UPDATE_RATE = 3`, normally done by source
    `GameState_Init`; `Regs_InitDataImpl` does not set it. A zeroed register makes
    source velocity movement and scaled turns stationary. Preserve the 20 Hz
    source / 30 Hz host conversion and run `test_core_update_rate.py` plus
    `oot-core/tests/run_tool_actor_probe.sh` after movement/importer changes.
96. **Aim and equipment assets need a full rebuild.** `ITMAIM.SPR` adds a
    2,080-byte/one-slot reserve to every scene budget. Gear tile deduplication
    changes generated texture indices, and `LGEARMSH.BIN` appends 1,068 bytes of
    per-face fallback colours. Rebuild generated headers, mesh, texture table
    and pixels together; quick-only builds against old gear staging are invalid.
    Optional artwork can be absent/short or fail VRAM admission without hiding
    valid gear geometry. Geometry and skin validation remain mandatory.
97. **Room bakes run in parallel.** `build_all_scenes.py` extracts scenes and
    bakes rooms in a process pool (`--jobs`, default `DOSEI_BAKE_JOBS` or CPU
    count capped at 24; set `DOSEI_BAKE_JOBS=1` to debug serially). Output is
    byte-identical to the serial bake (Deku Tree + Kokiri: 1m53s -> 15s at 16
    jobs). Any edit to a converter in `converter_fingerprint()` (including this
    script and `shared/tools/build_kokiri_scene.py`) still re-bakes all 388
    rooms; progress lines arrive out of order, the report keeps source order.
98. **Sound RAM is full (52 B spare).** New resident SFX shrink the area slot;
    `build_action_audio.py` water-fills each area bank, fading the longest tails
    (now including forest `tree_open` and boss `gohma_dead`). Check the
    `trimmed ...` lines and report them when adding resident sounds.
99. **WSL has no `sh-elf-objdump` on PATH.** The audit needs a SH objdump:
    `/home/valkyrie/sh-elf-build/build-binutils/binutils/objdump -d
    build/oot-core/oot-core.elf > X; python3 tools/audit_oot_core_wide.py X`.
    An empty disassembly "passes" with 0 sites: check the line count. Write
    the commands to a script file; `wsl bash -c "..."` from Git Bash mangles
    `$VAR`/`~`. `valgrind` (callgrind) is installed for host collision
    profiling (instruction counts, closer to SH-2 cost than x86 cycles).
100. **`run_bg_port_probe.sh` can hide a link failure.** A host link error in
    the probe build prints `collect2: error` but the script still exits 0.
    Grep its output for `error` after API changes; host stubs for new core
    calls go in `oot-core/tests/bgcheck_host_stubs.cpp`.
101. **Cart carve sizes moved (2026-10-09).** Core blob 0xA0000 at
    0x02760000, scene collision/pack carve 0x30000 at 0x02730000
    (`src/ram_cart.h`, makefile OOT_CORE_LOAD_ADDR/MAX_BYTES,
    OOT_SCENECOL_MAX_BYTES; tool copies in oot_core_regions.c,
    partition_core_regions.py, player_migration_symbols.py,
    bridge_actor_pack.cpp default). `build_actor_packs.py` fails a scene whose
    OOC + objects + pack outgrow 0x30000.
102. **Slave SH-2 rules (async core, 2026-10-09).** Caches are write-through
    but not coherent: purge on the slave before reading master data, purge
    on the master after the join, poll shared flags cache-through
    (`addr | 0x20000000`). The slave has its own FRT: never call
    `frame_timer_*` there (it extends the master's counter). SGL's slave
    stack is ~3.5 KB at 0x06001E00; long jobs switch to
    `RAM_LOW_SLAVE_STACK`. No jo_malloc, CD, jo_printf or sound from the
    slave.
103. **SGL slave queue rule (2026-10-09).** `slPutPolygon` gives a PDATA to
    the slave only when SGL's slave command queue is empty; otherwise the
    master transforms it (sglC08.o). A long `slSlaveFunc` job queued before a
    big submit moves that submit's whole transform onto the master. Queue
    slave jobs where the master does not submit polygons (game steps, actor
    sprites), and drain before big meshes (`kokiri_sgl.c sgl_slave_drain`).
104. **Check the log, not only the exit code.** One WSL `./build.sh` run
    printed a compile `error:` and still returned 0 (2026-10-09, cause not
    pinned down). After every build grep the log for `error:` and require
    the final `built:` line.
105. **`SLAVE_JOBS=0` rollback (2026-10-09).** `./build.sh OOT_CORE=1
    SLAVE_JOBS=0` builds without our second-SH-2 jobs (core update, Link
    skin, scene prepare back on the master). The mode stamp forces a full
    recompile when it flips. Use it to A/B any slave-scheduling problem.
106. **Player aim repair uses API31 (2026-10-12).** Rebuild host, core and
    core-CRC-bound scene packs together. `player_tap_aim.h` is an explicit
    bridge_player_source object dependency. Use the usual Clean image with
    slave jobs enabled; the human reports 10→20 FPS from that work.
107. **WSL sessions can hang up mastering.** This review saw EventFd startup
    failures and a real `mkisofs` Hangup deleting the incomplete ISO. An
    ignored-HUP wrapper (`trap '' HUP`) completed the normal build. Serialize
    WSL verification if startup is unstable. Require the final built line,
    successful boundary/math checks and ISO/staging comparison; an ELF alone
    is not a rebuilt disc. Linux shared-library probes need `-fPIC` and must
    discover gcc rather than silently skip on a Windows-only path.
108. **The SH-2 FRT is 8-bit: never read FRC as a word (2026-10-12).** Read
    FRCH (0xFFFFFE12, latches FRCL), then FRCL (0xFFFFFE13); use
    `frame_timer_frc()` in `frame_timer.h` on either CPU. Mednafen returns only
    FRC >> 8 for a word read (Kronos returns all 16 bits), which made the timer
    jump 293 ms per wrap and fired the slave prepare watchdog falsely.
    `audit_oot_core_wide.py` fails on FRT word/long loads. SGL never sets the
    slave's TCR (clock/8, 18 ms wrap): slave jobs call
    `frame_timer_slave_prescale()` (/128, keeps IEDG for SGL's wake-up). WSL host tests that
    read the decomp need `DOSEI_OOT=/mnt/d/Workspace-Claude/game-decomps/n64/oot`.
109. **Jo's cart heap is cache-through (2026-10-12).** `jo_malloc` zones at
    0x22400000/0x22600000 return uncached addresses: every read goes over the
    A-bus. Kronos hides the cost; Mednafen/hardware do not. Hot, CPU-written
    data read every frame should use the cached alias (`& ~0x20000000`, see
    `kokiri_sgl.c bank_allocate`) with explicit purges where the other CPU or
    DMA writes it. Debug build and Clean share `build/cd`: verify each ISO right
    after its own build (`0.BIN` differs otherwise).

110. **Host headers: no new `static inline` bodies (2026-10-12).** Host C uses
    `-fkeep-inline-functions`, so each includer keeps its own copy even with
    LTO. With one small accessor inline in `oot_core_host.h` (13 includers)
    the build failed the SGL boundary by 16 B; as a plain function in
    `oot_core_host.c` the same batch had 240 B spare. Load image sections are
    0x20-aligned: savings under 32 B may not move `.bss` end at all.

111. **Child-route compile check (2026-10-12).** `build/route-c0-check.sh`
    runs the importer, core meshes and sign staging, `--quick OOT_CORE=1`,
    then restores ordinary Debug staging/image (results in
    `build/route-check/`). `--quick` alone never reruns the importer, so
    scene-pack/actor list changes need it. Pack actors that are not in a
    built object fail to link on `object_*` symbols: add the object to
    `OBJECTS` (symbols come from obj_syms.ld; only scenes listing the object
    load its payload). Source actors calling missing core camera/cutscene
    functions need a classified stub in the bridges, not a pack copy.

112. **Scene carve 320 KiB; pack-only symbols (2026-10-13).** Dodongo's Cavern
    needed 305,136 B (OOC 76,560 + OOB + OAP 213,564). Carve is now 0x50000 at
    0x02710000, 128 KiB taken from bank-2 cart heap in total; core stays at
    0x02760000. Change makefile, ram_cart.h (SCENECOL/OOTCORE offsets, FIXED),
    bridge_actor_pack.cpp defaults, build_actor_packs.py defaults and
    test_actor_packs.py together. `pack.ld` PROVIDEs segment aliases
    `D_01000000` (billboard = gIdentityMtx; core billboard stays identity) and
    `D_06000000` (0x06000000, mapped by SEGMENTED_TO_VIRTUAL). Actor-local
    cutscene data files (`*_cutscene_data.c`) are not imported: EnOkarinaTag
    script refs are weak and `check_okarina_pack` fails import if a pack scene
    spawns tag type 2/4. Use `make -k ... oot-scene-packs`; plain -j stops at
    the first failing pack and its log mislabels interleaved errors.

113. **CD directory is ID-only + exact keys (2026-10-13).** GFS name table
    (24 B/entry) filled the 0xA000 low carve at 1,536 entries. fs_low.c now
    boots GFS with a temporary name table in RAM_LOW_FOREST_BANK, then keeps
    an ID-only table (12 B/entry, DOSEI_FS_MAX_FILES=2560) in .lowfs and exact
    packed 8.3 keys (two u32, base 38 + dot flag) in the old cart MUSICTRG gap
    (RAM_CART_FSKEYS, 20 KiB, no heap cost). File id = ISO position, so keys
    must be strictly increasing: check_disc_directory.py checks staging
    (capacity, 8.3, collisions) and, after mkisofs, `--iso` checks real order
    and deletes the image on failure. The makefile maps every GFS_NameToId to
    dosei_gfs_name_to_id; jo_fs_cd reloads via a temporary heap name table.
    Only 8.3 names; reports (e.g. kingdodongo_meshes.json) stay out of build/cd.
114. **HOSTCOLD cart section (2026-10-13).** Debug .bss was 12,016 B over the
    SGL base. Cold const tables marked HOST_COLD (host_cold.h: generated
    puzzle/wall/web/tree-mouth collision, dialogue pages/rules, cutscene
    tables, core_sprite_rows; 15,824 B) link into `.cart` at the HOSTCOLD
    carve's cached alias (0x026D2C00 core / 0x027FB000 non-core), objcopy to
    HOSTCOLD.BIN (0.BIN/raw use `-R .cart`), and main loads it right after the
    cart claim (size/address checked, else halt with a message). Keep the
    section end ALIGN(16): objcopy pads it and the loader compares sizes.
    Never mark a table read before that load. Cart offsets MSGDATA/SCENECOL/
    OOTCORE moved +0x5000 with FIXED_BYTES; core/scene absolute addresses kept.

115. **Scene blob format 5: per-layer objects (2026-10-13).** `OotSceneBlob`
    gained `layer_objects`/`num_object_layers` (>= 4 masks, bit k = objects[k]);
    format 0x4f4f4305, API v36. Sprite preload and `set_objects` follow only
    the destination layer (`ENTRY->destination_layer`, after `mirror_save`,
    which now runs once before the preload). The host halts the scene if
    `play_init` picks another layer. Importer, core and every OOC rebuild
    together; an old OOC is rejected by `scene_valid`.

116. **Player bank split (2026-10-13).** `PLAYANIM.PFB` is gone. The makefile
    runs `tools/split_player_bank.py` on `bank_full/ALL.PFB`: `PLAYC.PFB`
    (C clips, boot), `PLAYRES.PFB` (common, first scene load until session
    reset), `PG<group>.PFB`, `PCS<oot scene>.PFB` and
    `build/generated/player_groups.h` (host tables, HOST_COLD). Group bit
    order lives in `oot_core_api.h` `OOT_CORE_PLAYER_GROUP_*`; the splitter
    refuses a mismatch. Every Saturn C clip (`build_link_model.CLIPS`) is
    forced resident. The importer patches `Player_UseItem` (gate) — anchor
    change fails the import.

117. **Gohma track is CVQ1 (2026-10-13).** `build_gohma.py` converts
    `GOHMA.ANM` to 8-bit per-pose quantized chunks (32 poses, sector aligned;
    max error 0.47 world units, build fails at >= 1). `cutscene_actor.c` reads
    chunks with sector reads; CVA1 tracks (others, clip swaps) unchanged.
    No `JO_SECTOR_SIZE` in game sources (fs.h is not included): use a local
    2048 constant.

118. **No new inline bodies in shared blob headers either.** `oot_scene_blob.h`
    is included by host C; its helper is a macro (see 110).

119. **HOSTCOLD also holds cold code (`.cartt`, 2026-10-13).** `HOST_COLD_CODE`
    (host_cold.h: section + noinline) puts load-time functions in the cart
    HOSTCOLD section; they execute from cart RAM. Use only for code that runs
    after `ram_cart_load_host_cold()` (main, right after the cart claim). This
    batch's loaders (+3.3 KB) had pushed `.bss` 512 B over the SGL base.
    HOSTCOLD is 20,480 B; 18,976 used. A forward declaration of a static cold
    function may omit the attribute; the definition must carry it.

120. **Music level tables are 32 KB chunks.** `music.c` `levels[]` /
    `pending_levels[]` are chunk arrays (byte b at `[b >> 15][b & 32767]`),
    `levels_live` gates the vblank reader. Test fixtures that poke music.c
    internals set `levels[0]` + `levels_live`, never assign `levels`.

121. **Scene object limits.** `OOT_SCENE_MAX_OBJECTS` 32 is the per-scene union
    (layer-mask width; Lon Lon Ranch lists 32 and was rejected at 30). One
    layer may name at most 30 (ObjectContext 32 slots minus keep and Player
    stub); the importer fails the scene otherwise.
122. **Area music must cover engine requests (2026-10-13).** `build_area_music.py`
    scanned actor/scene sources only. `z_message` plays the ocarina song fanfares
    (0x25, 0x35, 0x36, 0x44-0x49), so those had no bank. Song of Time after Field
    gave host fatal `41554446` (AUDF) `48`: `music_area_fanfare` failed. It now
    also scans `src/code/*.c` (minus seq 0, the SFX sequence); see
    `tests/test_area_music_routes.py`. These fanfares use Soundfont 0 (SFX
    font, 247 samples, `Disable` envelopes, `SampleNNN.half.wav`). Now
    `load_font(used=...)` loads only the samples played (font 0 only, so
    other banks stay byte-identical), and envelopes stop at the first
    non-Point entry. Each fanfare is about 46 KB PCM.
123. **`build/clean10-verify.py` hard-codes an old Debug ISO hash.** Copied
    Clean scripts die there after a good build (the restore trap still runs).
    `build/clean16-build.sh` drops it and prints the md5. Back up the current
    `game-clean.iso` before any Clean rebuild.
