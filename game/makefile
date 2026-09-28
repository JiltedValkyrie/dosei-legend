#
# Isolated Jo Engine / SGL Kokiri viewer
#
# Objects are redirected into this project's private obj/ tree so the shared
# SDK at ../../joengine is never written to. See docs/JOENGINE_PORT.md step 1.
#

JO_COMPILE_WITH_VIDEO_MODULE = 0
# Backup RAM holds the save files. See docs/OOT_PROGRESSION_PLAN.md phase 2.
JO_COMPILE_WITH_BACKUP_MODULE = 1
JO_COMPILE_WITH_TGA_MODULE = 0
JO_COMPILE_WITH_AUDIO_MODULE = 0
JO_COMPILE_WITH_3D_MODULE = 1
JO_COMPILE_WITH_PSEUDO_MODE7_MODULE = 0
JO_COMPILE_WITH_EFFECTS_MODULE = 0
JO_COMPILE_WITH_FAST_BUT_LESS_ACCURATE_MATH = 0
# The 4 MB RAM expansion cart is REQUIRED, not optional: the game refuses to run
# without it (src/ram_cart.c). On by default in the SDK makefile; stated here so
# it cannot be switched off by accident.
JO_COMPILE_WITH_RAM_CARD_MODULE = 1
JO_DEBUG = 1
HIRES ?= 0
CLEAN_TEST ?= 0
ifeq ($(OPENING_CHECK),1)
override TARGET = build/opening-check.elf
OBJDIR = build/obj-opening-check
else ifeq ($(CLEAN_TEST),1)
override TARGET = build/game-clean.elf
OBJDIR = build/obj-clean
else ifeq ($(HIRES),1)
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
# 2026-09-26: 2800 -> 2400 frees 8 KB of work RAM (20 B a slot). Streaming
# peak = resident (Link 143 + icons) + largest room bank (S1R1 1496) +
# cutscene-actor uploads; the load guards in kokiri_sgl.c still refuse any
# overrun loudly. Standard HUD row 27 shows the live peak (sp).
JO_MAX_SPRITE = 2400

# The project-local SGL work area (generated/sglarea.o) is laid out from the
# top of work RAM downwards and needs .bss to end below its base. The stock
# 384 KB malloc arena sits in .bss and is nearly unused -- textures are read
# straight into VDP1 VRAM -- so trade some of it for that headroom. Collision
# and title data are intended to come out of what remains.
#
# Trimmed again for Link's animation: the clip tables and the skinned POINT
# table live below the same boundary, so they compete with this arena. Known
# demand is the 16 KB collision index plus a 1 KB background strip, and Jo
# itself allocates only small blocks (font, fs read buffers). 176 KB leaves
# roughly ten times the measured demand; the A-button overlay prints
# jo_memory_usage_percent() so the real figure can be checked in Kronos.
# Overridable: the authored quad scene needs a bigger SGL polygon table, and
# both live below the same boundary. Measured demand is ~11 KB (the A-button
# overlay prints jo_memory_usage_percent(), which reads 6% of 176 KB), so a
# smaller arena still leaves several times the real figure.
#
# Trimmed again for the opening cutscenes. Their const tables (camera event
# lists, the message text and its coloured runs) live in .rodata, which sits
# below the same boundary, and they had taken the normal variant's gap down to
# 2,608 bytes. Known arena demand is the 16 KB collision index, the largest
# cutscene camera track at about 13 KB, a 1 KB background strip and Jo's small
# blocks -- roughly 32 KB. 128 KB still leaves about four times that, and buys
# back 48 KB of boundary headroom.
# Trimmed again for the dream's polygon budget. Large allocations now come
# from the 4 MB cart (src/ram_cart.c registers both banks with jo_malloc), so
# this work-RAM arena only has to cover Jo's own small blocks and the
# collision index -- and every byte it gives back buys SGL work area, which
# must live in work RAM and is what caps polygons per frame.
# Resident opening sound control uses a few more bytes of work RAM; large
# scene allocations already use the expansion cart.
# Demo plan M0 (2026-09-25): actor pool + collide + area SFX code took ~4.7 KB
# below the boundary. Known arena demand stays ~32 KB (collision index 16 KB,
# largest camera track ~13 KB, small blocks); 52 KB keeps >1.5x that.
# Header-complete rebuild + permanent shot skip crossed the normal boundary
# by 16 bytes. Keep ~2 KB clear; jo_malloc spills into the cart zones.
JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC ?= 51200

