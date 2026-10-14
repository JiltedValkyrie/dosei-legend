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
else ifeq ($(BOOT_KOKIRI_TEST),1)
override TARGET = build/game-perf-kokiri.elf
OBJDIR = build/obj-perf-kokiri
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

# The SDK also uses this as GFS_Init's open-file capacity. Music streams keep
# one handle across frames; scene/cutscene reads need a second handle meanwhile.
JO_MAX_FS_BACKGROUND_JOBS = 2

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
# Recomp plan M0 (2026-09-25): actor pool + collide + area SFX code took ~4.7 KB
# below the boundary. Known arena demand stays ~32 KB (collision index 16 KB,
# largest camera track ~13 KB, small blocks); 52 KB keeps >1.5x that.
# Header-complete rebuild + permanent shot skip crossed the normal boundary
# by 16 bytes. Keep ~2 KB clear; jo_malloc spills into the cart zones.
# 2026-10-03: 47 KB (was 44 KB, peak hit the cap; still 1.47x the known ~32 KB demand) to
# give the decomp glue static RAM; overflow goes to the cart zones.
# 2026-10-04: 8 KB of it moved to a low-RAM zone (ram_low.h RAM_LOW_HEAP,
# added in ram_cart_claim_second_bank); total malloc capacity unchanged.
JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC ?= 35840

# CORE_COLLISION=1 (default with OOT_CORE=1): the core's z_bgcheck is the only
# collision world. C bg_* go through src/bg_core_shim.c, C Link's wrappers
# through src/bg_core_link.c; no C scene buffer/index/dyna carve. 0 links the
# old C library (shared/lib/collision) as the rollback. Player migration
# phase 2, docs/PLAYER_MIGRATION.md. Chosen before SRCS: jo_engine_makefile
# expands its target's objects from SRCS when included.
OOT_CORE ?= 0
CORE_COLLISION ?= $(OOT_CORE)
ifeq ($(OOT_CORE)$(CORE_COLLISION),11)
COLLISION_SRCS = src/bg_core_shim.c src/bg_core_link.c
else
COLLISION_SRCS = src/recomp_collision.c
endif
SRCS = src/main.c src/ram_cart.c src/game_mode.c src/message.c src/cutscene.c src/cutscene_actor.c src/save_state.c src/item_drop.c src/world_props.c src/world_signs.c src/world_props_draw.c src/actor_sys.c src/attention.c src/karebaba.c src/karebaba_draw.c src/game_over.c src/collide.c src/save_file.c src/save_device.c src/ui_preferences.c src/file_select.c src/scene_flow.c src/kokiri_sgl.c ../shared/lib/music/music.c src/music_banks.c src/recomp.c src/navi.c src/player_input.c src/gameplay.c src/dialogue_text.c src/text_pool.c src/minimap.c src/health_hud.c src/pause_windows.c src/pause_window_state.c src/cdda.c src/music_songs.c src/action_audio.c src/recomp_camera.c $(COLLISION_SRCS) src/recomp_follow.c src/link_anim.c src/link_anim_state.c src/player_air.c src/player_bg.c src/player_climb.c src/player_crawl.c src/frame_timer.c build/generated/kokiri_scene.c build/generated/kokiri_textures.c build/generated/link_scene.c build/generated/link_textures.c build/generated/link_clips.c build/generated/scene_table.c build/generated/kokiri_actors.c build/generated/kokiri_dialogue.c build/generated/cutscenes.c
override ASSETS_DIR = ./build/cd

JO_ENGINE_SRC_DIR = ../../joengine/jo_engine
COMPILER_DIR = ../../joengine/Compiler
PYTHON ?= python

# The toolchain ships an ancient msys-1.0 sh.exe in "Other Utilities", which is
# first on PATH during a build and mangles arguments passed to the cygwin
# mkisofs (every pathspec arrives empty -> "Missing pathspec"). Drive recipes
# with MSYS2 bash instead. Override on the command line if bash lives elsewhere.
ifeq ($(OS),Windows_NT)
SHELL := C:/msys64/usr/bin/bash.exe
else
SHELL := /bin/bash
endif

include $(COMPILER_DIR)/COMMON/jo_engine_makefile
LDFILE = sgl.linker
# Cold host tables (host_cold.h, linker section .cart) at the cart HOSTCOLD
# carve's cached alias (ram_cart.h); objcopied to HOSTCOLD.BIN, never 0.BIN.
ifeq ($(OOT_CORE),1)
HOST_CART_ADDR = 0x026D2C00
else
HOST_CART_ADDR = 0x027FB000
endif
LDFLAGS += -Xlinker --defsym -Xlinker HOST_CART_ADDR=$(HOST_CART_ADDR)

# Link our patched work area instead of the SDK's, so MaxPolygons covers the
# scene's 2060-polygon list. The shared SDK object is only ever read.
SYSOBJS = build/generated/sglarea.o

# The converter writes kokiri_scene.h into generated/.
_CCFLAGS += -Ibuild/generated -Isrc -Ilevels/kokiri/assets/audio -Iassets/audio/cutscenes -I../shared/assets/audio/title -I../shared/lib/camera -I../shared/lib/collision -I../shared/lib/music
_CCFLAGS += -include src/video_mode.h
_CCFLAGS += -DHOST_CART_ADDR=$(HOST_CART_ADDR)u
# GFS keeps an ID-only directory; names resolve through fs_low.c's exact keys.
_CCFLAGS += '-DGFS_NameToId(name)=dosei_gfs_name_to_id(name)'
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
ifeq ($(BOOT_KOKIRI_TEST),1)
_CCFLAGS += -DDOSEI_BOOT_KOKIRI_TEST
endif

