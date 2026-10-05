# Burning Rangers (Saturn) polygon/texture-swim study

Claude, 2026-10-05. Static reading only: personal disc image (MK-81803 V1.001),
no emulator run, no disc data committed. Suggested by Frogbull as a later,
better-engineered reference than Tomb Raider. Addresses are `0.BIN` loaded at
0x06004000 (IP.BIN first-read address).

## Tools used (scratch, not committed)

- ISO9660 extraction + `sh2eb-elf-objdump -b binary -m sh2 -EB --adjust-vma=0x06004000`.
- Almost every data file is Sonic Team **PRS** compressed (LSB-first flag bits:
  1 = literal; 00 + 2 bits = short copy len 2..5, offset byte-256; 01 = long
  copy, 13-bit offset, len (lo&7)+2 or next byte+1; zero word = end). Game's own
  decoder is at 0x060061E8. A 20-line Python port decodes every file exactly.
- `0.BIN` holds stale linker-map fragments (ADX/CDC/SGL names only). The 3D
  engine is Sonic Team's own hand-written SH-2 assembly, not SGL's 3D path.

## Renderer facts (0x06012610..0x06015100)

1. **Transform** (0x06012610 and copies at 0x06012E34, 0x06013C68, 0x0601473C
   for skinned/other paths): 3x4 16.16 matrix with `mac.l`; Z computed first so
   the vertex can be rejected before X/Y work.
2. **Per-vertex near/far reject, no clipping.** If `z >= far` (gbr+776) or
   `z < 32.0` (`0x200000`), the vertex record is written as 0.
3. **Projection:** one DIVU per vertex, `DVDNTH=focal, DVDNTL=0, DVSR=z`
   (reciprocal `focal*2^16/z`), then two `dmuls.l` (x, y) taking MACH. The divide
   is started and the NEXT vertex's transform runs while DIVU works (software
   pipelining). No float, no 64-bit C math.
4. **Guard-band clamp, not clip.** Viewport 352x224 centred. Outcode bits:
   x>=176 (8), x<=-176 (4), y>=112 (2), y<=-112 (1). Off-screen coordinates are
   then clamped to x in [-249,249], y in [-199,199]. Vertex record = 8 bytes:
   `long (z & ~15) | outcode` (negated when any outcode set), `word x`, `word y`.
5. **Face pass** (0x0601274A, type table 0x06012832): any vertex record == 0
   (behind near or past far) => **whole face dropped**. Outcode AND != 0 =>
   dropped. Screen-space cross product backface test for one-sided faces.
   Sort key per face: average, nearest, farthest, or farthest+bias (same idea as
   SGL SORT_CEN/MIN/MAX/BFR). Commands linked into Z buckets (0x0601213C),
   CMDCTRL | 0x1000 (jump-assign).
6. **No runtime subdivision found** in any path. Negative vertex index is a
   scaled billboard sprite (0x06012BEC: size from DIVU), not a clip case.
7. Depth cue: 4-level gouraud toward a fog colour from face depth
   (0x06012CDC). Far geometry fades, hiding far cut-off.

## World geometry: the real swim answer

- Rounds are a **3D tile grid**. `ROUNDx_y.MBD` = 32-byte header + 48 x 8 x 54
  big-endian u16 cells: low 9 bits block id, high bits rotation/flip flags.
  `.BLK` = per-cell byte flags; `.LTB` = 512 x 64-byte per-block nibble tables
  (collision-like); `.GDT` palettes; `.TBD` texture bank.
- Block meshes (`R21.BIN`, `R21W.BIN`, `R22.BIN`, `RD3.BIN`, `RD_4_12.BIN`):
  int16 8.8 points, byte quad indices, 1 to 3 faces per block. Cell = 20 units
  (first block is a +/-10 square).

| Library | Blocks | Faces/block | Edge p50 | Edge p90 | Max edge |
|---|---:|---:|---:|---:|---:|
| R21 | 271 | 2.5 | 20.0 | 22.4 | 57.3 |
| R21W | 335 | 2.5 | 20.0 | 25.5 | 57.3 |
| R22 | 308 | 2.7 | 20.0 | 22.4 | 57.3 |
| RD3 | 352 | 3.2 | 20.0 | 20.0 | 42.4 |
| RD_4_12 | 422 | 1.8 | 20.0 | 20.6 | 30.2 |

- Textures per block face: mostly 32x32, 40x40, 48x48 (4bpp/8bpp banked);
  one texture per cell face, so texel density is uniform everywhere.
- Prop/character PDATA (`RDxxMDL.BIN`, base 0x002D4000): edge p50 4-6,
  p90 10-23 units.

## Why BR barely swims (inference from the above)

Affine mapping error grows with the depth ratio across one face. A 20x20 face
has diameter about 28, so with all corners at z >= 32 its depth ratio cannot
exceed about (32+28)/32 = 1.9. This is a typical-cell example, not an all-face
bound: the measured libraries include edges up to 57.3, and a quad's diameter
also includes its diagonals. The extraction does not establish a maximum
diameter for every rendered face. Small faces limit the area lost to whole-face
near rejection; whether those holes stay below the screen needs runtime proof.
"Barely swims" remains a hypothesis, not an observed result of this static study.

Our OoT field faces are roughly 1000-1500 units with near 30: the same ratio
can exceed 30. The P3 split (children still several hundred units across) still
leaves ratios around 20+. BR's numbers say face edge should be on the order of
the near distance (BR: edge 20 ~ 0.6 x near 32) for faces close to the camera.
Unit scale between BR cells and OoT Link is not established here; compare
ratios, not raw units.

Astra review (2026-10-05): retained the supplied static findings without an
independent disc extraction. Qualified the universal ratio/hidden-hole claims
above. Our actual SGL traces do not establish the same near-rejection rule;
backface culling and a camera below sloped ground explain some missing faces.

## Takeaways for our renderer (candidates, not approved changes)

1. Main lever = **offline geometry density near where the camera goes**, not
   runtime tricks. BR does no clip, no runtime split, no perspective trick.
2. Keep near-straddling faces cheap to lose: whole-face reject at near only
   works visually when faces are small. With large OoT faces it makes holes
   (matches the earlier "sky band" report).
3. Guard-band clamp (+/-249 x +/-199 on 352x224) instead of clipping; BR accepts
   the small mapping change on partly off-screen faces.
4. Uniform texel density: one 32-48 px texture per small face rather than one
   big texture stretched over a large face.
5. Budget reality: tiling OoT ground to ~near-distance cells everywhere is far
   beyond VDP1/command budgets. A BR-like target would be a bounded ring of
   small cells around the player only (TR-style local split) or a much larger
   near value combined with small near faces. Either needs the same budget and
   hole/movement checks already listed in TOMB_RAIDER_POLY_NOTES.md (P3/P4).

Unknowns: BR focal value (gbr+380 word) and far value at runtime; exact block
renderer entry (assumed same transform family; all four copies share the
near/clamp code); BR world scale versus characters.