SRCS = src/main.c src/ram_cart.c src/game_mode.c src/message.c src/cutscene.c src/cutscene_actor.c src/save_state.c src/actor_sys.c src/attention.c src/karebaba.c src/karebaba_draw.c src/game_over.c src/collide.c src/save_file.c src/save_device.c src/ui_preferences.c src/file_select.c src/scene_flow.c src/kokiri_sgl.c ../shared/lib/music/music.c src/music_banks.c src/demo.c src/navi.c src/player_input.c src/gameplay.c src/dialogue_text.c src/text_pool.c src/minimap.c src/health_hud.c src/pause_windows.c src/pause_window_state.c src/cdda.c src/action_audio.c src/demo_camera.c src/demo_collision.c src/demo_follow.c src/link_anim.c src/link_anim_state.c src/player_air.c src/player_bg.c src/player_climb.c src/player_crawl.c src/frame_timer.c build/generated/kokiri_scene.c build/generated/kokiri_textures.c build/generated/link_scene.c build/generated/link_textures.c build/generated/link_clips.c build/generated/scene_table.c build/generated/kokiri_actors.c build/generated/kokiri_dialogue.c build/generated/cutscenes.c
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
_CCFLAGS += -Ibuild/generated -Isrc -Ilevels/kokiri/assets/audio -Iassets/audio/cutscenes -I../shared/assets/audio/title -I../shared/lib/camera -I../shared/lib/collision -I../shared/lib/music
_CCFLAGS += -include src/video_mode.h
# Link's per-frame clip tables come from LINKANIM.BIN (cart), not .rodata.
_CCFLAGS += -DLINK_FRAMES_FROM_DISC
ifeq ($(CLEAN_TEST),1)
_CCFLAGS += -DDOSEI_CLEAN_TEST
endif
ifeq ($(HIRES),1)
_CCFLAGS += -DDOSEI_HIRES
endif
ifeq ($(TEXTURE_PROBE),1)
_CCFLAGS += -DDOSEI_TEXTURE_PROBE
endif
ifneq ($(FOREST_FAR),)
_CCFLAGS += -DDOSEI_FOREST_FAR=$(FOREST_FAR)
endif
ifeq ($(WARP_PROBE),1)
_CCFLAGS += -DDOSEI_WARP_PROBE
endif
# Boot straight into one cutscene, for looking at it without the opening.
# Diagnostic only; never set for a player disc.
ifneq ($(CUTSCENE_PROBE),)
_CCFLAGS += -DDOSEI_CUTSCENE_PROBE=$(CUTSCENE_PROBE)
ifeq ($(CUTSCENE_PROBE_AUTO),1)
_CCFLAGS += -DDOSEI_CUTSCENE_PROBE_AUTO
endif
ifneq ($(CUTSCENE_PROBE_FRAME),)
_CCFLAGS += -DDOSEI_CUTSCENE_PROBE_FRAME=$(CUTSCENE_PROBE_FRAME)
endif
endif
ifneq ($(filter 1 2 3 4 5,$(PERF_PROBE)),)
_CCFLAGS += -DDOSEI_PERF_PROBE=$(PERF_PROBE)
endif

