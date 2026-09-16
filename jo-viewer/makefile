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

# One SGL TEXTURE slot per unique Kokiri tile (1801) plus Jo's reserved entry
# 0. The stock default is 255, which __jo_sprite_def would overflow.
JO_MAX_SPRITE = 1802

SRCS = src/main.c src/kokiri_sgl.c generated/kokiri_scene.c generated/kokiri_textures.c

JO_ENGINE_SRC_DIR = ../../joengine/jo_engine
COMPILER_DIR = ../../joengine/Compiler

# The toolchain ships an ancient msys-1.0 sh.exe in "Other Utilities", which is
# first on PATH during a build and mangles arguments passed to the cygwin
# mkisofs (every pathspec arrives empty -> "Missing pathspec"). Drive recipes
# with MSYS2 bash instead. Override on the command line if bash lives elsewhere.
SHELL := C:/msys64/usr/bin/bash.exe

include $(COMPILER_DIR)/COMMON/jo_engine_makefile

# The converter writes kokiri_scene.h into generated/.
_CCFLAGS += -Igenerated -Isrc

# --- keep build products inside this project -------------------------------
# The stock makefile derives OBJS as $(SRCS:.c=.o) and compiles via a .c.o
# suffix rule, which would drop engine objects straight into the shared
# jo_engine/ directory. Its $(TARGET) prerequisites are already expanded by the
# time the include returns, so redefining OBJS alone cannot redirect them.
# Instead declare our own link/convert targets against an obj/ object list and
# cancel the inherited suffix rule so it can never fire on an SDK source.
MY_OBJS = $(patsubst %.c,obj/%.o,$(notdir $(SRCS)))

# The parent expanded $(TARGET)'s prerequisites from its own OBJS while reading
# its rules; make unions prerequisites across rules for the same target, so
# those SDK paths must be given a rule of their own. Point each one at the
# corresponding obj/ file instead of compiling in place.
$(foreach s,$(SRCS),$(eval $(s:.c=.o): obj/$(notdir $(s:.c=.o))))

%.o: %.c

obj/%.o: src/%.c | obj
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

obj/%.o: generated/%.c | obj
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

obj/%.o: $(JO_ENGINE_SRC_DIR)/%.c | obj
	$(CC) $< $(DFLAGS) $(CCFLAGS) $(_CCFLAGS) -o $@

obj:
	mkdir -p obj

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

clean:
	$(RM) obj $(TARGET) $(TARGET1) $(TARGET2) $(TARGET3) $(MPFILE) cd/0.bin
