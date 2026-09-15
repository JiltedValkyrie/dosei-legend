/* Single-owner, live SCSP PCM player. The SH2 writes only 16-bit registers.
 * The 68000 runs an idle loop and never modifies slots or sample memory.
 * Pitch/address/loop registers change only after an explicit hardware key-off.
 */
#include <yaul.h>
#include "title_player.h"
#include "title_score.h"
#include <assert.h>

extern uint8_t asset_title_pcm[];
extern uint8_t asset_title_pcm_end[];
extern uint8_t asset_title_levels[];
extern uint8_t asset_title_levels_end[];

#define SLOT_REG(slot, offset) (*(volatile uint16_t *)(0x25B00000UL + (slot) * 32 + (offset)))
#define KEY_ON 0x0800
#define KEY_EXECUTE 0x1000
#define LOOP_FORWARD 0x0020

static uint16_t _frame;
static uint16_t _cursor;
static uint16_t _keys[TITLE_VOICES];
static bool _active[TITLE_VOICES];

static void
_stop_all(void)
{
        for (unsigned i = 0; i < TITLE_VOICES; i++) {
                SLOT_REG(i, 0x0C) = 255;
                _keys[i] &= ~KEY_ON;
                SLOT_REG(i, 0) = _keys[i];
                _active[i] = false;
        }
        SLOT_REG(0, 0) = _keys[0] | KEY_EXECUTE;
}

static void
_start(const title_trigger_t *event)
{
        const unsigned slot = event->slot;
        const title_pcm_t *sample = &title_pcm[event->sample];
        const uint32_t address = TITLE_SAMPLE_BASE + sample->offset;

        /* Execute the old note's stop before changing any of its sample
         * registers. This is an SCSP register transaction, not a command
         * flag that another CPU may or may not observe between updates. */
        SLOT_REG(slot, 0x0C) = 255;
        SLOT_REG(slot, 0) = (_keys[slot] & ~KEY_ON) | KEY_EXECUTE;
        _keys[slot] = LOOP_FORWARD | ((address >> 16) & 0xF);
        SLOT_REG(slot, 0) = _keys[slot];
        SLOT_REG(slot, 2) = address & 0xFFFF;
        SLOT_REG(slot, 4) = sample->loop_start;
        SLOT_REG(slot, 6) = sample->loop_end;
        SLOT_REG(slot, 8) = 31;         /* instant attack; software controls gain */
        SLOT_REG(slot, 10) = 31;        /* instant release; no hardware decay */
        SLOT_REG(slot, 14) = 0;         /* no FM modulation */
        SLOT_REG(slot, 16) = event->pitch;
        SLOT_REG(slot, 18) = 0;         /* no hardware LFO */
        SLOT_REG(slot, 20) = 0;         /* no DSP input */
        SLOT_REG(slot, 22) = (7 << 13) | (event->pan << 8);
        _keys[slot] |= KEY_ON;
        SLOT_REG(slot, 0) = _keys[slot] | KEY_EXECUTE;
        _active[slot] = true;
}

void
title_player_init(void)
{
        const uint32_t bytes = asset_title_pcm_end - asset_title_pcm;
        assert((bytes & 1) == 0);
        assert(TITLE_SAMPLE_BASE + bytes <= 0x80000);
        assert(asset_title_levels_end - asset_title_levels == TITLE_FRAMES * TITLE_VOICES);
        /* The SH2 must access sound RAM as words, even for the final bytes.
         * Packed PCM is big-endian signed 16-bit, matching both CPUs. */
        volatile uint16_t *dst = (volatile uint16_t *)(0x25A00000UL + TITLE_SAMPLE_BASE);
        const uint16_t *src = (const uint16_t *)asset_title_pcm;
        for (uint32_t i = 0; i < bytes / 2; i++) {
                dst[i] = src[i];
        }
        for (unsigned i = 0; i < TITLE_VOICES; i++) {
                _keys[i] = 0;
        }
        _stop_all();
        _frame = 0;
        _cursor = 0;
}

void
title_player_update(void)
{
        if (_frame == TITLE_FRAMES) {
                _stop_all();
                _frame = TITLE_LOOP_FRAME;
                _cursor = 0;
                while (_cursor < TITLE_TRIGGER_COUNT && title_triggers[_cursor].frame < _frame) {
                        _cursor++;
                }
        }
        while (_cursor < TITLE_TRIGGER_COUNT && title_triggers[_cursor].frame == _frame) {
                _start(&title_triggers[_cursor++]);
        }
        for (unsigned i = 0; i < TITLE_VOICES; i++) {
                if (_active[i]) {
                        SLOT_REG(i, 0x0C) = asset_title_levels[_frame * TITLE_VOICES + i];
                }
        }
        _frame++;
}
