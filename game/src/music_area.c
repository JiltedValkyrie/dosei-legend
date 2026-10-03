#include <jo/jo.h>
#include "music.h"
#include "music_area.h"
#include "area_music_list.h"

#define AREA_HEADER_BYTES 36u

/* Two slots: the bank fading out keeps its tables while the new one loads. */
static music_bank_t area_bank[2];
static char area_names[2][2][8];
static unsigned char *area_blob[2];
static unsigned int area_seq[2] = { 0xFFFFu, 0xFFFFu };
static unsigned int area_slot;

static unsigned int be32(const unsigned char *p)
{
    return ((unsigned int)p[0] << 24) | ((unsigned int)p[1] << 16) | ((unsigned int)p[2] << 8) | p[3];
}

static void area_name(char *out, unsigned int seq, const char *ext)
{
    static const char hex[] = "0123456789ABCDEF";
    out[0] = 'M'; out[1] = hex[(seq >> 4) & 15]; out[2] = hex[seq & 15]; out[3] = '.';
    out[4] = ext[0]; out[5] = ext[1]; out[6] = ext[2]; out[7] = 0;
}

bool music_area_play(unsigned int seq, unsigned int fade_frames)
{
    unsigned int k = area_slot ^ 1u, pcm_count, trigger_count;
    music_bank_t *bank = &area_bank[k];
    char hdr[8];
    int length = 0;
    unsigned char *blob;

    /* jo_fs_read_file reports a missing file as a fatal error: only open
    ** banks build_area_music.py actually baked. */
    if (seq >= 128u || !(area_music_baked[seq >> 3] & (1u << (seq & 7)))) return false;
    if (area_seq[area_slot] == seq && music_current() == &area_bank[area_slot]) return true;
    if (music_current() == bank || music_busy()) return false; /* slot still audible */
    area_name(hdr, seq, "HDR");
    blob = (unsigned char *)jo_fs_read_file(hdr, &length);
    if (!blob) return false;
    if (length < (int)AREA_HEADER_BYTES || blob[0] != 'M' || blob[1] != 'B' || blob[2] != 'N' || blob[3] != 'K')
        { jo_free(blob); return false; }
    pcm_count = be32(blob + 28);
    trigger_count = be32(blob + 32);
    if ((unsigned int)length != AREA_HEADER_BYTES + 8u * (pcm_count + trigger_count))
        { jo_free(blob); return false; }
    if (area_blob[k]) jo_free(area_blob[k]);
    area_blob[k] = blob;
    area_seq[k] = seq;
    area_name(area_names[k][0], seq, "PCM");
    area_name(area_names[k][1], seq, "LVL");
    bank->pcm_file = area_names[k][0];
    bank->level_file = area_names[k][1];
    bank->frames = be32(blob + 4);
    bank->loop_frame = be32(blob + 8);
    bank->voices = be32(blob + 12);
    bank->sample_base = be32(blob + 16);
    bank->pcm_bytes = be32(blob + 20);
    bank->level_bytes = be32(blob + 24);
    bank->pcm = (const music_pcm_t *)(blob + AREA_HEADER_BYTES);
    bank->triggers = (const music_trigger_t *)(blob + AREA_HEADER_BYTES + 8u * pcm_count);
    bank->trigger_count = trigger_count;
    area_slot = k;
    return music_fade_to(bank, fade_frames);
}
