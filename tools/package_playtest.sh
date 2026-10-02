#!/usr/bin/env bash
# Package the Clean image for private dev playtesters into playtest/<name>.zip.
# Build first: (cd game && ./build.sh --clean). Not a public release.
# Bundles the draw-cap-fixed Kronos (stock Kronos freezes; game/docs/BUILD.md
# gotcha 17) with a settings file stripped of local paths, cart type preset.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build="$root/game/build"
kronos="${KRONOS_DIR:-$root/../dosei-legend/game/build/kronos-draw-fix}"
# WSL git cannot read this worktree (.git holds a Windows path): pass OOT_SAT_REV.
rev="${OOT_SAT_REV:-$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo local)}"
stamp="$(date +%Y%m%d)-$rev"
name="oot-sat-playtest-$stamp"
out="$root/playtest"
stage="$out/$name"

[ -f "$build/game-clean.iso" ] || { echo "missing game-clean.iso: run ./build.sh --clean" >&2; exit 1; }
rm -rf "$stage" && mkdir -p "$stage/game" "$stage/kronos"

# Disc: the cue names its files relatively, so keep the names unchanged.
cp "$build/game-clean.cue" "$build/game-clean.iso" "$stage/game/"
for track in $(grep -o 'TRACK[0-9]*\.BIN' "$build/game-clean.cue"); do
    cp "$build/$track" "$stage/game/"
done

# Emulator: runtime files only (no build leftovers), plus the patched source.
for f in "$kronos"/*.exe "$kronos"/*.dll; do
    case "$f" in *.bak*) continue ;; esac
    cp "$f" "$stage/kronos/"
done
cp -r "$kronos/platforms" "$stage/kronos/"
cp "$kronos/vdp1.c" "$stage/kronos/vdp1-draw-cap-fix.c"
sed -e 's|^General\\Bios=.*|General\\Bios=|' \
    -e 's|^General\\SaveStates=.*|General\\SaveStates=|' \
    -e 's|^General\\ScreenshotsDirectory=.*|General\\ScreenshotsDirectory=|' \
    -e 's|^Memory\\Path=.*|Memory\\Path=|' \
    "$kronos/kronos.ini" > "$stage/kronos/kronos.ini"
if grep -qiE 'jilte|Workspace-Claude' "$stage/kronos/kronos.ini"; then
    echo "kronos.ini still contains local paths" >&2; exit 1
fi

cp "$root/tools/playtest_readme.txt" "$stage/README.txt"
sed -i "s|@BUILD@|$stamp|" "$stage/README.txt"

(cd "$out" && rm -f "$name.zip" && zip -qr "$name.zip" "$name")
rm -rf "$stage"
echo "packaged: $out/$name.zip"
