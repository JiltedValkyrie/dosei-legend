# M5/M6 source room ledger

Generated from US 1.2 child-day headers. Source presence is not runtime support.
Full coordinates, rotations, object dependencies, collision cameras/water and
source fingerprints: `game/build/generated/progression_manifest.json`.

Door_Shutter gates require their actor state; never treat them as open tunnels.
M6 Sacred Forest Meadow and M7 Field destinations remain integration boundaries.

## ydan

12 rooms; 2321 collision triangles.

| Spawn | Room | Position | Yaw |
|---|---|---|---|
| 0 | 0 | [-4, 0, 603] | 8000 |
| 1 | 9 | [-850, -1880, -894] | 0FA5 |

| Transition | Rooms | Actor | Params | Kind |
|---|---|---|---|---|
| 0 | 0 / 1 | Door_Shutter | 007F | None |
| 1 | 5 / 6 | Door_Shutter | 0083 | None |
| 2 | 3 / 4 | Door_Shutter | 003F | None |
| 3 | 8 / 7 | Door_Shutter | 003F | None |
| 4 | 11 / 9 | Door_Shutter | 007F | None |
| 5 | 2 / 1 | Door_Shutter | 007F | None |
| 6 | 0 / 10 | Door_Shutter | 00BC | None |
| 7 | 7 / 6 | Door_Shutter | 0083 | None |
| 8 | 5 / 4 | Door_Shutter | 0084 | None |
| 9 | 0 / 3 | En_Holl | 00BF | 2 |
| 10 | 3 / 9 | En_Holl | 00BF | 2 |
| 11 | 7 / 3 | En_Holl | 013F | 4 |

| Exit slot | Entrance | Destination | Spawn |
|---|---|---|---|
| 1 | 0209 | SCENE_KOKIRI_FOREST | 1 |
| 2 | 040F | SCENE_DEKU_TREE_BOSS | 0 |

### Room 0

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_Sw | 0000 | [283, 478, 357] |
| En_Sw | 0000 | [416, 520, 179] |
| En_Sw | 0000 | [327, 678, 321] |
| En_St | 0001 | [-67, 1069, 255] |
| En_St | 0001 | [256, 1071, -62] |
| En_St | 0001 | [-179, 1072, -190] |
| En_Kusa | FF01 | [391, 0, -156] |
| En_Kusa | FF01 | [355, 0, -233] |
| En_Kusa | FF01 | [307, 0, -289] |
| En_Kusa | FF01 | [80, 293, -414] |
| En_Kusa | FF01 | [142, 307, -399] |
| En_Dekubaba | 0000 | [-218, 0, 63] |
| En_Dekubaba | 0000 | [-41, 0, -230] |
| En_Dekubaba | 0000 | [194, 0, 105] |
| En_Box | 0823 | [333, 360, 253] |
| Bg_Ydan_Sp | 0FC5 | [0, 0, 0] |
| Elf_Msg | 0A03 | [-417, 400, 427] |
| Elf_Msg | 0A03 | [-513, 800, 10] |
| Elf_Msg | 9301 | [0, -24, 0] |
| Elf_Msg | 1F02 | [118, 0, -325] |
| Elf_Msg | 1F02 | [-1394, 280, 1188] |
| Elf_Msg | 1F02 | [-1186, 355, 1398] |
| Elf_Msg | 1F02 | [-1176, 480, 1485] |
| Elf_Msg | 1F02 | [465, 360, 114] |
| Elf_Msg | 1F02 | [282, 360, 360] |
| En_Item00 | 2C03 | [-25, 280, -81] |
| En_Item00 | 2D03 | [87, 744, -16] |

### Room 1

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_Hintnuts | 1A00 | [-695, 400, 692] |

### Room 2

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_d_lift, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_Kusa | FF01 | [-1229, 280, 1006] |
| En_Kusa | FF01 | [-1280, 280, 1026] |
| En_Kusa | FF01 | [-1005, 280, 1216] |
| En_Kusa | FF01 | [-1018, 280, 1263] |
| Elf_Msg2 | 3F04 | [-1065, 590, 1074] |
| Bg_Ydan_Sp | 1FFF | [-1047, 613, 1077] |
| En_Box | 00A1 | [-1391, 480, 1391] |
| En_Box | 5905 | [-1108, 656, 1582] |
| Obj_Lift | 0050 | [-1188, 390, 1190] |
| Bg_Ydan_Maruta | 0123 | [-1066, 560, 1066] |

