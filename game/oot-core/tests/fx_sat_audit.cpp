/*
 * Host-only Fx saturation collector (Wave 0 range audit). Link into a probe
 * built with -DFX_SAT_AUDIT; at exit it prints each saturating call site
 * ("FXSAT pc count") to stderr. Symbolize with addr2line -f -C -e EXE.
 * Plain C style: probe flags use -nostdinc and the prelude's keyword renames.
 */
extern "C" int dprintf(int fd, const char* fmt, ...);
extern "C" int atexit(void (*fn)(void));

#define FX_SAT_SITES 512
static void* sSitePc[FX_SAT_SITES];
static unsigned long sSiteCount[FX_SAT_SITES];
static int sSites;
static int sRegistered;

static void fx_sat_dump(void) {
    for (int i = 0; i < sSites; i++) {
        dprintf(2, "FXSAT %p %lu\n", sSitePc[i], sSiteCount[i]);
    }
}

void fx_sat_hit(void* site) {
    if (!sRegistered) {
        sRegistered = 1;
        atexit(fx_sat_dump);
    }
    for (int i = 0; i < sSites; i++) {
        if (sSitePc[i] == site) {
            sSiteCount[i]++;
            return;
        }
    }
    if (sSites < FX_SAT_SITES) {
        sSitePc[sSites] = site;
        sSiteCount[sSites] = 1;
        sSites++;
    }
}
