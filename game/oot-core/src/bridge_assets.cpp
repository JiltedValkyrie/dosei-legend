/*
 * Placeholder asset symbols (gameplay_keep, object_kusa, field/dangeon keep).
 * Decomp code only takes their addresses (gSPDisplayList, texture loads). The
 * Phase 2 draw shim maps each address to a prebuilt Saturn mesh/texture, so
 * the contents here are never read. No decomp headers on purpose: C++
 * namespace-scope variables are not name-mangled, so a u64 array satisfies
 * any `extern Gfx x[]` / `extern u64 x[]` declaration at link time.
 * One 8-byte word each keeps every address unique.
 */
typedef unsigned long long u64;
u64 gCircleShadowDL[1];
u64 gCuttableShrubStalkDL[1];
u64 gCuttableShrubTipDL[1];
u64 gDropArrows1Tex[1];
u64 gDropArrows2Tex[1];
u64 gDropArrows3Tex[1];
u64 gDropBombTex[1];
u64 gDropDekuNutTex[1];
u64 gDropDekuSeedsTex[1];
u64 gDropDekuStickTex[1];
u64 gDropKeySmallTex[1];
u64 gDropMagicLargeTex[1];
u64 gDropMagicSmallTex[1];
u64 gDropRecoveryHeartTex[1];
u64 gEffFlash1DL[1];
u64 gFieldBushDL[1];
u64 gGlowCircleDL[1];
u64 gGlowCircleTextureLoadDL[1];
u64 gHeartContainerInteriorDL[1];
u64 gHeartPieceExteriorDL[1];
u64 gHeartPieceInteriorDL[1];
u64 gItemDropDL[1];
u64 gLensOfTruthMaskTex[1];
u64 gRupeeBlueTex[1];
u64 gRupeeDL[1];
u64 gRupeeGreenTex[1];
u64 gRupeeOrangeTex[1];
u64 gRupeePinkTex[1];
u64 gRupeeRedTex[1];
u64 gUnknownCircle6Tex[1];
u64 gUnknownEffBlureTex[1];
u64 object_kusa_DL_000140[1];
u64 object_kusa_DL_0002E0[1];
