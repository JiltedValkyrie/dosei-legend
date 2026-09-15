ifeq ($(strip $(YAUL_INSTALL_ROOT)),)
  $(error Undefined YAUL_INSTALL_ROOT (install root directory))
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
	src/debug/crash_vectors.sx \
	src/scene/kokiri_scene.c \
	src/scene/kokiri_collision.c \
	src/scene/kokiri_camera.c \
	src/scene/kokiri_clip.c \
	src/audio/title_music.c \
	src/audio/title_player.c

SH_CFLAGS+= -Os -Isrc/audio -Isrc/scene -Isrc/debug -Iassets/generated $(TGA_CFLAGS)
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