### Room 3

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_Karebaba | 0001 | [-546, -820, 392] |
| En_Kusa | FF01 | [48, -880, 130] |
| En_Kusa | FF01 | [48, -880, 187] |
| En_Dekubaba | 0000 | [-637, -820, 181] |
| En_Dekubaba | 0000 | [-50, -880, 204] |
| En_Dekubaba | 0000 | [-453, -820, -4] |
| Obj_Syokudai | 2400 | [-465, -780, 430] |
| Obj_Syokudai | 2400 | [-425, -770, -430] |
| Obj_Syokudai | 2400 | [-865, -760, -120] |
| Obj_Syokudai | 2400 | [-866, -760, 120] |
| Bg_Ydan_Hasi | FF02 | [-1080, 600, 0] |
| Bg_Ydan_Sp | 1080 | [21, -850, -277] |
| En_Sw | 8102 | [-281, -815, -436] |
| Obj_Syokudai | 03C2 | [26, -845, -290] |
| Obj_Switch | 0200 | [-150, -845, -289] |
| En_Sw | 8104 | [95, -713, -43] |
| En_Box | 5904 | [53, -845, -278] |
| Bg_Ydan_Sp | 0FC6 | [-635, -820, 0] |
| Bg_Ydan_Sp | 1FC9 | [-82, -880, 517] |
| Obj_Makeoshihiki | FF10 | [-365, -905, -290] |

### Room 4

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts

| Actor | Params | Position |
|---|---|---|
| En_Kusa | FF01 | [49, -880, 752] |
| En_Kusa | FF01 | [79, -880, 794] |
| En_Kusa | FF01 | [-202, -880, 751] |
| En_Kusa | FF01 | [-228, -880, 792] |
| En_Hintnuts | 9B00 | [-66, -880, 962] |
| Obj_Switch | 0412 | [-314, -759, 960] |

### Room 5

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_St | 0000 | [-1360, -806, 1079] |
| En_Kusa | FF01 | [-1361, -870, 840] |
| En_Kusa | FF01 | [-1310, -870, 840] |
| Obj_Oshihiki | FFC0 | [-1365, -880, 1200] |
| Bg_Ydan_Hasi | FF00 | [-835, -880, 1050] |
| Bg_Ydan_Maruta | 00FF | [-835, -860, 1050] |
| Elf_Msg | 0F08 | [-1364, -883, 1188] |
| Elf_Msg | 510C | [-700, -880, 941] |
| Elf_Msg | 510C | [-435, -880, 1163] |
| Obj_Switch | 3E00 | [-835, -1020, 1264] |
| Bg_Ydan_Hasi | 3E01 | [-835, -900, 1050] |

### Room 6

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_dekunuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts

| Actor | Params | Position |
|---|---|---|
| En_Karebaba | 0001 | [-2038, -760, 1252] |
| En_Karebaba | 0001 | [-1674, -760, 1248] |
| En_Kusa | FF01 | [-1919, -760, 820] |
| En_Kusa | FF01 | [-1796, -760, 821] |
| En_Dekubaba | 0000 | [-1843, -760, 1033] |
| Obj_Syokudai | 2400 | [-1855, -760, 1212] |
| Obj_Syokudai | 1083 | [-1966, -760, 964] |
| Obj_Syokudai | 1083 | [-1743, -760, 965] |

### Room 7

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_bwall

| Actor | Params | Position |
|---|---|---|
| En_Karebaba | 0001 | [-2174, -760, 295] |
| En_St | 0000 | [-1854, -642, 488] |
| En_Kusa | FF01 | [-2025, -760, -301] |
| En_Kusa | FF01 | [-1955, -760, -296] |
| En_Dekubaba | 0000 | [-2292, -760, -320] |
| En_Goma | 0008 | [-1869, -320, 14] |
| En_Goma | 0008 | [-2039, -320, 15] |
| En_Goma | 0008 | [-1951, -320, 140] |
| Obj_Syokudai | 2400 | [-2240, -760, 75] |
| Bg_Ydan_Sp | 1FC7 | [-1355, -820, 3] |
| Bg_Ydan_Sp | 1FC8 | [-2229, -760, -262] |
| Bg_Breakwall | 2012 | [-2345, -760, -381] |

### Room 8

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_St | 0000 | [-2684, -735, -712] |
| En_Sw | 8101 | [-2577, -626, -411] |

### Room 9

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts

| Actor | Params | Position |
|---|---|---|
| En_Kusa | FF01 | [-269, -1880, -643] |
| En_Kusa | FF01 | [-273, -1880, -577] |
| En_Kusa | FF01 | [-273, -1880, -515] |
| En_Hintnuts | 0001 | [-662, -1880, -957] |
| En_Hintnuts | 0002 | [-311, -1880, -904] |
| En_Hintnuts | 9C03 | [-946, -1880, -767] |
| En_Item00 | 2E03 | [-885, -1950, -185] |
| En_Item00 | 3003 | [-820, -1960, -76] |
| En_Item00 | 3103 | [-354, -1943, -206] |

