# Developer setup (Windows)

Open `launch-game.bat`, then **Config > Paths...**. Browse to your own tools,
click **Validate paths / ROM**, then **Save**. Settings go in the repository's
`config.ini` (git-ignored). No SDK files are modified. You can also copy
[`config.example.ini`](../../config.example.ini) to `config.ini` and edit it.
Paths may be absolute or relative to the repository root; do not quote them.

## Dependencies

| Setting | Select |
| --- | --- |
| Jo Engine SDK root | The directory containing `jo_engine/` and `Compiler/`. The Windows SH compiler and `Compiler/COMMON/SGL_302j` are required. |
| MSYS2 root | An MSYS2 installation containing `usr/bin/bash.exe` and `usr/bin/make.exe`. Install `make` in its MSYS shell with `pacman -S make` if needed. |
| Python executable | Windows Python 3.10+ (`python.exe`), with Pillow installed using that Python's `-m pip install Pillow`. Do not select `py.exe` or a Microsoft Store installation stub. |
| Kronos executable | Your local `kronos.exe`. Keep its supplied plugins and libraries together. |
| Kronos DLLs | Optional additional DLL directory. Our MSYS2 build uses `mingw64/bin` for OpenAL, SDL2 and compiler runtime DLLs. Leave blank for a self-contained Kronos release. Use libraries matching your emulator build. |
| Saturn BIOS | Your own Saturn BIOS file. This project has been run with the European v1.00 BIOS. |

## Mednafen (optional, most accurate)

Config > **Paths and emulator...** > **Emulator** tab: pick Kronos or Mednafen,
set `mednafen.exe`, cartridge (keep `extram4`: game needs 4 MB RAM cart),
fullscreen, extra args. Saved under `[Emulator]` in `config.ini`.
Mednafen has no menu: double-click `mednafen.exe` alone just quits. Launcher passes the CUE.
Put your BIOS in `<mednafen>/firmware/`: `sega_101.bin` (JP 1.01) and
`mpr-17933.bin` (US/EU 1.00). Tab shows OK/MISSING. In Mednafen: Esc quit,
Alt+Enter fullscreen, Alt+Shift+1 map pad 1.
| zeldaret/oot checkout | The repository root described below, not its `src` or `baseroms` directory. |
| US 1.2 ROM directory | Folder containing your original US NTSC 1.2 `.z64`. Blank means `<oot checkout>/baseroms/ntsc-1.2`. |

Jo Engine supplies SGL and the SH compiler; there is no separate libyaul or
N64 compiler dependency for the active Saturn build. Reusable game libraries
and staged music/title assets are already in `shared/` and `game/`.
The project checks the original SGL work-area object's identity before patching
a **project-local copy**. An incompatible SDK is rejected; do not bypass that
check. Use a compatible SGL_302j installation rather than editing the shared SDK.

SDK/MSYS2 paths containing spaces are supported through generated directory
junctions inside `game/build/dependencies/`. These point to read-only inputs;
objects still go into `game/build/obj*`. Do not recursively clean through those
junctions with tools that follow links.

## OoT decomp and ROM

Use the upstream **[zeldaret/oot decomp](https://github.com/zeldaret/oot)**.
Known working revision: `c2aff68a86400830e0264a07024214671d4161a7`.

```powershell
git clone https://github.com/zeldaret/oot.git C:\dev\oot
git -C C:\dev\oot checkout c2aff68a86400830e0264a07024214671d4161a7
```

Select `C:\dev\oot` in Config. The converters read the checkout's
`baseroms/ntsc-1.2/config.yml` and `segments.csv`; you **do not need to compile
the N64 game**, install its compiler, or run its extraction setup first.

Supply your own **The Legend of Zelda: Ocarina of Time, USA NTSC revision 1.2**,
original compressed **big-endian `.z64`** ROM. Required MD5:

```text
57a9719ad547c516342e1a15d5c28c3d
```

Recommended placement:

```text
C:\dev\oot\baseroms\ntsc-1.2\baserom.z64
```

The filename can differ, but leave exactly one checksum-matching `.z64` in the
selected folder. JP/PAL, 1.0/1.1, debug, byte-swapped, patched, and decompressed
ROMs are not accepted. Renaming a different ROM does not convert it.
You may select a separate ROM directory; metadata still comes from the decomp.

**Open decomp** and **Open ROM folder** in Config open those local directories
using the displayed paths. They do not download anything. Neither ROMs nor BIOS
files are provided or linked for download.

## Build and run

After saving the configuration, from the project root:

```powershell
.\game\build.bat
.\game\build.bat -Variant hires
```

Build sequentially: both modes share generated assets and CD staging.
Alternatively use `./build.sh` or `./build.sh --hires` from `game/` in MSYS2;
that shell needs a working Windows Python on PATH to read the config initially
(or set `DOSEI_PYTHON` to its full path).

Open `launch-game.bat`, select Play Dosei Legend (Standard), Play Dosei Legend (320x480i), or Debug Mode, then **Run selected**.
Clean hides the in-game diagnostic overlay. Build it with `game/build.bat -Variant clean`.
Reopen an already-running launcher after updating its variant list.
The selector launches existing images; it does not build them. Direct launchers
`game/run-kronos.bat` and `game/run-kronos-hires.bat` use the same configuration.
Close Kronos before switching variants or rebuilding its mounted image.

Build output remains under `game/build/`. If only running an already-built
image, only Kronos, its runtime libraries, and the BIOS are needed; the SDK,
Python, decomp and ROM are build-time inputs.

## Xbox-style controller triggers (3D Control Pad) need a Kronos patch

Emulating the 3D Control Pad with an Xbox-style controller: stock Kronos
never passes LT/RT through. Its SDL joystick code treats a trigger resting
at -32768 as dead zone, so both trigger axes stay at 128 and R (shield) and
L (look) never press. Kronos also has no plain R/L button entry for the 3D
pad; triggers are axes only.

Fix: apply `tools/launcher/kronos-sdl-trigger.patch` to Kronos source
(`git apply` from the Kronos repo root), rebuild Kronos, then in the 3D
Control Pad setup bind LT to **Axis L Trigger** and RT to **Axis R
Trigger**. Keep bumpers on real buttons (for example Z and C). The
standard-build debug row `pad ... R### L###` shows 0 at rest and 176 or
more on a pull. Without the patch, use the pad's digital mode or a
Standard Pad, where R is shield as usual.

## Missing libopenal-1.dll

Use the project launcher with `kronos_dlls` set to the matching Kronos runtime
directory (this workstation: `C:/msys64/mingw64/bin`). Opening a bare executable
does not inherit the launcher's configured DLL path. A locally built Kronos may
also need its matching runtime DLL dependencies beside the executable and Qt's
`platforms/qwindows.dll` plugin. Keep these from the same installed toolchain;
do not fetch individual DLLs from download sites. The local `kronos-draw-fix`
copy now has these dependencies staged beside it.