# Never retain a fixed-view callback in a subsequent normal build.
.PHONY: perf_mode_check
# kokiri_sgl.o carries the warp probe, so it must recompile too or a
# probe build could linger in a later normal disc.
$(OBJDIR)/main.o $(OBJDIR)/demo.o $(OBJDIR)/kokiri_sgl.o: perf_mode_check
$(OBJDIR)/main.o $(OBJDIR)/demo.o $(OBJDIR)/kokiri_sgl.o $(OBJDIR)/frame_timer.o: src/frame_timer.h
$(OBJDIR)/kokiri_sgl.o: src/scene_actor_order.h src/actor_order.h src/sgl_order_queue.h

# --- keep build products inside this project -------------------------------
# The stock makefile derives OBJS as $(SRCS:.c=.o) and compiles via a .c.o
# suffix rule, which would drop engine objects straight into the shared
# jo_engine/ directory. Its $(TARGET) prerequisites are already expanded by the
# time the include returns, so redefining OBJS alone cannot redirect them.
# Instead declare our own link/convert targets against an obj/ object list and
# cancel the inherited suffix rule so it can never fire on an SDK source.
SRCS += src/push_block.c src/player_push.c src/player_lift.c src/player_slope.c src/player_water.c src/player_camera.c
MY_OBJS = $(patsubst %.c,$(OBJDIR)/%.o,$(notdir $(SRCS)))
# Header layout changes must rebuild every consumer (save v2 otherwise wrote
# 300 bytes into a stale 220-byte stack buffer). makefile bootstraps .d files
# for existing objects and also invalidates compiled configuration changes.
$(MY_OBJS): build/generated/toolchain.stamp makefile
-include $(MY_OBJS:.o=.d)

# The parent expanded $(TARGET)'s prerequisites from its own OBJS while reading
# its rules; make unions prerequisites across rules for the same target, so
# those SDK paths must be given a rule of their own. Point each one at the
# corresponding obj/ file instead of compiling in place.
$(foreach s,$(SRCS),$(eval $(s:.c=.o): $(OBJDIR)/$(notdir $(s:.c=.o))))

%.o: %.c

$(OBJDIR)/%.o: src/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/demo_camera.o: ../shared/lib/camera/kokiri_camera.c ../shared/lib/camera/kokiri_camera.h ../shared/lib/collision/kokiri_collision.h
$(OBJDIR)/demo_follow.o: ../shared/lib/camera/oot_follow.c ../shared/lib/camera/oot_follow.h ../shared/lib/camera/kokiri_camera.h
$(OBJDIR)/demo_collision.o: ../shared/lib/collision/kokiri_collision.c ../shared/lib/collision/kokiri_collision.h
$(OBJDIR)/demo.o: build/generated/texture_probe.h build/generated/title_paths.h src/input_edge.h
$(OBJDIR)/cutscene.o $(OBJDIR)/kokiri_sgl.o: src/vdp1_draw_wait.h
$(OBJDIR)/main.o $(OBJDIR)/kokiri_sgl.o: build/generated/kokiri_scene.h build/generated/link_scene.h build/generated/vdp1_layout.h
$(OBJDIR)/kokiri_sgl.o $(OBJDIR)/kokiri_actors.o $(OBJDIR)/gameplay.o $(OBJDIR)/demo.o $(OBJDIR)/main.o $(OBJDIR)/kokiri_dialogue.o $(OBJDIR)/dialogue_text.o: build/generated/kokiri_actors.h build/generated/kokiri_dialogue.h src/gameplay.h
# The skinner and its clip tables are generated by build_link_model.py --animate.
$(OBJDIR)/link_anim.o $(OBJDIR)/link_anim_state.o $(OBJDIR)/kokiri_sgl.o: build/generated/link_clips.h build/generated/link_scene.h
$(OBJDIR)/kokiri_sgl.o: build/generated/link_equipment.h
# Cutscene tables are generated by build_cutscenes.py from the decomp data.
$(OBJDIR)/message.o $(OBJDIR)/cutscene.o $(OBJDIR)/cutscenes.o $(OBJDIR)/demo.o $(OBJDIR)/main.o: build/generated/cutscenes.h src/message.h src/cutscene.h
$(OBJDIR)/minimap.o $(OBJDIR)/main.o: build/generated/minimap_data.h src/minimap.h
$(OBJDIR)/minimap.o: build/generated/gameplay_hud_data.h src/gameplay_hud_state.h

