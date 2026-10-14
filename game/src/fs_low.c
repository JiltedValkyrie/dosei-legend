/* Keep the SDK immutable. Cold GFS tables move into one bounded low-RAM
 * carve; two open handles and allocator behavior stay unchanged.
 *
 * Directory (2026-10-13): GFS keeps an ID-only table (12 B per entry) in the
 * low carve. Names become exact packed 8.3 keys (two u32, base 38, plus a
 * dot flag) in the retired cart MUSICTRG gap, indexed by file id. ISO order
 * equals key order (checked at boot and by check_disc_directory.py), so a
 * binary search yields the GFS file id. The project maps every
 * GFS_NameToId call to dosei_gfs_name_to_id (makefile). */
#include "fs_capacity.h"
#include "ram_low.h"
#include "ram_cart.h"
#include <SEGA_GFS.H>
static GfsDirName __jo_fs_dirname[JO_FS_MAX_FILES]
    __attribute__((section(".lowfs")));
static char __jo_fs_work[GFS_WORK_SIZE(JO_MAX_FS_BACKGROUND_JOBS)]
    __attribute__((section(".lowfs"),aligned(4)));
static GfsDirId fs_ids[DOSEI_FS_MAX_FILES]
    __attribute__((section(".lowfs"),aligned(4)));
typedef char fs_directory_fits[sizeof(__jo_fs_dirname)+sizeof(__jo_fs_work)+sizeof(fs_ids)<=RAM_LOW_FS_DIRECTORY_BYTES?1:-1];
typedef char fs_keys_fit[DOSEI_FS_MAX_FILES*8u<=RAM_CART_FSKEYS_BYTES?1:-1];
/* Boot-only name table: the forest bank carve is unused until a scene loads. */
#define FS_TEMP_ENTRIES (RAM_LOW_FOREST_BANK_BYTES / sizeof(GfsDirName))
typedef char fs_temp_fits[FS_TEMP_ENTRIES>DOSEI_FS_MAX_FILES?1:-1];
static GfsDirTbl fs_idtbl;
static int fs_count;
#undef JO_IS_ARRAY_INSIDE_USER_RAM_AREA
#define JO_IS_ARRAY_INSIDE_USER_RAM_AREA(a) \
    ((JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)) && \
      JO_IS_PTR_INSIDE_USER_RAM_AREA((unsigned char *)(a)+sizeof(a))) || \
     ((unsigned int)(a)>=RAM_LOW_ADDRESS+RAM_LOW_FS_DIRECTORY_OFFSET && \
      (unsigned int)(a)+sizeof(a)<=RAM_LOW_ADDRESS+RAM_LOW_FS_DIRECTORY_OFFSET+RAM_LOW_FS_DIRECTORY_BYTES))
/* Cover whole-file, metadata and streaming Jo callers without editing SDK.
 * Music uses raw GFS on the main thread; its next service resumes read-ahead. */
#include "music.h"
#define GFS_Open(id) (music_yield_cd() ? GFS_Open(id) : (GfsHn)0)
#define GFS_Load(id, off, buf, size) \
    (music_yield_cd() ? GFS_Load(id, off, buf, size) : -1)
#define GFS_Fread(h, n, buf, size) \
    (music_yield_cd() ? GFS_Fread(h, n, buf, size) : -1)
/* Replace only the two functions that build name tables; keep the rest. */
#define jo_fs_init jo_fs_init_sdk_name_table
#define jo_fs_cd jo_fs_cd_sdk_name_table
#include "fs.c"
#undef jo_fs_init
#undef jo_fs_cd
#undef GFS_Open
#undef GFS_Load
#undef GFS_Fread
#include "fs_range.h"

static unsigned int *fs_keys(void)
{
    return (unsigned int *)(RAM_CART_FIXED_ADDRESS + RAM_CART_FSKEYS_OFFSET);
}

static int fs_symbol(int c)
{
    if (c >= '0' && c <= '9') return c - '0' + 1;
    if (c >= 'A' && c <= 'Z') return c - 'A' + 11;
    return c == '_' ? 37 : -1;
}

/* Exact and order-preserving for ISO 8.3 names; anything else is rejected,
 * so a name that never matched in GFS still never matches. Disc records may
 * carry the ISO ";1" version suffix; requests may not. */
static bool fs_key(const char *name, unsigned int length, bool disc, unsigned int key[2])
{
    int sym[11] = {0}, v;
    unsigned int i = 0, k = 0, dot = 0, a = 0, b = 0;
    if (disc) {
        unsigned int end = 0;
        while (end < length && name[end] && name[end] != ';') ++end;
        length = end;
    }
    for (; i < length && name[i] && name[i] != '.'; ++i) {
        if (k >= 8 || (v = fs_symbol((unsigned char)name[i])) < 0) return false;
        sym[k++] = v;
    }
    if (!k) return false;
    if (i < length && name[i] == '.') {
        dot = 1;
        for (++i, k = 8; i < length && name[i]; ++i) {
            if (k >= 11 || (v = fs_symbol((unsigned char)name[i])) < 0) return false;
            sym[k++] = v;
        }
    }
    if (i < length && name[i]) return false;
    for (k = 0; k < 6; ++k) a = a * 38u + (unsigned int)sym[k];
    for (; k < 11; ++k) b = b * 38u + (unsigned int)sym[k];
    key[0] = a; key[1] = b * 2u + dot;
    return true;
}

static bool fs_key_less(const unsigned int *x, const unsigned int *y)
{
    return x[0] < y[0] || (x[0] == y[0] && x[1] < y[1]);
}

