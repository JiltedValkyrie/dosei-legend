"""Packed real-Player animation clip format (prototype, big-endian, SH-2 order).

One independent block per clip. Kept poses are grouped into delta blocks of
BLOCK_K (default 8). Random access reads one block only: the absolute first
pose plus at most BLOCK_K-1 per-channel deltas. Interpolation uses at most
two kept poses.

  u16 frames, u16 kept, u8 stride, u8 blockK
  u16 bits_a, u16 nblocks, u16 pad
  u16 base[67]
  u8  width[67]     absolute field width (0 = constant). Exact channels use these.
  u8  dwidth[63]    signed-delta width for rotation channels inside a block
  u8  shift[63]     per rotation channel, value = quant << shift. 0 = exact.
  u8  pad
  u32 block_bit[nblocks]   bit offset from the start of stream B
  stream A         frames * bits_a bits, MSB first (root xyz + face, exact)
  stream B         each block: 63 absolute fields, then (count-1) x 63 deltas
  tail padded so a 32-bit field window stays inside the allocation

Exact channels (root xyz, face) are shift 0 on every source frame.
A delta field of width w stores (delta + 2^(w-1)); w = 0 means delta 0.
Quant domain is mod 2^(16-shift). Decode then shifts back to s16.
Interpolation is shortest-arc with C truncating division.
"""
import struct

CHANNELS = 67
ROT = range(3, 66)
EXACT = (0, 1, 2, 66)
HEADER = 12
BASES = HEADER
WIDTHS = BASES + CHANNELS * 2
DWIDTHS = WIDTHS + CHANNELS
SHIFTS = DWIDTHS + 63
TABLE = SHIFTS + 63 + 1          # 340, 4-byte aligned
BLOCK_K = 8


def wrap(v):
    return (v + 32768) % 65536 - 32768


def cdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def kept_frames(n, stride):
    kept = list(range(0, n, stride))
    if kept[-1] != n - 1:
        kept.append(n - 1)
    return kept


def as_shifts(shift):
    if isinstance(shift, int):
        return [0, 0, 0] + [shift] * 63 + [0]
    shifts = [0, 0, 0] + list(shift) + [0]
    if len(shifts) != CHANNELS:
        raise ValueError('need 63 rotation shifts')
    return shifts


def quant(v, shift):
    m = 1 << (16 - shift)
    return (((v & 0xFFFF) + ((1 << shift) >> 1)) >> shift) % m


def circular_base(values, modulus):
    vals = sorted(set(values))
    if len(vals) == 1:
        return vals[0], 0
    gaps = [(vals[(i + 1) % len(vals)] - vals[i]) % modulus for i in range(len(vals))]
    i = max(range(len(vals)), key=lambda k: gaps[k])
    base = vals[(i + 1) % len(vals)]
    span = modulus - gaps[i]
    return base, span.bit_length()


def delta_width(deltas):
    """Bits for a biased signed field. Bias is 2^(w-1); w must cover it."""
    if not deltas or all(d == 0 for d in deltas):
        return 0
    span = max(-min(deltas), max(deltas) + 1)
    return 1 + (span - 1).bit_length()