# Never retain a fixed-view callback in a subsequent normal build.
.PHONY: perf_mode_check
# kokiri_sgl.o carries the warp probe, so it must recompile too or a
# probe build could linger in a later normal disc.
$(OBJDIR)/main.o $(OBJDIR)/recomp.o $(OBJDIR)/kokiri_sgl.o: perf_mode_check
$(OBJDIR)/main.o $(OBJDIR)/recomp.o $(OBJDIR)/kokiri_sgl.o $(OBJDIR)/frame_timer.o: src/frame_timer.h
$(OBJDIR)/kokiri_sgl.o: src/scene_actor_order.h src/actor_order.h src/sgl_order_queue.h

# --- keep build products inside this project -------------------------------
# The stock makefile derives OBJS as $(SRCS:.c=.o) and compiles via a .c.o
# suffix rule, which would drop engine objects straight into the shared
# jo_engine/ directory. Its $(TARGET) prerequisites are already expanded by the
# time the include returns, so redefining OBJS alone cannot redirect them.
# Instead declare our own link/convert targets against an obj/ object list and
# cancel the inherited suffix rule so it can never fire on an SDK source.
SRCS += src/push_block.c src/player_push.c src/player_lift.c src/player_slope.c src/player_water.c src/player_camera.c src/npc_draw.c
SRCS += src/npc_pose.c src/interior_mask.c src/music_area.c
# NPC sprite impostors (both variants since the 2026-10-04 RAM moves).
SRCS += src/npc_sprite.c
SRCS += src/player_items.c src/dungeon_doors.c src/dungeon_webs.c src/dungeon_torches.c src/dungeon_puzzles.c
SRCS += src/skulltula.c src/wall_skull.c src/dekubaba.c
SRCS += src/hintnuts.c
SRCS += src/gohma_larva.c
SRCS += src/gohma.c
SRCS += src/level_select.c src/tree_mouth.c src/field_music.c src/story_route.c src/emerald_story.c \
	src/oot_core_host.c
MY_OBJS = $(patsubst %.c,$(OBJDIR)/%.o,$(notdir $(SRCS)))

# --- oot-core (fork Phase 0): real decomp code compiled as C++ ---------------
# OOT_CORE=1 builds the imported decomp math slice and its SH-2 benchmark into
# OOTCORE.BIN: a self-contained blob linked at a fixed RAM-cart address
# (oot-core/oot-core.ld), loaded at boot and run from the cart, so decomp code
# never costs work RAM. The game reaches it only through its entry table
# (oot-core/include/oot_core_api.h). Run tools/oot_core_import.py first
# (build.sh does). Flags mirror oot-core/oot-core-flags.sh. See
# docs/OOT_CORE_PIPELINE_PLAN.md and docs/BUILD.md.
OOT_CORE ?= 0
PLAYER_SOURCE ?= $(OOT_CORE)
# SLAVE_JOBS=0 (rollback, 2026-10-09): no second-SH-2 jobs of ours (core
# update, Link skin, scene prepare run on the master as before).
SLAVE_JOBS ?= 1
CART_ACTOR_POOL ?= 0
ifeq ($(CART_ACTOR_POOL),1)
_CCFLAGS += -DDOSEI_CART_ACTOR_POOL
endif
OOT_CORE_MODE = $(OOT_CORE)$(if $(filter 1,$(OOT_CORE)),c$(CORE_COLLISION)p$(PLAYER_SOURCE))s$(SLAVE_JOBS)a$(CART_ACTOR_POOL)
ifeq ($(SLAVE_JOBS),0)
_CCFLAGS += -DDOSEI_NO_SLAVE_JOBS
endif
# OOT_CORE changes ram_cart.h carves and many #ifdefs: a flip must recompile
# every game object (2026-10-05: a stale non-core ram_cart.o in an OOT_CORE=1
# image refused the OOTCORE carve, "oc load failed f 0"). CORE_COLLISION too.
OOT_CORE_STAMP = build/generated/oot_core_mode.stamp
$(shell mkdir -p build/generated; [ "$$(cat $(OOT_CORE_STAMP) 2>/dev/null)" = "$(OOT_CORE_MODE)" ] || echo "$(OOT_CORE_MODE)" > $(OOT_CORE_STAMP))
ifeq ($(OOT_CORE),1)
ifeq ($(CORE_COLLISION),1)
_CCFLAGS += -DCORE_COLLISION
endif
ifeq ($(OS),Windows_NT)
# Jo's Windows SDK has no C++ front end; use the sibling sh2eb-elf g++.
OOT_CORE_CXX ?= ../../sh2eb-elf/bin/sh2eb-elf-g++
OOT_CORE_READELF ?= ../../sh2eb-elf/bin/sh2eb-elf-readelf
else
# The Linux gcc 9.3 (tools/toolchain/build-sh-elf-linux.sh) includes C++.
OOT_CORE_CXX ?= $(CC)
OOT_CORE_READELF ?= readelf
endif
OOT_CORE_DECOMP ?= $(DOSEI_OOT)
OOT_CORE_D = build/oot-core/decomp
OOT_CORE_OBJDIR = $(OBJDIR)/oot-core
# Cached cart alias of the RAM_CART_OOTCORE carve (src/ram_cart.h; ram_cart.c
# checks the carve sits here). 0x2xxxxxxx is cache-through: never run code there.
OOT_CORE_LOAD_ADDR = 0x02760000
OOT_CORE_MAX_BYTES = 0xA0000
# Low Work RAM span for the core's large BSS (src/ram_low.h RAM_LOW_OOTCORE_BSS).
OOT_CORE_LOW_BSS_ADDR = 0x0021D800
OOT_CORE_LOW_BSS_BYTES = 0xA000
# Scene collision blobs (RAM_CART_SCENECOL carve, cached alias). One per scene in
# tools/oot_core_import.py SCENE_COLLISION; data only, nothing executes there.
OOT_SCENECOL_ADDR = 0x02710000
OOT_SCENECOL_MAX_BYTES = 0x50000
OOT_CORE_CXXFLAGS = -x c++ -std=gnu++17 -fno-exceptions -fno-rtti -fpermissive -funsigned-char -w \
	-DOOT_CORE_LOAD_ADDR=$(OOT_CORE_LOAD_ADDR)u -DOOT_SCENECOL_ADDR=$(OOT_SCENECOL_ADDR)u \
	-DOOT_SCENECOL_MAX_BYTES=$(OOT_SCENECOL_MAX_BYTES)u \
	-fno-threadsafe-statics -fno-use-cxa-atexit -Os -m2 -ffunction-sections -fdata-sections \
	-include oot_prelude.h \
	-DPLATFORM_N64=1 -DPLATFORM_GC=0 -DPLATFORM_IQUE=0 -DOOT_VERSION=NTSC_1_2 -DOOT_REVISION=2 \
	-DOOT_REGION=REGION_US -DLIBULTRA_VERSION=LIBULTRA_VERSION_I -DLIBULTRA_PATCH=1 -DDEBUG_FEATURES=0 \
	-DNDEBUG -DF3DEX_GBI_2 -DNON_MATCHING -DAVOID_UB -D_LANGUAGE_C -D_MIPS_SZLONG=32 -D_MIPS_SZINT=32 \
	-D_MIPS_SZPTR=32 -nostdinc -Ioot-core/shim -Ioot-core/include -I$(OOT_CORE_D)/include \
	-I$(OOT_CORE_D)/include/libc -I$(OOT_CORE_D)/src -I$(OOT_CORE_D) \
	-I$(OOT_CORE_DECOMP)/extracted/ntsc-1.2 -I$(OOT_CORE_DECOMP)