### Room 10

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts, object_gi_sutaru

| Actor | Params | Position |
|---|---|---|
| En_Karebaba | 0001 | [-1472, 840, -157] |
| En_St | 0000 | [-1082, 993, 268] |
| En_Kusa | FF01 | [-1516, 840, 142] |
| En_Kusa | FF01 | [-1444, 840, 169] |
| En_Dekubaba | 0000 | [-884, 720, 136] |
| Obj_Syokudai | 2400 | [-635, 800, -132] |
| Elf_Msg2 | 3F06 | [-722, 860, 159] |
| En_Box | 0802 | [-1491, 840, 1] |
| En_Box | 5906 | [-1082, 820, 387] |
| En_Sw | 8108 | [-1081, 866, 501] |
| Obj_Syokudai | 107C | [-722, 800, 157] |
| Obj_Switch | 3D00 | [-739, 800, -147] |
| Bg_Ydan_Hasi | 3D02 | [-1080, 580, 0] |

### Room 11

Objects: object_ydan_objects, object_gol, object_st, object_dekubaba, object_hintnuts, object_box, object_syokudai, object_kusa, object_gi_heart, object_gi_nuts

| Actor | Params | Position |
|---|---|---|
## ydan_boss

2 rooms; 152 collision triangles.

| Spawn | Room | Position | Yaw |
|---|---|---|---|
| 0 | 1 | [321, -640, 772] | 91C7 |

| Transition | Rooms | Actor | Params | Kind |
|---|---|---|---|---|
| 0 | 0 / 1 | Door_Shutter | 003F | None |

| Exit slot | Entrance | Destination | Spawn |
|---|---|---|---|
| 1 | 0252 | SCENE_DEKU_TREE | 1 |

### Room 0

Objects: object_ydan_objects, object_goma, object_gol, object_warp1, object_gi_hearts, object_kusa

| Actor | Params | Position |
|---|---|---|

### Room 1

Objects: object_ydan_objects, object_goma, object_gol, object_warp1, object_gi_hearts, object_kusa

| Actor | Params | Position |
|---|---|---|
| Boss_Goma | FFFF | [-160, -280, -371] |
| En_Kusa | FF01 | [194, -640, -974] |
| En_Kusa | FF01 | [480, -640, -681] |
| En_Kusa | FF01 | [-855, -640, -596] |
| En_Kusa | FF01 | [-848, -640, -166] |
| En_Kusa | FF01 | [-444, -640, 323] |
| En_Kusa | FF01 | [-646, -640, 108] |
| En_Kusa | FF01 | [525, -640, -375] |
| En_Kusa | FF01 | [545, -640, -75] |
## spot10

10 rooms; 2210 collision triangles.

| Spawn | Room | Position | Yaw |
|---|---|---|---|
| 0 | 0 | [-3, 0, 295] | 8000 |
| 1 | 8 | [802, 0, -2740] | 0000 |
| 2 | 0 | [-304, 0, 1] | 4000 |
| 3 | 0 | [-2, 0, -308] | 0000 |
| 4 | 0 | [300, 0, -1] | C000 |
| 5 | 7 | [1876, 0, -2396] | C000 |
| 6 | 2 | [794, -26, -1112] | 0000 |
| 7 | 3 | [2188, -260, -855] | C000 |
| 8 | 5 | [-1509, -200, 1603] | 3B06 |
| 9 | 5 | [-901, -200, 1601] | C000 |

| Transition | Rooms | Actor | Params | Kind |
|---|---|---|---|---|
| 0 | 4 / 3 | En_Holl | 003F | 0 |
| 1 | 3 / 2 | En_Holl | 003F | 0 |
| 2 | 2 / 1 | En_Holl | 003F | 0 |
| 3 | 1 / 0 | En_Holl | 003F | 0 |
| 4 | 9 / 0 | En_Holl | 003F | 0 |
| 5 | 6 / 4 | En_Holl | 003F | 0 |
| 6 | 5 / 9 | En_Holl | 003F | 0 |
| 7 | 7 / 4 | En_Holl | 003F | 0 |
| 8 | 8 / 7 | En_Holl | 003F | 0 |