class BitWriter:
    def __init__(self):
        self.acc, self.n, self.out = 0, 0, bytearray()

    def bitpos(self):
        return len(self.out) * 8 + self.n

    def put(self, value, width):
        for b in range(width - 1, -1, -1):
            self.acc = (self.acc << 1) | ((value >> b) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc, self.n = 0, 0

    def bytes(self):
        if self.n:
            self.out.append(self.acc << (8 - self.n))
            self.acc, self.n = 0, 0
        return bytes(self.out)


def read_bits(data, bitpos, width):
    v = 0
    for _ in range(width):
        v = (v << 1) | ((data[bitpos >> 3] >> (7 - (bitpos & 7))) & 1)
        bitpos += 1
    return v


def pack_clip(src, shift, stride, block_k=BLOCK_K):
    shifts = as_shifts(shift)
    n = len(src)
    kept = kept_frames(n, stride)
    bases, widths = [0] * CHANNELS, [0] * CHANNELS
    for c in range(CHANNELS):
        s = shifts[c]
        rows = range(n) if c in EXACT else kept
        bases[c], widths[c] = circular_base(
            [quant(src[i][c], s) for i in rows], 1 << (16 - s))
    dwidth = [0] * 63
    groups = [kept[s:s + block_k] for s in range(0, len(kept), block_k)]
    qkept = []
    for i in kept:
        qkept.append([quant(src[i][c], shifts[c]) for c in ROT])
    for c in range(63):
        ds = []
        m = 1 << (16 - shifts[3 + c])
        for group in groups:
            for j in range(1, len(group)):
                a = qkept[kept.index(group[j - 1])][c]
                b = qkept[kept.index(group[j])][c]
                ds.append(((b - a + m // 2) % m) - m // 2)
        dwidth[c] = delta_width(ds)
    bits_a = sum(widths[c] for c in EXACT)
    a, b = BitWriter(), BitWriter()
    offsets = []
    for gi, group in enumerate(groups):
        offsets.append(b.bitpos())
        idxs = [kept.index(frame) for frame in group]
        for c in ROT:
            m = 1 << (16 - shifts[c])
            b.put((qkept[idxs[0]][c - 3] - bases[c]) % m, widths[c])
        for j in range(1, len(idxs)):
            for c in range(63):
                ch = 3 + c
                m = 1 << (16 - shifts[ch])
                d = ((qkept[idxs[j]][c] - qkept[idxs[j - 1]][c] + m // 2) % m) - m // 2
                if dwidth[c]:
                    b.put(d + (1 << (dwidth[c] - 1)), dwidth[c])
    for i in range(n):
        for c in EXACT:
            a.put((quant(src[i][c], 0) - bases[c]) % 65536, widths[c])
    out = struct.pack('>HHBBHHH', n, len(kept), stride, block_k, bits_a, len(groups), 0)
    out += struct.pack('>%dH' % CHANNELS, *bases)
    out += bytes(widths) + bytes(dwidth) + bytes(shifts[3:66]) + bytes(1)
    if len(out) != TABLE:
        raise AssertionError(f'descriptor {len(out)} != {TABLE}')
    out += struct.pack('>%dI' % len(offsets), *offsets)
    out += a.bytes() + b.bytes()
    return out + bytes((-len(out) % 4) or 4)


def _pose_at(block, bi, within, shifts):
    n, k, stride, block_k, bits_a, nblocks, _ = struct.unpack_from('>HHBBHHH', block, 0)
    bases = struct.unpack_from('>%dH' % CHANNELS, block, BASES)
    widths = block[WIDTHS:WIDTHS + CHANNELS]
    dwidth = block[DWIDTHS:DWIDTHS + 63]
    table = TABLE + bi * 4
    pos = struct.unpack_from('>I', block, table)[0]
    b_off = TABLE + nblocks * 4 + (n * bits_a + 7) // 8
    pos += b_off * 8
    q = []
    for c in ROT:
        m = 1 << (16 - shifts[c])
        f = read_bits(block, pos, widths[c])
        pos += widths[c]
        q.append((bases[c] + f) % m)
    for _ in range(within):
        for c in range(63):
            w = dwidth[c]
            m = 1 << (16 - shifts[3 + c])
            if w:
                d = read_bits(block, pos, w) - (1 << (w - 1))
                pos += w
            else:
                d = 0
            q[c] = (q[c] + d) % m
    return [wrap(q[c] << shifts[3 + c]) for c in range(63)]


def unpack_frame(block, i):
    n, k, stride, block_k, bits_a, nblocks, _ = struct.unpack_from('>HHBBHHH', block, 0)
    bases = struct.unpack_from('>%dH' % CHANNELS, block, BASES)
    widths = block[WIDTHS:WIDTHS + CHANNELS]
    shifts = as_shifts(list(block[SHIFTS:SHIFTS + 63]))
    a_off = TABLE + nblocks * 4
    out = [0] * CHANNELS
    pos = (a_off << 3) + i * bits_a
    for c in EXACT:
        f = read_bits(block, pos, widths[c])
        pos += widths[c]
        out[c] = wrap(bases[c] + f)
    lo_k = min(i // stride, k - 1)
    lo = lo_k * stride if lo_k * stride < n else n - 1
    # kept index of frame `lo` is lo_k only when lo lands on the grid.
    if lo != i and lo_k + 1 < k:
        hi = min(lo + stride, n - 1)
        pa = _pose_at(block, lo_k // block_k, lo_k % block_k, shifts)
        hi_k = lo_k + 1
        pb = _pose_at(block, hi_k // block_k, hi_k % block_k, shifts)
        rot = [wrap(x + cdiv(wrap(y - x) * (i - lo), hi - lo)) for x, y in zip(pa, pb)]
    else:
        kk = lo_k if lo == i else k - 1
        rot = _pose_at(block, kk // block_k, kk % block_k, shifts)
    out[3:66] = rot
    return out


def reference(src, shift, stride):
    """Same values as unpack_frame, computed without the byte format."""
    shifts = as_shifts(shift)
    n = len(src)
    kept = kept_frames(n, stride)

    def q(frame, c):
        return wrap(quant(frame[c], shifts[c]) << shifts[c])

    out = []
    for i in range(n):
        lo_k = i // stride
        lo = lo_k * stride
        if lo == i or lo_k + 1 >= len(kept):
            src_i = lo if lo == i else kept[-1]
            rot = [q(src[src_i], c) for c in ROT]
        else:
            hi = kept[lo_k + 1]
            pa = [q(src[lo], c) for c in ROT]
            pb = [q(src[hi], c) for c in ROT]
            rot = [wrap(x + cdiv(wrap(y - x) * (i - lo), hi - lo)) for x, y in zip(pa, pb)]
        out.append(list(src[i][0:3]) + rot + [src[i][66]])
    return out