# Decomp file list: tools/oot_core_import.py SOURCES (writes sources.mk).
-include build/oot-core/sources.mk
# PLAYER_SOURCE=1 (default with OOT_CORE=1): the real decomp Player owns Link
# (z_player*, frame bank, host I/O glue in bridge_player_source.cpp). 0 keeps
# the C Link + bridge_player.cpp proxy as the rollback. Player migration
# phase 4, docs/PLAYER_MIGRATION.md.
PLAYER_SOURCE ?= $(OOT_CORE)
ifeq ($(PLAYER_SOURCE),1)
OOT_PLAYER_OWNER_SRCS = $(OOT_PLAYER_SRCS) oot-core/src/player_frame_bank.cpp oot-core/src/player_frame_decode.cpp oot-core/src/bridge_player_source.cpp
OOT_CORE_CXXFLAGS += -DPLAYER_SOURCE=1 -DPFB_CORE=1
_CCFLAGS += -DPLAYER_SOURCE=1
else
OOT_PLAYER_OWNER_SRCS = oot-core/src/bridge_player.cpp
endif
OOT_CORE_SRCS = $(OOT_CORE_DECOMP_SRCS) \
	oot-core/src/oot_math.cpp oot-core/src/oot_rand.cpp \
	oot-core/src/oot_core_bench.cpp oot-core/src/oot_core_link_stubs.cpp \
	oot-core/src/oot_core_api.cpp oot-core/src/bridge_tables.cpp oot-core/src/bridge_libc.cpp \
	oot-core/src/bridge_play.cpp oot-core/src/bridge_assets.cpp $(OOT_PLAYER_OWNER_SRCS) \
	oot-core/src/bridge_message.cpp oot-core/src/oot_core_views.cpp \
	oot-core/src/bridge_cutscene.cpp oot-core/src/bridge_cutscene_camera.cpp \
	oot-core/src/bridge_child_route.cpp oot-core/src/bridge_ranch.cpp oot-core/src/bridge_route_audio.cpp \
	oot-core/src/oot_core_draw.cpp build/oot-core/keep_ph.cpp oot-core/src/bridge_npc.cpp \
	oot-core/src/bridge_items.cpp oot-core/src/bridge_actor_pack.cpp oot-core/src/oot_core_sprite.cpp oot-core/src/oot_core_bg.cpp
