/* Preserve the SDK register dump and add memory evidence before its reset.
 * Kronos reports PC+2 to the guest illegal-instruction handler, so show both
 * saved PC and the preceding instruction. P2 bypasses the SH-2 data cache. */
#include <yaul.h>
#include <stdio.h>
#include "crash_probe.h"

extern void __exception_assert(const cpu_registers_t *, const char *);
extern void crash_illegal(void), crash_slot(void);

void crash_probe_init(void)
{
        cpu_intc_ihr_set(CPU_INTC_INTERRUPT_ILLEGAL_INSTRUCTION, crash_illegal);
        cpu_intc_ihr_set(CPU_INTC_INTERRUPT_ILLEGAL_SLOT, crash_slot);
}

void crash_exception(const cpu_registers_t *regs, const char *name)
{
        static char message[192];
        const uint32_t pc = regs->pc;
        if (!(pc & 1) && pc >= 0x06004002 && pc < 0x06100000) {
                const volatile uint16_t *cached = (const volatile uint16_t *)(pc - 2);
                const volatile uint16_t *uncached = (const volatile uint16_t *)((pc - 2) | 0x20000000);
                const unsigned c0 = cached[0], c1 = cached[1];
                const unsigned u0 = uncached[0], u1 = uncached[1];
                snprintf(message, sizeof(message),
                    "%s\nAt PC-2 / PC:\nP0 %04X %04X\nP2 %04X %04X",
                    name, c0, c1, u0, u1);
                name = message;
        }
        __exception_assert(regs, name);
}
