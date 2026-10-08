/* Infrastructure fixture only: no imported actor or effect profiles. */
extern "C" volatile unsigned int oot_pack_ctor_result;
volatile unsigned int oot_pack_ctor_result;
static volatile unsigned int sProbeSeed = 0x51;
struct PackProbeInit {
    PackProbeInit() { oot_pack_ctor_result = sProbeSeed + 0x32; }
};
static PackProbeInit sInit;
extern "C" unsigned int oot_pack_probe() { return oot_pack_ctor_result; }