OOT_CORE_OBJS = $(patsubst %.cpp,$(OOT_CORE_OBJDIR)/%.o,$(notdir $(OOT_CORE_SRCS)))
OOT_FIELD_SRCS = $(OOT_FIELD_ENEMY_SRCS) oot-core/src/field_enemy_sprite.cpp oot-core/src/field_enemy_pack.cpp
OOT_FIELD_OBJS = $(patsubst %.cpp,$(OOT_CORE_OBJDIR)/%.o,$(notdir $(OOT_FIELD_SRCS)))
OOT_BOSS_EFFECT_ALL_SRCS = $(OOT_BOSS_EFFECT_SRCS) $(OOT_ROUTE_EFFECT_SRCS)
OOT_BOSS_EFFECT_OBJS = $(patsubst %.cpp,$(OOT_CORE_OBJDIR)/%.o,$(notdir $(OOT_BOSS_EFFECT_ALL_SRCS)))
OOT_BOSS_EFFECT_OBJS += $(filter %/z_eff_ss_dust.o %/z_eff_ss_hahen.o %/z_eff_ss_en_fire.o %/z_eff_ss_dead_db.o %/z_eff_ss_dead_sound.o %/z_eff_ss_hitmark.o,$(OOT_FIELD_OBJS))
# Scene-owned NPC/prop actors (tools/scene_pack_actors.py): compiled once,
# linked into each scene's OAP that can spawn them, never into the core.
OOT_PACK_ACTOR_OBJS = $(patsubst %.cpp,$(OOT_CORE_OBJDIR)/%.o,$(notdir $(OOT_PACK_ACTOR_SRCS)))
OOT_PACK_PROFILE_OBJS = $(patsubst %,$(OOT_CORE_OBJDIR)/%_profiles.o,$(OOT_SCENE_PACKS))
OOT_PACK_HELPER_OBJS = $(OOT_CORE_OBJDIR)/dodongo_enemy_sprite.o
OOT_RANCH_HELPER_OBJS = $(OOT_CORE_OBJDIR)/ranch_horse_sprite.o
OOT_WATER_HELPER_OBJS = $(OOT_CORE_OBJDIR)/water_enemy_sprite.o $(OOT_CORE_OBJDIR)/field_enemy_sprite.o
_CCFLAGS += -DDOSEI_OOT_CORE -DOOT_CORE_LOAD_ADDR=$(OOT_CORE_LOAD_ADDR)u \
	-DOOT_SCENECOL_ADDR=$(OOT_SCENECOL_ADDR)u -Ioot-core/include
vpath %.cpp $(sort $(dir $(OOT_CORE_SRCS)))
vpath %.cpp $(sort $(dir $(OOT_FIELD_SRCS)))
vpath %.cpp $(sort $(dir $(OOT_BOSS_EFFECT_ALL_SRCS)))
vpath %.cpp $(sort $(dir $(OOT_PACK_ACTOR_SRCS))) build/oot-core/packs build/oot-core/player
$(OOT_CORE_OBJDIR):
	mkdir -p $@
# Static ctors are fine: OotCoreEntry.init runs the blob's ctor table.
# Placeholder tables are keyed by slot: keep source order (BUILD.md 124).
$(OOT_CORE_OBJDIR)/%_ph.o: OOT_CORE_CXXFLAGS += -fno-toplevel-reorder
$(OOT_CORE_OBJDIR)/%.o: %.cpp oot-core/include/fx.h oot-core/include/oot_prelude.h oot-core/include/oot_core_bench.h oot-core/include/oot_core_api.h oot-core/include/oot_core_host.h | $(OOT_CORE_OBJDIR)
	$(OOT_CORE_CXX) $(OOT_CORE_CXXFLAGS) -c $< -o $@
$(OOT_CORE_OBJDIR)/bridge_message.o: build/oot-core/ocarina_restrictions.inc build/oot-core/ocarina_memory.inc build/generated/ocarina_sfx_duration.h
$(OOT_CORE_OBJDIR)/oot_core_api.o: build/oot-core/environment_clock.inc build/oot-core/environment_player_gate.inc oot-core/include/oot_scene_blob.h
$(OOT_CORE_OBJDIR)/z_bgcheck.o: oot-core/include/bgcheck_bounds.h
$(OOT_CORE_OBJDIR)/bridge_player.o: oot-core/include/bgcheck_bounds.h
$(OOT_CORE_OBJDIR)/bridge_player_source.o: oot-core/include/player_tap_aim.h oot-core/include/player_host_carry.h
$(OOT_CORE_OBJDIR)/oot_core_sprite.o: oot-core/include/oot_sprite_archive.h
$(OOT_CORE_OBJDIR)/player_frame_decode.o: oot-core/tests/player_frame_decode.c
$(OOT_CORE_OBJDIR)/oot_core_draw.o $(OOT_CORE_OBJDIR)/z_player_lib.o: oot-core/include/player_anchor_matrix.h
$(OOT_FIELD_OBJS): oot-core/include/field_enemy_sprite.h
$(OOT_CORE_OBJDIR)/field_enemy_sprite.o: build/oot-core/field_anchors.inc
$(OOT_CORE_OBJDIR)/dodongo_enemy_sprite.o: build/oot-core/dodongo_anchors.inc oot-core/include/dodongo_enemy_sprite.h
$(OOT_CORE_OBJDIR)/ranch_horse_sprite.o: oot-core/include/ranch_horse_sprite.h oot-core/include/ranch_horse_anchors.inc
$(OOT_CORE_OBJDIR)/bridge_play.o: oot-core/include/core_item_grant_mirror.inc
$(OOT_CORE_OBJDIR)/oot_core_api.o $(OOT_CORE_OBJDIR)/oot_core_views.o: oot-core/include/oot_core_shop.h oot-core/include/oot_cutscene_camera.h oot-core/include/oot_core_effects.h oot-core/include/oot_core_api.h
$(OBJDIR)/oot_core_host.o: src/core_item_grants.inc oot-core/include/oot_core_audio.h oot-core/include/oot_core_shop.h oot-core/include/oot_cutscene_camera.h oot-core/include/oot_core_api.h
$(OOT_CORE_OBJDIR)/water_enemy_sprite.o: build/oot-core/water_anchors.inc oot-core/include/water_enemy_sprite.h
build/oot-core/water_anchors.inc: tools/build_water_enemy_anchors.py tools/build_field_enemy_anchors.py
	"$(PYTHON)" tools/build_water_enemy_anchors.py --oot "$(OOT_CORE_DECOMP)" --rom-dir "$(OOT_CORE_DECOMP)/baseroms/ntsc-1.2" --out $@
