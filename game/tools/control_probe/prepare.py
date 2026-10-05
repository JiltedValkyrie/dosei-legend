"""Snapshot Opus's probe, add only isolated control/trace hooks, write build script."""
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


def main():
    if DEST.exists():
        raise SystemExit(f"Snapshot already exists; preserve it: {DEST}")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    # No SDK symlinks or old object trees. Fresh target objects are mandatory.
    shutil.copytree(SOURCE, DEST, ignore=shutil.ignore_patterns(
        "build", ".git", "__pycache__", "node_modules"))
    for name in ("cd", "generated", "oot-core"):
        shutil.copytree(SOURCE / "game/build" / name, DEST / "game/build" / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    for p in (SOURCE / "game/build").glob("TRACK0*.*"):
        shutil.copy2(p, DEST / "game/build" / p.name)
    manifest = {"source": str(SOURCE), "files": {}}
    for name in ("main.c", "demo.c", "kokiri_sgl.c", "player_input.c"):
        manifest["files"][name] = digest(SOURCE / "game/src" / name)
    for name in ("game-clean.iso", "game.iso"):
        p = ROOT / "game/build" / name
        if p.exists():
            manifest["files"]["preserved/" + name] = digest(p)
    for p in (SOURCE / "game/build/cd").glob("*.STM"):
        manifest["files"]["cd/" + p.name] = digest(p)
    for p in HERE.glob("control_*"):
        if p.suffix in (".h", ".inc"):
            shutil.copy2(p, DEST / "game/src" / p.name)
    game = DEST / "game"
    for name in ("main.c", "demo.c", "kokiri_sgl.c"):
        replace(game / "src" / name, '#include "demo.h"',
                '#include "demo.h"\n#include "control_probe.h"')
    replace(game / "src/main.c", "    demo_update();", "    control_trace_finish();\n    demo_update();")
    replace(game / "src/main.c", "    core_low_init();",
            "    core_low_init();\n    memset((void *)CONTROL, 0, sizeof(*CONTROL));")
    replace(game / "src/main.c", 'static void __attribute__((optimize("Os"))) viewer_hud(void)\n{',
            'static void __attribute__((optimize("Os"))) viewer_hud(void)\n{\n'
            '    if (CONTROL->hud) {\n'
            '        jo_printf(0,0,"ASTRA f%u step%u req%u    ",CONTROL->frame,CONTROL->sim_steps,CONTROL->ack);\n'
            '        jo_printf(0,1,"FEET %d %d %d %s    ",demo_link.x,demo_link.y-90,demo_link.z,oot_follow_legacy()?"FAR":"OOT");\n'
            '    }\n    return; /* Detailed traces are read by the host, not drawn over the ground. */')
    # The game owns step timing and pad delivery; physical/global input is ignored.
    replace(game / "src/demo.c", "static void demo_vblank(void)\n{",
            "static void demo_vblank(void)\n{\n    return; /* Controlled probe: input and ticks come from mailbox. */")
    replace(game / "src/demo.c", "void demo_update(void)\n{",
            '#include "control_demo.inc"\n\nvoid demo_update(void)\n{\n    control_begin();')
    replace(game / "src/demo.c", "    unsigned int now = ticks, elapsed = now - previous_tick, steps;",
            "    unsigned int now = ticks, elapsed = now - previous_tick, steps;\n"
            "    if (!elapsed) { control_end(); return; }")
    replace(game / "src/demo.c", "    story_owl_camera();", "    story_owl_camera();\n    control_end();")
    # WARP_PROBE is disabled. The new trace uses its own previous-frame metadata.
    replace(game / "src/kokiri_sgl.c", "    frame_timer_end(FRAME_PHASE_PREP);\n    submit(&kokiri_pdata, 1u);",
            "    frame_timer_end(FRAME_PHASE_PREP);\n    submit(&kokiri_pdata, 1u);\n    control_trace_prepare(visible);")
    # Definitions need the file's private geometry tables; the header provides prototypes.
    with (game / "src/kokiri_sgl.c").open("a", encoding="utf-8", newline="\n") as out:
        out.write('\n#include "control_trace.inc"\n')
    script = f'''#!/usr/bin/env bash
set -euo pipefail
export SH_ELF_LINUX=/mnt/d/Workspace-Claude/saturn-homebrew/sh-elf-9.3-linux
cd /mnt/d/Workspace-Claude/saturn-homebrew/oot-sat/game/build/astra-control/oot-sat/game
./build.sh --quick OOT_CORE=1 > ../../build.log 2>&1
'''
    (DEST.parent / "build.sh").write_text(script, encoding="utf-8", newline="\n")
    (DEST.parent / "baseline.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(DEST)


if __name__ == "__main__":
    main()
