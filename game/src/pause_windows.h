#ifndef PAUSE_WINDOWS_H
#define PAUSE_WINDOWS_H
#include <stdbool.h>
bool pause_windows_update(void);
void pause_windows_reset(void);
bool pause_windows_failed(void);
bool pause_windows_text_ready(void);
void pause_windows_print(int x, int y, const char *text);
#define pause_windows_printf(X,Y,...) do { sprintf(__jo_sprintf_buf,__VA_ARGS__); pause_windows_print(X,Y,__jo_sprintf_buf); } while (0)
#endif