build/oot-core/dodongo_anchors.inc: tools/build_dodongo_enemy_anchors.py
	"$(PYTHON)" tools/build_dodongo_enemy_anchors.py --oot "$(OOT_CORE_DECOMP)" --rom-dir "$(OOT_CORE_DECOMP)/baseroms/ntsc-1.2" --out $@
build/oot-core/field_exports.ld: $(OOT_FIELD_OBJS) $(OOT_PACK_ACTOR_OBJS) $(OOT_PACK_PROFILE_OBJS) $(OOT_PACK_HELPER_OBJS) $(OOT_RANCH_HELPER_OBJS) $(OOT_WATER_HELPER_OBJS) $(OOT_BOSS_EFFECT_OBJS) $(OOT_CORE_OBJS) tools/build_pack_exports.py
	"$(PYTHON)" tools/build_pack_exports.py --nm $(patsubst %g++,%nm,$(patsubst %gcc,%nm,$(OOT_CORE_CXX))) --pack $(sort $(OOT_FIELD_OBJS) $(OOT_PACK_ACTOR_OBJS) $(OOT_PACK_PROFILE_OBJS) $(OOT_PACK_HELPER_OBJS) $(OOT_RANCH_HELPER_OBJS) $(OOT_WATER_HELPER_OBJS) $(OOT_BOSS_EFFECT_OBJS)) --resident $(OOT_CORE_OBJS) --out $@
build/oot-core/oot-core.elf: $(OOT_CORE_OBJS) build/oot-core/sources.mk oot-core/oot-core.ld build/oot-core/obj_syms.ld build/oot-core/msg_syms.ld build/oot-core/field_exports.ld
	$(OOT_CORE_CXX) -m2 -nostdlib -nostartfiles -T oot-core/oot-core.ld \
		-Wl,--defsym,OOT_CORE_LOAD_ADDR=$(OOT_CORE_LOAD_ADDR) \
		-Wl,--defsym,OOT_CORE_MAX_BYTES=$(OOT_CORE_MAX_BYTES) \
		-Wl,--defsym,OOT_CORE_LOW_BSS_ADDR=$(OOT_CORE_LOW_BSS_ADDR) \
		-Wl,--defsym,OOT_CORE_LOW_BSS_BYTES=$(OOT_CORE_LOW_BSS_BYTES) \
		-Wl,--gc-sections -Wl,-Map,build/oot-core/oot-core.map \
		$(OOT_CORE_OBJS) build/oot-core/msg_syms.ld build/oot-core/obj_syms.ld build/oot-core/field_exports.ld -lgcc -o $@
	"$(PYTHON)" tools/check_ph_order.py keep $@ build/oot-core/keep_ph.txt
$(ASSETS_DIR)/OOTCORE.BIN: build/oot-core/oot-core.elf
	$(CONV) -O binary $< $@
# One OAP per scene that owns pack actors (OOT_SCENE_PACKS, generated by
# oot_core_import.py): its NPC/prop actors plus, for Hyrule Field (SA), the
# Field enemies. Scene code and data must fit the scene carve together. Bind
# each pack to the exact resident image; changing the core relinks them all.
define SCENE_PACK_RULE
OOT_PACK_$(1)_OBJS = $$(patsubst %,$$(OOT_CORE_OBJDIR)/%.o,$$(OOT_PACK_$(1)_ACTORS) $(1)_profiles) $$(if $$(filter SA,$(1)),$$(OOT_FIELD_OBJS))
OOT_PACK_$(1)_OBJS += $$(if $$(filter z_en_dodojr z_en_dodongo z_en_am z_en_zf z_en_vm z_en_sw,$$(OOT_PACK_$(1)_ACTORS)),$$(OOT_PACK_HELPER_OBJS))
OOT_PACK_$(1)_OBJS += $$(if $$(filter z_en_tite z_en_firefly,$$(OOT_PACK_$(1)_ACTORS)),$$(OOT_WATER_HELPER_OBJS))
OOT_PACK_$(1)_OBJS += $$(if $$(filter z_en_horse_link_child z_en_horse_normal,$$(OOT_PACK_$(1)_ACTORS)),$$(OOT_RANCH_HELPER_OBJS))
OOT_PACK_$(1)_OBJS += $$(patsubst %,$$(OOT_CORE_OBJDIR)/%.o,$$(OOT_PACK_$(1)_EFFECTS))
OOT_PACK_$(1)_PAYLOADS = $(1).OOC $$(addsuffix .OOB,$$(OOT_PACK_$(1)_OBJECTS))
build/oot-core/packs/$(1).OAP: build/oot-core/oot-core.elf $$(ASSETS_DIR)/OOTCORE.BIN $$(OOT_PACK_$(1)_OBJS) $$(addprefix $$(ASSETS_DIR)/,$$(OOT_PACK_$(1)_PAYLOADS)) tools/build_actor_packs.py oot-core/pack.ld
	"$$(PYTHON)" tools/build_actor_packs.py --core build/oot-core/oot-core.elf --core-bin $$(ASSETS_DIR)/OOTCORE.BIN --obj-syms build/oot-core/obj_syms.ld --output $$@ --cxx $$(OOT_CORE_CXX) --scene $$(OOT_PACK_$(1)_SCENE) --objects $$(OOT_PACK_$(1)_OBJS) $$(foreach p,$$(OOT_PACK_$(1)_PAYLOADS),--payload $$(p)=$$(ASSETS_DIR)/$$(p)) --carve-base $$(OOT_SCENECOL_ADDR) --carve-bytes $$(OOT_SCENECOL_MAX_BYTES)
