"""Snapshot a checkout, add only isolated control/trace hooks, write build script.

Default: Opus's probe -> astra-control, quick build reusing its assets.
Square retopo: --source <repo root> --dest game/build/square-retopo/oot-sat
--full --layout field-square-184 copies the working tree (no build outputs),
selects that layout in the copy only and runs a full asset build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "game/build/probe/oot-sat"
DEST = ROOT / "game/build/astra-control/oot-sat"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def replace(path, old, new):
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one patch site: {path}: {old[:60]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def wsl(path):
    path = Path(path).resolve()
    return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]


def install_hooks(game):
    """Install into freshly copied source files; refuse duplicate/changed hooks."""
    for p in HERE.glob("control_*"):
        if p.suffix in (".h", ".inc"):
            shutil.copy2(p, game / "src" / p.name)
    for name in ("main.c", "recomp.c", "kokiri_sgl.c"):
        replace(game / "src" / name, '#include "recomp.h"',
                '#include "recomp.h"\n#include "control_probe.h"')
    replace(game / "src/main.c", "    recomp_update();", "    control_trace_finish();\n    recomp_update();")
    replace(game / "src/main.c", "    core_low_init();",
            "    core_low_init();\n    memset((void *)CONTROL, 0, sizeof(*CONTROL));")
    replace(game / "src/main.c", 'static void __attribute__((optimize("Os"))) viewer_hud(void)\n{',
            'static void __attribute__((optimize("Os"))) viewer_hud(void)\n{\n'
            '    if (CONTROL->hud) {\n'
            '        jo_printf(0,0,"ASTRA f%u step%u req%u    ",CONTROL->frame,CONTROL->sim_steps,CONTROL->ack);\n'
            '        jo_printf(0,1,"FEET %d %d %d %s    ",recomp_link.x,recomp_link.y-90,recomp_link.z,oot_follow_legacy()?"FAR":"OOT");\n'
            '    }\n    return; /* Detailed traces are read by the host, not drawn over the ground. */')
    # The game owns step timing and pad delivery; physical/global input is ignored.
    replace(game / "src/recomp.c", "static void recomp_vblank(void)\n{",
            "static void recomp_vblank(void)\n{\n    return; /* Controlled probe: input and ticks come from mailbox. */")
    replace(game / "src/recomp.c", "void recomp_update(void)\n{",
            '#include "control_recomp.inc"\n\nvoid recomp_update(void)\n{\n    control_begin();')
    replace(game / "src/recomp.c", "    unsigned int now = ticks, elapsed = now - previous_tick, steps;",
            "    unsigned int now = ticks, elapsed = now - previous_tick, steps;\n"
            "    if (!elapsed) { control_end(); return; }")
    replace(game / "src/recomp.c", "    story_owl_camera();", "    story_owl_camera();\n    control_end();")
    replace(game / "src/recomp.c", "    if (jo_is_pad1_available()) {",
            "    if (true) { /* Diagnostic mailbox is the connected pad. */")
    # WARP_PROBE is disabled. The new trace uses its own previous-frame metadata.
    replace(game / "src/kokiri_sgl.c", "    frame_timer_end(FRAME_PHASE_PREP);\n    submit(&kokiri_pdata, 1u);",
            "    frame_timer_end(FRAME_PHASE_PREP);\n    submit(&kokiri_pdata, 1u);\n    control_trace_prepare(visible);")
    # Definitions need the file's private geometry tables; the header provides prototypes.
    with (game / "src/kokiri_sgl.c").open("a", encoding="utf-8", newline="\n") as out:
        out.write('\n#include "control_trace.inc"\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--dest", type=Path, default=DEST)
    ap.add_argument("--full", action="store_true",
                    help="full asset build; copy no build outputs except CD audio tracks")
    ap.add_argument("--layout", help="layout variant selected inside the copy only")
    args = ap.parse_args()
    source, dest = args.source.resolve(), args.dest.resolve()
    if dest.exists():
        raise SystemExit(f"Snapshot already exists; preserve it: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # No SDK symlinks or old object trees. Fresh target objects are mandatory.
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(
        "build", ".git", "__pycache__", "node_modules"))
    (dest / "game/build").mkdir(parents=True, exist_ok=True)
    if not args.full:
        for name in ("cd", "generated", "oot-core"):
            shutil.copytree(source / "game/build" / name, dest / "game/build" / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
    if args.full and (source / "shared/build").is_dir():
        # Extracted audio sources (build_cdda); a full build reads them.
        shutil.copytree(source / "shared/build", dest / "shared/build",
                        ignore=shutil.ignore_patterns("__pycache__"))
    for p in (source / "game/build").glob("TRACK0*.*"):
        shutil.copy2(p, dest / "game/build" / p.name)
    if not list((dest / "game/build").glob("TRACK0*.BIN")):
        raise SystemExit("No CD audio tracks copied; the CUE would not be runnable")
    manifest = {"source": str(source), "full": args.full, "layout": args.layout, "files": {}}
    for name in ("main.c", "recomp.c", "kokiri_sgl.c", "player_input.c"):
        manifest["files"][name] = digest(source / "game/src" / name)
    for name in ("game-clean.iso", "game.iso"):
        p = ROOT / "game/build" / name
        if p.exists():
            manifest["files"]["preserved/" + name] = digest(p)
    for p in (source / "game/build/cd").glob("*.STM"):
        manifest["files"]["cd/" + p.name] = digest(p)
    if args.layout:
        variant = dest / "game/assets/layouts/variants" / (args.layout + ".json")
        if not variant.is_file():
            raise SystemExit(f"Layout variant missing in the copy: {variant}")
        (dest / "game/assets/layouts/selection.json").write_text(
            json.dumps({"version": 1, "layout": args.layout}, indent=2) + "\n", encoding="utf-8")
        manifest["files"]["layout/" + args.layout] = digest(variant)
    game = dest / "game"
    install_hooks(game)
    quick = "" if args.full else "--quick "
    script = f'''#!/usr/bin/env bash
set -euo pipefail
export SH_ELF_LINUX=/mnt/d/Workspace-Claude/saturn-homebrew/sh-elf-9.3-linux
cd {wsl(game)}
./build.sh {quick}OOT_CORE=1 > ../../build.log 2>&1
'''
    (dest.parent / "build.sh").write_text(script, encoding="utf-8", newline="\n")
    (dest.parent / "baseline.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
