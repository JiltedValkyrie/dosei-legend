#
# Isolated Jo Engine / SGL Kokiri viewer
#
# Objects are redirected into this project's private obj/ tree so the shared
# SDK at ../../joengine is never written to. See docs/JOENGINE_PORT.md step 1.
#

JO_COMPILE_WITH_VIDEO_MODULE = 0
JO_COMPILE_WITH_BACKUP_MODULE = 0
JO_COMPILE_WITH_TGA_MODULE = 0
JO_COMPILE_WITH_AUDIO_MODULE = 0
JO_COMPILE_WITH_3D_MODULE = 1
JO_COMPILE_WITH_PSEUDO_MODE7_MODULE = 0
JO_COMPILE_WITH_EFFECTS_MODULE = 0
JO_COMPILE_WITH_FAST_BUT_LESS_ACCURATE_MATH = 0
JO_DEBUG = 1
HIRES ?= 0
ifeq ($(HIRES),1)
override TARGET = build/game-hires.elf
OBJDIR = build/obj-hires
else
override TARGET = build/game.elf
OBJDIR = build/obj
endif

# One SGL TEXTURE slot per unique Kokiri tile (1801) plus Jo's reserved entry
# 0. The stock default is 255, which __jo_sprite_def would overflow.
# One SGL TEXTURE slot per unique tile across EVERY mesh, plus Jo's reserved
# entry 0. Forest 1801 + Link 419 + 1 = 2221 today; the margin is because a
# texture change can move Link's tile count, and overrunning this aborts into
# Jo's error handler at load. tests/test_build_sgl_scene.py checks the sum.
JO_MAX_SPRITE = 2400

# The project-local SGL work area (generated/sglarea.o) is laid out from the
# top of work RAM downwards and needs .bss to end below its base. The stock
# 384 KB malloc arena sits in .bss and is nearly unused -- textures are read
# straight into VDP1 VRAM -- so trade some of it for that headroom. Collision
# and title data are intended to come out of what remains.
JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC = 221184

SRCS = src/main.c src/kokiri_sgl.c ../shared/lib/music/music.c src/music_banks.c src/demo.c src/demo_camera.c src/demo_collision.c build/generated/kokiri_scene.c build/generated/kokiri_textures.c build/generated/link_scene.c build/generated/link_textures.c
override ASSETS_DIR = ./build/cd

JO_ENGINE_SRC_DIR = ../../joengine/jo_engine
COMPILER_DIR = ../../joengine/Compiler
PYTHON ?= python

# The toolchain ships an ancient msys-1.0 sh.exe in "Other Utilities", which is
# first on PATH during a build and mangles arguments passed to the cygwin
# mkisofs (every pathspec arrives empty -> "Missing pathspec"). Drive recipes
# with MSYS2 bash instead. Override on the command line if bash lives elsewhere.
SHELL := C:/msys64/usr/bin/bash.exe

include $(COMPILER_DIR)/COMMON/jo_engine_makefile

# Link our patched work area instead of the SDK's, so MaxPolygons covers the
# scene's 2060-polygon list. The shared SDK object is only ever read.
SYSOBJS = build/generated/sglarea.o

# The converter writes kokiri_scene.h into generated/.
_CCFLAGS += -Ibuild/generated -Isrc -Ilevels/kokiri/assets/audio -I../shared/assets/audio/title -I../shared/lib/camera -I../shared/lib/collision -I../shared/lib/music
_CCFLAGS += -include src/video_mode.h
ifeq ($(HIRES),1)
_CCFLAGS += -DDOSEI_HIRES
endif
ifeq ($(TEXTURE_PROBE),1)
_CCFLAGS += -DDOSEI_TEXTURE_PROBE
endif

# --- keep build products inside this project -------------------------------
# The stock makefile derives OBJS as $(SRCS:.c=.o) and compiles via a .c.o
# suffix rule, which would drop engine objects straight into the shared
# jo_engine/ directory. Its $(TARGET) prerequisites are already expanded by the
# time the include returns, so redefining OBJS alone cannot redirect them.
# Instead declare our own link/convert targets against an obj/ object list and
# cancel the inherited suffix rule so it can never fire on an SDK source.
MY_OBJS = $(patsubst %.c,$(OBJDIR)/%.o,$(notdir $(SRCS)))
$(MY_OBJS): build/generated/toolchain.stamp

# The parent expanded $(TARGET)'s prerequisites from its own OBJS while reading
# its rules; make unions prerequisites across rules for the same target, so
# those SDK paths must be given a rule of their own. Point each one at the
# corresponding obj/ file instead of compiling in place.
$(foreach s,$(SRCS),$(eval $(s:.c=.o): $(OBJDIR)/$(notdir $(s:.c=.o))))

%.o: %.c

$(OBJDIR)/%.o: src/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

$(OBJDIR)/demo_camera.o: ../shared/lib/camera/kokiri_camera.c ../shared/lib/camera/kokiri_camera.h ../shared/lib/collision/kokiri_collision.h
$(OBJDIR)/demo_collision.o: ../shared/lib/collision/kokiri_collision.c ../shared/lib/collision/kokiri_collision.h
$(OBJDIR)/demo.o: build/generated/texture_probe.h build/generated/title_paths.h
$(OBJDIR)/main.o $(OBJDIR)/kokiri_sgl.o: build/generated/kokiri_scene.h build/generated/link_scene.h build/generated/vdp1_layout.h

$(OBJDIR)/music.o: ../shared/lib/music/music.c ../shared/lib/music/music.h src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

$(OBJDIR)/%.o: build/generated/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

$(OBJDIR)/%.o: $(JO_ENGINE_SRC_DIR)/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(TARGET): $(SYSOBJS) $(MY_OBJS) $(MAKEFILE) $(LDFILE)
	$(CC) $(LDFLAGS) $(SYSOBJS) $(MY_OBJS) $(LIBS) -o $@

$(TARGET1): $(TARGET)
	$(CONV) -O binary $(TARGET) $(TARGET1)

# The parent's ISO recipe ends in an undefined $(ENTRYPOINT), which reaches
# mkisofs as a stray empty argument under make's shell and aborts with
# "Missing pathspec". Build the image here with an explicit pathspec instead.
$(TARGET2): $(TARGET1)
	$(CONV) -O binary $(TARGET) $(ASSETS_DIR)/0.bin
	$(MKISOFS) -quiet -sysid "SEGA SATURN" -volid "KOKIRIJO" -volset "KOKIRIJO" 		-sectype 2352 -publisher "SEGA ENTERPRISES, LTD." 		-preparer "SEGA ENTERPRISES, LTD." -appid "KOKIRIJO" 		-abstract "$(ASSETS_DIR)/ABS.TXT" -copyright "$(ASSETS_DIR)/CPY.TXT" 		-biblio "$(ASSETS_DIR)/BIB.TXT" -generic-boot $(IPFILE) 		-full-iso9660-filenames -o $(TARGET2) $(ASSETS_DIR)

$(TARGET3): $(TARGET2)
	"$(PYTHON)" tools/write_cue.py $(TARGET2) $(TARGET3)

clean:
	$(RM) $(OBJDIR) $(TARGET) $(TARGET1) $(TARGET2) $(TARGET3) $(MPFILE) build/cd/0.bin