$$(ASSETS_DIR)/$(1).OAP: build/oot-core/packs/$(1).OAP
	cp $$< $$@
$$(TARGET2): $$(ASSETS_DIR)/$(1).OAP
endef
$(foreach s,$(OOT_SCENE_PACKS),$(eval $(call SCENE_PACK_RULE,$(s))))
.PHONY: check-dodongo-boss-budget
check-dodongo-boss-budget:
	"$(PYTHON)" tools/check_dodongo_boss_budget.py --oot "$(OOT_CORE_DECOMP)" --cd "$(ASSETS_DIR)" --room "$(ASSETS_DIR)/SGR1.MSH" --report build/oot-core/dodongo-render-budget.json
# Real Player frames (PLAYER_SOURCE): build.sh regenerates bank_full when
# its inputs change; split_player_bank.py cuts it into the resident common
# set PLAYRES.PFB, demand groups PG*.PFB and scene cutscene packs PCS*.PFB
# (byte-identical blocks) plus the host's group tables.
ifeq ($(PLAYER_SOURCE),1)
$(ASSETS_DIR)/PLAYRES.PFB: build/player-migration/bank_full/ALL.PFB tools/split_player_bank.py oot-core/include/oot_core_api.h
	rm -f $(ASSETS_DIR)/PLAYANIM.PFB $(ASSETS_DIR)/PLAYC.PFB
	"$(PYTHON)" tools/split_player_bank.py --oot "$(OOT_CORE_DECOMP)" --cd $(ASSETS_DIR)
build/generated/player_groups.h: $(ASSETS_DIR)/PLAYRES.PFB
	@test -f $@
$(OBJDIR)/oot_core_host.o: build/generated/player_groups.h
$(TARGET2): $(ASSETS_DIR)/PLAYRES.PFB
endif
# Core + every scene pack without mastering a disc (link/fit check).
.PHONY: oot-scene-packs
oot-scene-packs: $(patsubst %,build/oot-core/packs/%.OAP,$(OOT_SCENE_PACKS))
# Infrastructure fixture is never staged on the disc or registered as an actor.
.PHONY: oot-actor-pack-test
oot-actor-pack-test: build/oot-core/generic_sprites.h build/oot-core/pack-test/TEST.OAP
build/oot-core/pack-test/TEST.OAP: build/oot-core/oot-core.elf $(ASSETS_DIR)/OOTCORE.BIN build/oot-core/obj_syms.ld tools/build_actor_packs.py oot-core/pack.ld oot-core/tests/actor_pack_fixture.cpp
	"$(PYTHON)" tools/build_actor_packs.py --core build/oot-core/oot-core.elf --core-bin $(ASSETS_DIR)/OOTCORE.BIN --obj-syms build/oot-core/obj_syms.ld --output $@ --cxx $(OOT_CORE_CXX) --test-pack --carve-base $(OOT_SCENECOL_ADDR) --carve-bytes $(OOT_SCENECOL_MAX_BYTES)
# One blob per registered scene (oot_core_import.py registered_scenes), named
# by scene index like the room banks (S1, Z20). A scene whose blob does not fit
# the carve is left out (recipe removes the target); the runtime skips it.
# Link addresses live only in this makefile: a carve move must relink every blob
# (2026-10-03: stale S1.OOC kept the old 0x0275xxxx pointers, Kokiri collision
# read garbage, every En_Kusa failed its floor snap). Stamp rewritten on change.
OOT_CORE_ADDR_STAMP = build/oot-core/addr.stamp
OOT_CORE_ADDR_KEY = $(OOT_CORE_LOAD_ADDR) $(OOT_CORE_MAX_BYTES) $(OOT_SCENECOL_ADDR) $(OOT_SCENECOL_MAX_BYTES)
$(shell mkdir -p build/oot-core; [ "$$(cat $(OOT_CORE_ADDR_STAMP) 2>/dev/null)" = "$(OOT_CORE_ADDR_KEY)" ] || echo "$(OOT_CORE_ADDR_KEY)" > $(OOT_CORE_ADDR_STAMP))
build/oot-core/oot-core.elf: $(OOT_CORE_ADDR_STAMP)
$(OOT_CORE_OBJS): $(OOT_CORE_ADDR_STAMP)
$(OOT_CORE_OBJS) $(OOT_PACK_ACTOR_OBJS) $(OOT_FIELD_OBJS) $(OOT_PACK_HELPER_OBJS) $(OOT_RANCH_HELPER_OBJS) $(OOT_WATER_HELPER_OBJS) $(OOT_BOSS_EFFECT_OBJS): build/oot-core/import.stamp
$(OBJDIR)/oot_core_host.o $(OBJDIR)/ram_cart.o: $(OOT_CORE_ADDR_STAMP) src/ram_cart.h
build/oot-core/scenecol/%.elf: build/oot-core/scenecol/%.cpp oot-core/scenecol.ld oot-core/include/oot_scene_blob.h $(OOT_CORE_ADDR_STAMP)
	$(OOT_CORE_CXX) $(OOT_CORE_CXXFLAGS) -c $< -o build/oot-core/scenecol/$*.o || \
		{ rm -f build/oot-core/scenecol/$*.o; echo "scene blob $* compile failed"; }
	$(OOT_CORE_CXX) -m2 -nostdlib -nostartfiles -T oot-core/scenecol.ld \
		-Wl,--defsym,OOT_SCENECOL_ADDR=$(OOT_SCENECOL_ADDR) \
		-Wl,--defsym,OOT_SCENECOL_MAX_BYTES=$(OOT_SCENECOL_MAX_BYTES) \
		build/oot-core/scenecol/$*.o -o $@ || { rm -f $@; echo "scene blob $* left out"; }
