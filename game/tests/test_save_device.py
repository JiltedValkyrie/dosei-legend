"""Exercise actual save-device failure handling and BIOS workspace mounting."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class SaveDevice(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_read_write_errors_and_mount_diagnostics(self):
        source = (ROOT / 'src/save_device.c').read_text().replace('#include <jo/jo.h>', '')
        source = source.replace('#include "save_device.h"',
                                '#include "' + (ROOT / 'src/save_device.h').as_posix() + '"')
        source = source.replace('#include "ui_preferences.h"',
                                '#include "' + (ROOT / 'src/ui_preferences.h').as_posix() + '"')
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#define JoInternalMemoryBackup 0
static int bios_status, mount_ok=1, exists, read_ok=1, write_ok=1, writes, decoded;
static unsigned char contents[4096];
static unsigned content_bytes;
static int save_backup_status(void) { return bios_status; }
static bool jo_backup_mount(int d) { assert(d==0); return mount_ok; }
static bool jo_backup_file_exists(int d,const char *s) {
    assert(d==0); if (!strcmp(s,"DOSEICFG")) return false; return exists;
}
static void *jo_backup_load_file_contents(int d,const char *s,unsigned *n) {
    assert(d==0); if (!read_ok) return 0;
    *n=content_bytes; void *p=malloc(*n); memcpy(p,contents,*n); return p;
}
static bool jo_backup_save_file_contents(int d,char *s,char *c,void *p,unsigned n) {
    assert(d==0); ++writes;
    if (!write_ok) return false;
    assert(n<=sizeof(contents));memcpy(contents,p,n);content_bytes=n; exists=1; return true;
}
static bool jo_backup_delete_file(int d,const char *s) { return true; }
static int jo_backup_get_free_block_count(int d) { return 20; }
#define jo_free free
''' + source + r'''
save_state_t save_state;
void ui_preferences_reset(void) {}
void ui_preferences_pack(uint8_t *p) { memset(p,0,UI_PREF_BYTES); }
bool ui_preferences_unpack(const uint8_t *p,unsigned n) { return true; }
void save_file_pack(const save_state_t *s,uint8_t *p) { memset(p,42,SAVE_FILE_BYTES); }
save_file_status save_file_unpack(save_state_t *s,const uint8_t *p,unsigned n) {
    ++decoded; assert(n==SAVE_FILE_BYTES && p[0]==42); return SAVE_FILE_OK;
}
save_file_status save_file_read_summary(save_file_summary *s,const uint8_t *p,unsigned n) {
    if(s) memset(s,0,sizeof(*s)); return p ? SAVE_FILE_OK : SAVE_FILE_EMPTY;
}
int main(void) {
    save_file_summary summary;
    bios_status=2; mount_ok=0;
    assert(!save_device_init()); assert(!strcmp(save_device_error(),"INIT BACKUP IN BIOS"));
    assert(!save_device_write(0) && writes==0);
    assert(save_device_summary(0,&summary)==SAVE_FILE_EMPTY); /* explicit unsaved play */
    mount_ok=1; bios_status=0; assert(save_device_init());
    assert(save_device_read(0)==SAVE_FILE_EMPTY && decoded==0);
    bios_status=8; assert(save_device_read(0)==SAVE_FILE_DEVICE_ERROR && decoded==0);
    exists=1; read_ok=0;
    assert(save_device_summary(0,&summary)==SAVE_FILE_DEVICE_ERROR && !summary.present);
    assert(save_device_read(0)==SAVE_FILE_DEVICE_ERROR && decoded==0);
    write_ok=0; bios_status=4; assert(!save_device_write(0));
    assert(!strcmp(save_device_error(),"BACKUP MEMORY FULL"));
    bios_status=7; assert(!save_device_write(0));
    assert(!strcmp(save_device_error(),"BACKUP VERIFY FAILED"));
    write_ok=read_ok=1; bios_status=0; assert(save_device_write(2));
    assert(save_device_read(2)==SAVE_FILE_OK && decoded==1);
    assert(!save_device_write(SAVE_FILE_SLOTS));
    return 0;
}
''')

    def test_mount_uses_reserved_workspaces_and_never_formats(self):
        path = ROOT / 'src/backup_low.c'
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
typedef unsigned jo_backup_device;
static unsigned char ram[1024*1024];
''' + '#include "' + (ROOT / 'src/ram_low.h').as_posix() + '"\n' + r'''
#undef RAM_LOW
#define RAM_LOW(n) ((void*)(ram+(n)))
static bool __jo_backup_initialized;
static unsigned *__jo_backup_lib_space,*__jo_backup_work_space;
static int __jo_backup_cntb[3],init_calls,stat_calls,status;
static struct { int status,sttb; bool is_mounted; } __jo_backup_devices[3];
static void jo_core_disable_reset(void) {}
static void jo_core_enable_reset(void) {}
static void init_driver(void *lib,void *work,int *config) {
    ++init_calls;
    assert(lib==RAM_LOW(RAM_LOW_BACKUP_LIB_OFFSET));
    assert(work==RAM_LOW(RAM_LOW_BACKUP_WORK_OFFSET));
    assert(RAM_LOW_BACKUP_WORK_BYTES==8312);
    assert(((unsigned char*)work)[8311]==0);
    ((unsigned char*)work)[8311]=42;
}
static int stat_driver(unsigned device,unsigned bytes,int *out) { ++stat_calls; return status; }
#define JO_BACKUP_DRIVER_INIT init_driver
#define JO_BACKUP_DRIVER_STAT stat_driver
''' + graphics.function(path, 'bool jo_backup_mount(')
            + graphics.function(path, 'bool jo_backup_unmount(') + r'''
int main(void) {
    ram[RAM_LOW_BACKUP_WORK_OFFSET+8312]=91;
    status=2; assert(!jo_backup_mount(0)); assert(init_calls==1 && stat_calls==1);
    assert(ram[RAM_LOW_BACKUP_WORK_OFFSET+8312]==91);
    assert(!jo_backup_mount(3) && stat_calls==1);
    status=0; assert(jo_backup_mount(0)); assert(init_calls==1);
    assert(jo_backup_unmount(0)); assert(!jo_backup_unmount(0));
    assert(jo_backup_mount(0) && init_calls==1);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