| Exit slot | Entrance | Destination | Spawn |
|---|---|---|---|
| 1 | 0286 | SCENE_KOKIRI_FOREST | 6 |
| 2 | 00FC | SCENE_SACRED_FOREST_MEADOW | 0 |
| 3 | 011E | SCENE_LOST_WOODS | 0 |
| 4 | 01AD | SCENE_LOST_WOODS | 2 |
| 5 | 01B1 | SCENE_LOST_WOODS | 3 |
| 6 | 04C6 | SCENE_LOST_WOODS | 4 |
| 7 | 04E2 | SCENE_GORON_CITY | 3 |
| 8 | 01DD | SCENE_ZORAS_RIVER | 4 |
| 9 | 0185 | SCENE_HYRULE_FIELD | 3 |
| 10 | 020D | SCENE_KOKIRI_FOREST | 2 |

### Room 0

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [287, 0, -2] |
| Object_Kankyo | 0000 | [52, 0, -52] |

### Room 1

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [796, 0, -274] |
| En_Skj | 1BFF | [1123, -140, 340] |
| En_Skj | 07FF | [1265, -94, 420] |
| En_Skj | 0BFF | [1183, -72, 476] |
| En_Dnt_Nomal | FFFF | [1368, 80, -173] |
| En_Wonder_Item | 123F | [1256, -152, 194] |
| En_Wonder_Item | 123F | [1038, -180, 557] |
| En_Wonder_Item | 127F | [1371, -180, 497] |

### Room 2

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [1061, 0, -803] |
| Object_Kankyo | 0000 | [798, 0, -897] |
| En_Kusa | 0200 | [645, 0, -638] |
| En_Kusa | 0200 | [633, 0, -676] |
| En_Kusa | 0210 | [676, 0, -651] |
| En_Owl | 02C7 | [955, 210, -798] |
| Obj_Bombiwa | 8011 | [915, -5, -925] |
| Door_Ana | 0014 | [915, 0, -925] |

### Room 3

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [1596, 0, -1067] |
| Object_Kankyo | 0000 | [1735, 0, -792] |
| En_Okuta | FF00 | [2114, -20, -847] |
| Shot_Sun | FF41 | [1930, 0, -795] |
| En_Item00 | 3400 | [2215, -260, -850] |
| En_Item00 | 3500 | [2164, -260, -850] |
| En_Item00 | 3600 | [2113, -260, -850] |
| En_Item00 | 3700 | [2061, -260, -853] |
| En_Item00 | 3900 | [2194, -260, -895] |
| En_Item00 | 3A00 | [2156, -260, -937] |
| En_Item00 | 3B00 | [2193, -260, -813] |
| En_Item00 | 3C00 | [2153, -260, -779] |

### Room 4

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [1594, 0, -1880] |
| Object_Kankyo | 0000 | [1588, 0, -1581] |

### Room 5

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| Object_Kankyo | 0000 | [-1191, -220, 1626] |
| En_Shopnuts | 0009 | [-1137, -200, 2180] |
| Obj_Makekinsuta | 4E01 | [-1220, 0, 935] |
| Obj_Bean | 1F04 | [-1220, 0, 935] |
| En_Gs | 381D | [-1305, -226, 2300] |

### Room 6

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| Object_Kankyo | 0000 | [509, -20, -1568] |
| Obj_Mure | 5324 | [77, 28, -1590] |
| En_Shopnuts | 0000 | [653, 0, -1726] |
| En_Shopnuts | 0001 | [443, 0, -1357] |
| Obj_Makekinsuta | 4E02 | [610, 0, -1770] |
| Obj_Bean | 1F12 | [610, 0, -1770] |
| Door_Ana | 00F3 | [80, -20, -1600] |

### Room 7

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [1348, 0, -2389] |
| En_Kusa | 0200 | [1445, 0, -2238] |
| En_Kusa | 0200 | [1433, 0, -2276] |
| En_Kusa | 0210 | [1476, 0, -2251] |
| En_Item00 | 1301 | [1720, 0, -2510] |
| Obj_Bombiwa | 001E | [1720, 0, -2510] |

### Room 8

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_River_Sound | 000C | [793, 0, -2657] |
| En_River_Sound | 000C | [799, 0, -3155] |
| Object_Kankyo | 0000 | [794, 0, -2379] |
| En_Kusa | 0200 | [952, 0, -2275] |
| En_Kusa | 0200 | [965, 0, -2241] |
| En_Kusa | 0200 | [926, 0, -2232] |
| En_Owl | 0308 | [798, 208, -2246] |
| Door_Ana | 00F5 | [670, 0, -2520] |
| Obj_Bombiwa | 801F | [670, 0, -2520] |

### Room 9

Objects: object_skj, object_shopnuts, object_dnk, object_yabusame_point, object_owl, object_mamenoki, object_bombiwa, object_gs, object_hintnuts, object_gi_dekupouch, object_st

| Actor | Params | Position |
|---|---|---|
| En_Skj | 03FF | [-1132, 80, -128] |
| En_Skj | 17FF | [-951, 20, 52] |