$(ASSETS_DIR)/%.OOC: build/oot-core/scenecol/%.elf
	[ ! -f $< ] || $(CONV) -O binary $< $@
# Decomp object data blobs (oot_core_import.py OBJECTS), linked at segment 6.
# Their symbols reach the oot-core link as absolute 0x06xxxxxx addresses.
OOT_OBJECT_MAX_BYTES = 0x30000
OOT_CORE_NM ?= $(patsubst %gcc,%nm,$(patsubst %g++,%nm,$(OOT_CORE_CXX)))
OOT_OBJECT_ELFS = $(patsubst %,build/oot-core/objects/%.elf,$(OOT_OBJECT_NAMES))
build/oot-core/objects/%.elf: build/oot-core/objects/%.cpp build/oot-core/objects/%_ph.cpp oot-core/object.ld
	$(OOT_CORE_CXX) $(OOT_CORE_CXXFLAGS) -c build/oot-core/objects/$*.cpp -o build/oot-core/objects/$*.o
	$(OOT_CORE_CXX) $(OOT_CORE_CXXFLAGS) -fno-toplevel-reorder -c build/oot-core/objects/$*_ph.cpp -o build/oot-core/objects/$*_ph.o
	$(OOT_CORE_CXX) -m2 -nostdlib -nostartfiles -T oot-core/object.ld 		-Wl,--defsym,OOT_OBJECT_MAX_BYTES=$(OOT_OBJECT_MAX_BYTES) 		build/oot-core/objects/$*.o build/oot-core/objects/$*_ph.o -o $@
	"$(PYTHON)" tools/check_ph_order.py object $@ build/oot-core/objects/$*_ph.txt
build/oot-core/obj_syms.ld: $(OOT_OBJECT_ELFS)
	for f in $^; do $(OOT_CORE_NM) $$f | awk '$$2 ~ /^[DdBbRrGgSs]$$/ && $$3 !~ /^_oot_/ {print $$3 " = 0x" $$1 ";"}'; done > $@
build/oot-core/generic_sprites.h: build/oot-core/generic_sprites.json build/oot-core/obj_syms.ld tools/build_sprite_keys.py
	"$(PYTHON)" tools/build_sprite_keys.py $< build/oot-core/obj_syms.ld $@ --sheets build/generated/generic-sprites --archives $(ASSETS_DIR) --scenes build/oot-core/scenecol
$(OBJDIR)/oot_core_host.o: build/oot-core/generic_sprites.h
$(OOT_CORE_OBJDIR)/oot_core_draw.o: build/oot-core/generic_skins.h build/oot-core/generic_meshes.h
# ROM message text for z_message (oot-core/src/bridge_message.cpp).
$(ASSETS_DIR)/NESMSG.BIN: $(OOT_CORE_DECOMP)/extracted/ntsc-1.2/baserom/nes_message_data_static
	cp $< $@
$(ASSETS_DIR)/%.OOB: build/oot-core/objects/%.elf
	$(CONV) -O binary $< $@
$(TARGET2): $(ASSETS_DIR)/OOTCORE.BIN $(ASSETS_DIR)/NESMSG.BIN $(patsubst %,$(ASSETS_DIR)/%.OOC,$(OOT_SCENECOL_NAMES)) 	$(patsubst %,$(ASSETS_DIR)/%.OOB,$(OOT_OBJECT_NAMES))
endif
# Header layout changes must rebuild every consumer (save v2 otherwise wrote
# 300 bytes into a stale 220-byte stack buffer). makefile bootstraps .d files
# for existing objects and also invalidates compiled configuration changes.
$(MY_OBJS): build/generated/toolchain.stamp makefile $(OOT_CORE_STAMP)
-include $(MY_OBJS:.o=.d)

# The parent expanded $(TARGET)'s prerequisites from its own OBJS while reading
# its rules; make unions prerequisites across rules for the same target, so
# those SDK paths must be given a rule of their own. Point each one at the
# corresponding obj/ file instead of compiling in place.
$(foreach s,$(SRCS),$(eval $(s:.c=.o): $(OBJDIR)/$(notdir $(s:.c=.o))))

%.o: %.c

$(OBJDIR)/fs.o: src/fs_low.c $(JO_ENGINE_SRC_DIR)/fs.c src/fs_capacity.h src/ram_low.h src/ram_cart.h | $(OBJDIR)
	$(CC) src/fs_low.c $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -I$(JO_ENGINE_SRC_DIR) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/backup.o: src/backup_low.c $(JO_ENGINE_SRC_DIR)/backup.c src/ram_low.h | $(OBJDIR)
	$(CC) src/backup_low.c $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -I$(JO_ENGINE_SRC_DIR) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/3d.o: src/quads_low.c $(JO_ENGINE_SRC_DIR)/3d.c src/ram_low.h | $(OBJDIR)
	$(CC) src/quads_low.c $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -I$(JO_ENGINE_SRC_DIR) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/%.o: src/%.c src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/recomp_camera.o: ../shared/lib/camera/kokiri_camera.c ../shared/lib/camera/kokiri_camera.h ../shared/lib/collision/kokiri_collision.h
