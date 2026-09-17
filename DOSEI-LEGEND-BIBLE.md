# Dosei Legend engineering rules

## Every animated model: vertex owns bone, not triangle

Link broke because extraction ignored **24 G_MTX commands**. OoT Flex display
lists change matrices within one limb list to join vertices to neighbouring
bones. Assigning the whole face to the drawn limb splits boots, joints and neck.

- Capture matrix ownership at **G_VTX load time**, alongside each cached vertex.
  Later matrix changes must not change already loaded vertices. Cache-slot
  replacement must replace ownership too. A triangle can have three owners.
- Reuse `shared/tools/flex_vertex_owners.py` for OoT Flex actors. The helper
  handles verified segment-D model-view LOAD commands, 64-byte matrix slots,
  and rejects unknown commands, bad alignment, missing owners and bad slots.
  This is NOT a general N64 matrix-stack interpreter. Extend with source-backed
  semantics and tests for other formats; never silently ignore actor transforms.
  The base scene reader also rejects G_MTX unless an importer handles it.
- Build the matrix-slot map from the source skeleton's draw traversal, including
  its display-list/LOD rules. Slots are not necessarily limb indices. Check
  `SkelAnime_DrawFlexLod` / `SkelAnime_DrawFlexLimbLod` in OoT `z_skelanime.c`.
- Keep local coordinates and owner together through baking, deduplication and
  skinning. Do not merge vertices just because rounded bind positions match.
  Do not discard tiny animated faces after integer world rounding.
- Compose parent/joint transforms in source order. Apply scale and axis mapping
  once, at the output boundary. Keep fractional Q16 world coordinates.
- SH-2 has **NO FPU**. Runtime uses integer/fixed-point math. Offline tools may
  use floating point. Check target disassembly for software-float helpers.

Required regression checks for new actor importers: mixed-owner triangle,
matrix switch after vertex load, cache-slot reload, invalid command/slot,
distinct locals with coincident rounded bind positions, and actual C skinning
against an independent pose reference. Then inspect actor in motion in Kronos;
host tests alone cannot prove that seams, face, textures or sorting look right.

Current checks: `game/tests/test_link_geometry_precision.py` and
`game/tests/test_link_animation.py`. Actor inspection: `PERF_PROBE=3`; rebuild
without the option before shipping. Other model formats need their own adapter,
not a claim that Link's segment-D scheme fits every model.