/* Validate the whole directory before touching the live tables. */
static bool fs_index(const GfsDirName *names, int n)
{
    unsigned int key[2], prev[2] = {0, 1}, *keys = fs_keys();
    int i;
    if (n <= 2 || n > DOSEI_FS_MAX_FILES || !ram_cart_present()) return false;
    for (i = 2; i < n; ++i) {
        if (!fs_key((const char *)names[i].fname, GFS_FNAME_LEN, true, key) || !fs_key_less(prev, key))
            return false;
        prev[0] = key[0]; prev[1] = key[1];
    }
    for (i = 0; i < n; ++i) {
        fs_ids[i].dirrec = names[i].dirrec;
        if (i < 2) { keys[2 * i] = 0; keys[2 * i + 1] = (unsigned int)i; }
        else fs_key((const char *)names[i].fname, GFS_FNAME_LEN, true, keys + 2 * i);
    }
    GFS_DIRTBL_TYPE(&fs_idtbl) = GFS_DIR_ID;
    GFS_DIRTBL_DIRID(&fs_idtbl) = fs_ids;
    GFS_DIRTBL_NDIR(&fs_idtbl) = n;
    if (GFS_SetDir(&fs_idtbl) < 0) { fs_count = 0; return false; }
    fs_count = n;
    return true;
}

Sint32 dosei_gfs_name_to_id(Sint8 *fname)
{
    unsigned int key[2], *keys = fs_keys();
    int lo = 2, hi = fs_count - 1;
    if (!fname || !fs_key((const char *)fname, 0xffffu, false, key)) return GFS_ERR_NEXIST;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        const unsigned int *k = keys + 2 * mid;
        if (k[0] == key[0] && k[1] == key[1]) return mid;
        if (fs_key_less(k, key)) lo = mid + 1; else hi = mid - 1;
    }
    return GFS_ERR_NEXIST;
}

int jo_fs_init(void)
{
    static GfsDirTbl names; /* GFS keeps this pointer until fs_index replaces it */
    int i, n;
    JO_ZERO(__jo_fs_background_job_count);
    for (i = 0; i < JO_MAX_FS_BACKGROUND_JOBS; ++i)
        __jo_fs_background_jobs[i].active = false;
    GFS_DIRTBL_TYPE(&names) = GFS_DIR_NAME;
    GFS_DIRTBL_DIRNAME(&names) = (GfsDirName *)RAM_LOW(RAM_LOW_FOREST_BANK_OFFSET);
    GFS_DIRTBL_NDIR(&names) = FS_TEMP_ENTRIES;
    n = GFS_Init(JO_OPEN_MAX, __jo_fs_work, &names);
    /* Keys live on the cart: without it, main shows the cart message. */
    if (!ram_cart_present()) return 0;
    /* A full temporary table may be truncated: fail rather than guess. */
    if (n <= 2 || n >= (int)FS_TEMP_ENTRIES ||
        !fs_index(GFS_DIRTBL_DIRNAME(&names), n)) {
        jo_core_error("CD directory: %d entries, capacity %d", n, DOSEI_FS_MAX_FILES);
        return 0;
    }
    return 1;
}

/* Subdirectory support: reload names into a temporary heap table, then
 * index it. The current directory is unchanged if anything fails. */
void jo_fs_cd(const char *const sub_dir)
{
    GfsDirTbl names;
    GfsDirName *table;
    Sint32 fid, n;
    if (!sub_dir || (fid = GFS_NameToId((Sint8 *)sub_dir)) < 0) return;
    table = (GfsDirName *)jo_malloc((DOSEI_FS_MAX_FILES + 1) * sizeof(GfsDirName));
    if (!table) { jo_core_error("jo_fs_cd: no memory"); return; }
    GFS_DIRTBL_TYPE(&names) = GFS_DIR_NAME;
    GFS_DIRTBL_DIRNAME(&names) = table;
    GFS_DIRTBL_NDIR(&names) = DOSEI_FS_MAX_FILES + 1;
    n = GFS_LoadDir(fid, &names);
    if (n <= 2 || n > DOSEI_FS_MAX_FILES || !fs_index(table, (int)n))
        jo_core_error("jo_fs_cd: %s not indexed", sub_dir);
    jo_free(table);
}

int fs_file_size(const char *name)
{
    int id = GFS_NameToId((Sint8 *)name);
    return id < 0 ? -1 : jo_fs_get_file_size(id);
}

bool fs_read_sectors(const char *name, unsigned int sector, void *buffer,
                     unsigned int bytes)
{
    int id, size, retry;
    unsigned int offset;
    if (!buffer || !bytes || sector > 0x7fffffffu / JO_SECTOR_SIZE) return false;
    offset = sector * JO_SECTOR_SIZE;
    id = GFS_NameToId((Sint8 *)name);
    if (id < 0 || (size = jo_fs_get_file_size(id)) < 0 ||
        offset > (unsigned int)size || bytes > (unsigned int)size - offset)
        return false;
    for (retry = JO_READ_RETRY_COUNT; retry > 0; --retry) {
        if (!music_yield_cd()) return false;
        if (GFS_Load(id, (Sint32)sector, buffer, (Sint32)bytes) == (Sint32)bytes)
            return true;
        jo_spin_wait(JO_READ_SPIN_WAIT);
    }
    return false;
}

void fs_low_init(void)
{
    unsigned i;unsigned char *p=RAM_LOW(RAM_LOW_FS_DIRECTORY_OFFSET);
    for(i=0;i<RAM_LOW_FS_DIRECTORY_BYTES;++i)p[i]=0;
}