$(OBJDIR)/recomp_follow.o: ../shared/lib/camera/oot_follow.c ../shared/lib/camera/oot_follow.h ../shared/lib/camera/kokiri_camera.h
$(OBJDIR)/recomp_collision.o: ../shared/lib/collision/kokiri_collision.c ../shared/lib/collision/kokiri_collision.h
$(OBJDIR)/recomp.o: build/generated/texture_probe.h build/generated/title_paths.h src/input_edge.h
# Red Book track numbers/names come from assets/audio/cdda_tracks.json.
$(OBJDIR)/cdda.o $(OBJDIR)/music_songs.o: build/generated/cdda_tracks.h
$(OBJDIR)/music_songs.o $(OBJDIR)/recomp.o $(OBJDIR)/main.o $(OBJDIR)/cutscene.o: build/generated/song_ids.h
$(OBJDIR)/music_songs.o: build/generated/song_routes.inc
$(OBJDIR)/cutscene.o $(OBJDIR)/kokiri_sgl.o: src/vdp1_draw_wait.h
$(OBJDIR)/main.o $(OBJDIR)/kokiri_sgl.o: build/generated/kokiri_scene.h build/generated/link_scene.h build/generated/vdp1_layout.h
$(OBJDIR)/kokiri_sgl.o $(OBJDIR)/kokiri_actors.o $(OBJDIR)/gameplay.o $(OBJDIR)/recomp.o $(OBJDIR)/main.o $(OBJDIR)/kokiri_dialogue.o $(OBJDIR)/dialogue_text.o: build/generated/kokiri_actors.h build/generated/kokiri_dialogue.h src/gameplay.h
# The skinner and its clip tables are generated by build_link_model.py --animate.
$(OBJDIR)/link_anim.o $(OBJDIR)/link_anim_state.o $(OBJDIR)/kokiri_sgl.o: build/generated/link_clips.h build/generated/link_scene.h
$(OBJDIR)/kokiri_sgl.o: build/generated/link_equipment.h
# Cutscene tables are generated by build_cutscenes.py from the decomp data.
$(OBJDIR)/message.o $(OBJDIR)/cutscene.o $(OBJDIR)/cutscenes.o $(OBJDIR)/recomp.o $(OBJDIR)/main.o: build/generated/cutscenes.h src/message.h src/cutscene.h
$(OBJDIR)/minimap.o $(OBJDIR)/main.o: build/generated/minimap_data.h src/minimap.h
$(OBJDIR)/minimap.o: build/generated/gameplay_hud_data.h src/gameplay_hud_state.h

$(OBJDIR)/music.o: ../shared/lib/music/music.c ../shared/lib/music/music.h src/video_mode.h | $(OBJDIR)
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

$(OBJDIR)/core.o: src/core_low.c src/ram_low.h $(JO_ENGINE_SRC_DIR)/core.c makefile | $(OBJDIR)
	$(CC) src/core_low.c $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -I$(JO_ENGINE_SRC_DIR) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

# Keep the shared SDK immutable; relocate only its sprite metadata.
$(OBJDIR)/sprites.o: src/sprites_low.c src/ram_low.h $(JO_ENGINE_SRC_DIR)/sprites.c | $(OBJDIR)
	$(CC) src/sprites_low.c $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -I$(JO_ENGINE_SRC_DIR) -MMD -MP -MF $(@:.o=.d) -MT $@ -o $@

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
	$(CONV) -O binary -R .cart $(TARGET) $(TARGET1)

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
	$(CONV) -O binary -j .cart $(TARGET) $(ASSETS_DIR)/HOSTCOLD.BIN
	"$(PYTHON)" tools/check_disc_directory.py
	$(CONV) -O binary -R .cart $(TARGET) $(ASSETS_DIR)/0.bin
	$(MKISOFS) -quiet -sysid "SEGA SATURN" -volid "KOKIRIJO" -volset "KOKIRIJO" 		-sectype 2352 -publisher "SEGA ENTERPRISES, LTD." 		-preparer "SEGA ENTERPRISES, LTD." -appid "KOKIRIJO" 		-abstract "$(ASSETS_DIR)/ABS.TXT" -copyright "$(ASSETS_DIR)/CPY.TXT" 		-biblio "$(ASSETS_DIR)/BIB.TXT" -generic-boot $(IPFILE) 		-full-iso9660-filenames -o $(TARGET2) $(ASSETS_DIR)
	"$(PYTHON)" tools/check_disc_directory.py --iso $(TARGET2) || { rm -f $(TARGET2); exit 1; }

$(TARGET3): $(TARGET2)
	"$(PYTHON)" tools/write_cue.py $(TARGET2) $(TARGET3)

clean:
	$(RM) $(OBJDIR) $(TARGET) $(TARGET1) $(TARGET2) $(TARGET3) $(MPFILE) build/cd/0.bin

$(OBJDIR)/action_audio.o: build/generated/action_audio_data.h build/generated/opening_audio_data.h
$(OBJDIR)/action_audio.o $(OBJDIR)/recomp.o $(OBJDIR)/main.o: src/action_audio.h
$(OBJDIR)/action_audio.o: ../shared/lib/music/music.h src/gameplay.h

$(OBJDIR)/pause_windows.o $(OBJDIR)/gameplay.o: src/pause_window_state.h

$(OBJDIR)/pause_windows.o: build/generated/pause_cursor_data.h
