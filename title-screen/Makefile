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
	assets/KOKIRI_VERTS.RAW;asset_kokiri_verts_raw \
	assets/KOKIRI_EDGES.RAW;asset_kokiri_edges_raw \
	assets/SDRV.BIN;asset_sound_driver \
	assets/TITLE_SMP.RAW;asset_title_samples

SH_PROGRAM:= title-screen
SH_SRCS:= \
	main.c \
	kokiri_wireframe.c \
	ponesound.c \
	title_music.c \
	title_player.c

SH_CFLAGS+= -Os -I. $(TGA_CFLAGS)
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
