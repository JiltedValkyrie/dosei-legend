#ifndef DOSEI_INPUT_EDGE_H
#define DOSEI_INPUT_EDGE_H
#include <stdbool.h>

/* VBlank is the only producer; gameplay is the only consumer. Separate
 * counters avoid a read/clear race if VBlank interrupts consumption. */
typedef struct {
    volatile unsigned int produced;
    unsigned int consumed;
    bool held;
} input_edge_t;

static inline void input_edge_sample(input_edge_t *edge, bool held)
{
    if (held && !edge->held) ++edge->produced;
    edge->held = held;
}

static inline bool input_edge_consume(input_edge_t *edge)
{
    unsigned int latest = edge->produced;
    bool pressed = latest != edge->consumed;
    edge->consumed = latest;
    return pressed;
}
#endif
