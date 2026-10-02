#!/usr/bin/env bash
# Build the Linux sh-elf toolchain that matches Jo Engine's Windows compiler:
# binutils 2.34 + gcc 9.3.0 + newlib 3.3.0, configured like Compiler/WINDOWS (sh-elf-gcc -v).
# Jo's own Compiler/LINUX is gcc 8.2, whose bigger code overflows work RAM.
#
# Usage (Linux/WSL): tools/toolchain/build-sh-elf-linux.sh [prefix]
# Default prefix: ../sh-elf-9.3-linux next to this repository.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prefix="${1:-$(cd "$here/../../.." && pwd)/sh-elf-9.3-linux}"
work="${SH_ELF_WORK:-$HOME/sh-elf-build}"   # Linux filesystem: much faster than /mnt
jobs="$(nproc)"
BINUTILS=binutils-2.34
GCC=gcc-9.3.0
NEWLIB=newlib-3.3.0

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
    build-essential wget texinfo bison flex libgmp-dev libmpfr-dev libmpc-dev >/dev/null

mkdir -p "$work" && cd "$work"
[ -f $BINUTILS.tar.xz ] || wget -q https://ftp.gnu.org/gnu/binutils/$BINUTILS.tar.xz
[ -f $GCC.tar.xz ] || wget -q https://ftp.gnu.org/gnu/gcc/$GCC/$GCC.tar.xz
[ -d $BINUTILS ] || tar xf $BINUTILS.tar.xz
[ -d $GCC ] || tar xf $GCC.tar.xz
[ -f $NEWLIB.tar.gz ] || wget -q https://sourceware.org/pub/newlib/$NEWLIB.tar.gz
[ -d $NEWLIB ] || tar xf $NEWLIB.tar.gz

# Each stage writes a stamp when installed; delete it to rebuild that stage.
if [ ! -f stamp-binutils ]; then
mkdir -p build-binutils && cd build-binutils
../$BINUTILS/configure --target=sh-elf --prefix="$prefix" \
    --disable-nls --disable-werror --disable-multilib --with-cpu=m2
make -j"$jobs"
make install
cd ..
touch stamp-binutils
fi

export PATH="$prefix/bin:$PATH"
if [ ! -f stamp-gcc ]; then
mkdir -p build-gcc && cd build-gcc
# Same options as the Windows build, minus the host-specific ones.
../$GCC/configure --target=sh-elf --prefix="$prefix" \
    --without-headers --enable-languages=c,c++,lto --disable-threads \
    --disable-libmudflap --with-gnu-ld --with-gnu-as --disable-libgomp \
    --disable-nls --disable-shared --with-newlib --disable-multilib \
    --disable-libstdcxx --enable-lto --with-cpu=m2 --disable-libssp
make -j"$jobs" all-gcc all-target-libgcc
make install-gcc install-target-libgcc
cd ..
touch stamp-gcc
fi

# newlib: the makefile links -lc. Match Jo's Windows newlib 3.3.0 exactly
# (its newlib.h + archive): nano IO without float printf, nano malloc, lite exit, -Os.
# A default newlib build is ~37 KB bigger and overflows work RAM (BUILD.md).
if [ ! -f stamp-newlib-nano ]; then
rm -rf build-newlib && mkdir -p build-newlib && cd build-newlib
CFLAGS_FOR_TARGET="-Os -m2" ../$NEWLIB/configure --target=sh-elf --prefix="$prefix"     --disable-multilib --disable-nls --with-cpu=m2     --enable-newlib-nano-formatted-io --enable-newlib-nano-malloc --enable-lite-exit     --enable-newlib-io-long-long --disable-newlib-fvwrite-in-streamio     --disable-newlib-fseek-optimization --disable-newlib-unbuf-stream-opt     --disable-newlib-supplied-syscalls --disable-newlib-io-float
make -j"$jobs"
make install
cd ..
touch stamp-newlib-nano
fi

"$prefix/bin/sh-elf-gcc" -v 2>&1 | tail -1
echo "installed: $prefix"
