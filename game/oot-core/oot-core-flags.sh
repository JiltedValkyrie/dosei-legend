# Shared oot-core compile flags (sourced by host scripts; makefile mirrors them).
# Expects $GAME = game/ directory. Sets $D (imported decomp tree) and OOT_CORE_CXXFLAGS.
OOT=${OOT:-D:/Workspace-Claude/game-decomps/n64/oot}
D=$GAME/build/oot-core/decomp
OOT_CORE_DEFS="-DPLATFORM_N64=1 -DPLATFORM_GC=0 -DPLATFORM_IQUE=0 -DOOT_VERSION=NTSC_1_2 -DOOT_REVISION=2 \
 -DOOT_REGION=REGION_US -DLIBULTRA_VERSION=LIBULTRA_VERSION_I -DLIBULTRA_PATCH=1 -DDEBUG_FEATURES=0 -DNDEBUG \
 -DF3DEX_GBI_2 -DNON_MATCHING -DAVOID_UB -D_LANGUAGE_C -D_MIPS_SZLONG=32 -D_MIPS_SZINT=32 -D_MIPS_SZPTR=32"
OOT_CORE_INCS="-nostdinc -I$GAME/oot-core/shim -I$GAME/oot-core/include -I$D/include -I$D/include/libc -I$D/src -I$D \
 -I$OOT/extracted/ntsc-1.2 -I$OOT"
OOT_CORE_CXXFLAGS="-x c++ -std=gnu++17 -fno-exceptions -fno-rtti -fpermissive -funsigned-char -w \
 -include oot_prelude.h $OOT_CORE_DEFS $OOT_CORE_INCS"