$(OBJDIR)/music.o: ../shared/lib/music/music.c ../shared/lib/music/music.h src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/core.o: makefile

# Observe every SDK allocation from boot, without patching the shared SDK.
# heap_profile.c includes the selected allocator implementation privately.
$(OBJDIR)/malloc.o: src/heap_profile.c src/heap_profile.h $(JO_ENGINE_SRC_DIR)/malloc.c src/video_mode.h | $(OBJDIR)
	$(CC) src/heap_profile.c $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -I$(JO_ENGINE_SRC_DIR) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/%.o: build/generated/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/%.o: $(JO_ENGINE_SRC_DIR)/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(TARGET): $(SYSOBJS) $(MY_OBJS) $(MAKEFILE) $(LDFILE)
	$(CC) $(LDFLAGS) $(SYSOBJS) $(MY_OBJS) $(LIBS) -o $@

$(TARGET1): $(TARGET)
	$(CONV) -O binary $(TARGET) $(TARGET1)

# The parent's ISO recipe ends in an undefined $(ENTRYPOINT), which reaches
# mkisofs as a stray empty argument under make's shell and aborts with
# "Missing pathspec". Build the image here with an explicit pathspec instead.
# Link's cold POLYGON/ATTR tables (BUG-039): compiled by the real compiler,
# never linked, .rodata objcopied to the disc and loaded onto the cart.
# -fno-lto so the object carries real sections, not LTO bytecode.
$(ASSETS_DIR)/LINKMESH.BIN: build/generated/link_mesh.c build/generated/link_scene.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -fno-lto -o $(OBJDIR)/link_mesh_blob.o
	$(CONV) -O binary -j .rodata $(OBJDIR)/link_mesh_blob.o $@

$(ASSETS_DIR)/LINKTEX.BIN: build/generated/link_tex.c build/generated/link_scene.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -fno-lto -o $(OBJDIR)/link_tex_blob.o
	$(CONV) -O binary -j .rodata $(OBJDIR)/link_tex_blob.o $@

$(TARGET2): $(TARGET1) $(ASSETS_DIR)/LINKMESH.BIN $(ASSETS_DIR)/LINKTEX.BIN
	$(CONV) -O binary $(TARGET) $(ASSETS_DIR)/0.bin
	$(MKISOFS) -quiet -sysid "SEGA SATURN" -volid "KOKIRIJO" -volset "KOKIRIJO" 		-sectype 2352 -publisher "SEGA ENTERPRISES, LTD." 		-preparer "SEGA ENTERPRISES, LTD." -appid "KOKIRIJO" 		-abstract "$(ASSETS_DIR)/ABS.TXT" -copyright "$(ASSETS_DIR)/CPY.TXT" 		-biblio "$(ASSETS_DIR)/BIB.TXT" -generic-boot $(IPFILE) 		-full-iso9660-filenames -o $(TARGET2) $(ASSETS_DIR)

$(TARGET3): $(TARGET2)
	"$(PYTHON)" tools/write_cue.py $(TARGET2) $(TARGET3)

clean:
	$(RM) $(OBJDIR) $(TARGET) $(TARGET1) $(TARGET2) $(TARGET3) $(MPFILE) build/cd/0.bin

$(OBJDIR)/action_audio.o: build/generated/action_audio_data.h build/generated/opening_audio_data.h
$(OBJDIR)/action_audio.o $(OBJDIR)/demo.o $(OBJDIR)/main.o: src/action_audio.h
$(OBJDIR)/action_audio.o: ../shared/lib/music/music.h src/gameplay.h

$(OBJDIR)/pause_windows.o $(OBJDIR)/gameplay.o: src/pause_window_state.h

$(OBJDIR)/pause_windows.o: build/generated/pause_cursor_data.h
