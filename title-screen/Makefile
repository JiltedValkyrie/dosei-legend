ifeq ($(strip $(YAUL_INSTALL_ROOT)),)
  $(error Undefined YAUL_INSTALL_ROOT (install root directory))
endif

# PERF_BENCH=1 builds the fixed-pose profiler configuration. It is deliberately
# independent of DEBUG (which gates libyaul assertions) and redirects BOTH the
# object directory and the disc image, so the two configurations can never
# share objects or clobber each other's image. build/ already contains objects
# from retired configurations, so this separation is not hypothetical.
ifeq ($(filter 1 yes on,$(strip $(PERF_BENCH))),)
  # Normal shipping build.
  SH_BUILD_DIR:= build
  SH_OUTPUT_DIR:= .
else ifneq ($(filter 1 yes on,$(strip $(EARLY_CULL))),)
  # Experiment: conservative early face rejection before the vertex loop.
  SH_BUILD_DIR:= build-perf-early
  SH_OUTPUT_DIR:= build-perf-early
else ifneq ($(filter 1 yes on,$(strip $(ABLATE_WIREFRAME))),)
  # Ablation: wireframe. Fill removed, CPU path unchanged.
  SH_BUILD_DIR:= build-perf-wire
  SH_OUTPUT_DIR:= build-perf-wire
else ifneq ($(filter 1 yes on,$(strip $(ABLATE_TEXTURE))),)
  # Ablation: resampler skipped. Output is deliberately wrong.
  SH_BUILD_DIR:= build-perf-notex
  SH_OUTPUT_DIR:= build-perf-notex
else ifneq ($(filter 1 yes on,$(strip $(ABLATE_COLLISION))),)
  # Ablation: collision response removed from camera movement.
  SH_BUILD_DIR:= build-perf-nocol
  SH_OUTPUT_DIR:= build-perf-nocol
else ifneq ($(filter 1 yes on,$(strip $(ABLATE_MUSIC))),)
  # Ablation: score advancement skipped in the VBlank callback.
  SH_BUILD_DIR:= build-perf-nomus
  SH_OUTPUT_DIR:= build-perf-nomus
else ifneq ($(filter 0 no off,$(strip $(TEXTURE_STAGE_DISABLE))),)
  # Staging explicitly re-enabled for comparison.
  SH_BUILD_DIR:= build-perf-staged
  SH_OUTPUT_DIR:= build-perf-staged
else
  # Default benchmark build: staging off, nothing ablated.
  SH_BUILD_DIR:= build-perf
  SH_OUTPUT_DIR:= build-perf
endif

include $(YAUL_INSTALL_ROOT)/share/build.pre.mk

# Required for TGA loading (tga_read/tga_image_decode)
include $(YAUL_INSTALL_ROOT)/share/build.tga.mk

# Each asset follows the format: <path>;<symbol>. Duplicates are removed
BUILTIN_ASSETS+= \
	assets/TITLE.TGA;asset_title_tga \
	assets/FOREST_BG.TGA;asset_forest_bg_tga \
	assets/PRESS_START.RAW;asset_press_start_raw \
	assets/TITLE_PCM.RAW;asset_title_pcm \
	assets/TITLE_LEVELS.RAW;asset_title_levels

SH_PROGRAM:= title-screen
SH_SRCS:= \
	src/main.c \
	src/debug/frame_probe.c \
	src/debug/crash_probe.c \
	src/debug/perf_bench.c \
	src/debug/crash_vectors.sx \
	src/scene/kokiri_scene.c \
	src/scene/kokiri_collision.c \
	src/scene/kokiri_camera.c \
	src/scene/kokiri_clip.c \
	src/audio/title_music.c \
	src/audio/title_player.c

SH_CFLAGS+= -Os -Isrc/audio -Isrc/scene -Isrc/debug -Iassets/generated $(TGA_CFLAGS)
ifneq ($(filter 1 yes on,$(strip $(PERF_BENCH))),)
  SH_CFLAGS+= -DPERF_BENCH=1
endif
ifneq ($(strip $(TEXTURE_STAGE_DISABLE)),)
  SH_CFLAGS+= -DTEXTURE_STAGE_DISABLE=$(strip $(TEXTURE_STAGE_DISABLE))
endif
ifneq ($(filter 1 yes on,$(strip $(ABLATE_TEXTURE))),)
  SH_CFLAGS+= -DABLATE_TEXTURE=1
endif
ifneq ($(filter 1 yes on,$(strip $(ABLATE_WIREFRAME))),)
  SH_CFLAGS+= -DABLATE_WIREFRAME=1
endif
ifneq ($(filter 1 yes on,$(strip $(ABLATE_MUSIC))),)
  SH_CFLAGS+= -DABLATE_MUSIC=1
endif
ifneq ($(filter 1 yes on,$(strip $(ABLATE_COLLISION))),)
  SH_CFLAGS+= -DABLATE_COLLISION=1
endif
ifneq ($(filter 1 yes on,$(strip $(EARLY_CULL))),)
  SH_CFLAGS+= -DEARLY_CULL=1
endif
SH_LDFLAGS+= $(TGA_LDFLAGS)

IP_VERSION:= V1.000
IP_RELEASE_DATE:= 20260914
IP_AREAS:= JTUBKAEL
IP_PERIPHERALS:= JAMKST
IP_TITLE:= Dosei Legend - Title Screen
IP_MASTER_STACK_ADDR:= 0x06004000
IP_SLAVE_STACK_ADDR:= 0x06001E00
IP_1ST_READ_ADDR:= 0x06004000
IP_1ST_READ_SIZE:= 0

include $(YAUL_INSTALL_ROOT)/share/build.post.iso-cue.mk
