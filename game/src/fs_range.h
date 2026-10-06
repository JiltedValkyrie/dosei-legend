#ifndef DOSEI_FS_RANGE_H
#define DOSEI_FS_RANGE_H
#include <stdbool.h>
int fs_file_size(const char *name);
/* Sector-addressed read into caller storage; no allocation or terminator. */
bool fs_read_sectors(const char *name, unsigned int sector, void *buffer,
                     unsigned int bytes);
#endif
