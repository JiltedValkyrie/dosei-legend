/* C-reference scene for bg_shim_scenario.c: Kokiri Forest S1.COL in the C library. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "kokiri_collision.h"

void scene_init(const char *col_file)
{
        static uint8_t file[1 << 20], store[1 << 20];
        static bg_mesh_t mesh;
        FILE *f = fopen(col_file, "rb");
        uint32_t len = (uint32_t)fread(file, 1, sizeof file, f), need;
        fclose(f);
        need = bg_mesh_bytes(file, len);
        if (!need || !bg_mesh_decode(file, len, store, need, &mesh)) { puts("C mesh load failed"); exit(2); }
        bg_scene_set(&mesh);
}

void scene_reenter(const char *col_file)
{
        uint32_t i;
        bg_dyna_clear();
        for (i = 0; i < 16; i++) bg_water_reset_surface(i);
        scene_init(col_file);
}
