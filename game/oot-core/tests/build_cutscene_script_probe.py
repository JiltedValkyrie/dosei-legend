"""Use the imported dispatcher/commands and complete source scene scripts.

Only command packing changes for the little-endian host ABI. Saturn keeps the
original big-endian macros. Destination loading is observed, not simulated.
"""
from pathlib import Path
import re
import sys

GAME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GAME / 'tools'))
from core_cutscene_sources import scene_scripts


def function(text, name):
    start = re.search(r'^(?:void|s32) ' + name + r'\(', text, re.M).start()
    brace = text.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


oot, out = map(Path, sys.argv[1:])
types = (GAME / 'build/oot-core/decomp/include/ultra64/ultratypes.h').read_text()
types = re.sub(r'typedef signed long\s+s32;', 'typedef signed int s32;', types)
types = re.sub(r'typedef unsigned long\s+u32;', 'typedef unsigned int u32;', types)
out.with_name('ultratypes32.h').write_text(types)
source = (GAME / 'build/oot-core/decomp/src/code/z_demo.cpp').read_text()
names = ['CutsceneCmd_Misc', 'CutsceneCmd_SetLightSetting', 'CutsceneCmd_StartSequence',
         'CutsceneCmd_StopSequence', 'CutsceneCmd_FadeOutSequence', 'CutsceneCmd_RumbleController',
         'CutsceneCmd_SetTime', 'CutsceneCmd_Transition', 'CutsceneCmd_UpdateCamEyeSpline',
         'CutsceneCmd_UpdateCamAtSpline', 'CutsceneCmd_SetCamEye', 'CutsceneCmd_SetCamAt',
         'CutsceneCmd_Text', 'Cutscene_ProcessScript']
body = ''.join(function(source, name) for name in names)
body += '''
#include "cutscene_commands.h"
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#undef CMD_BBBB
#undef CMD_BBH
#undef CMD_HBB
#undef CMD_HH
#define CMD_BBBB(a,b,c,d) (_SHIFTL(a,0,8)|_SHIFTL(b,8,8)|_SHIFTL(c,16,8)|_SHIFTL(d,24,8))
#define CMD_BBH(a,b,c) (_SHIFTL(a,0,8)|_SHIFTL(b,8,8)|_SHIFTL(c,16,16))
#define CMD_HBB(a,b,c) (_SHIFTL(a,0,16)|_SHIFTL(b,16,8)|_SHIFTL(c,24,8))
#define CMD_HH(a,b) (_SHIFTL(a,0,16)|_SHIFTL(b,16,16))
#endif
'''
commands = (GAME / 'build/oot-core/decomp/include/cutscene_commands.h').read_text()
# These source macros pack a 16-bit value, but runtime consumes its low
# byte as the second byte of the word. Retain that field layout on LE.
for name in ['CS_START_SEQ', 'CS_STOP_SEQ', 'CS_LIGHT_SETTING']:
    macro = re.search(r'#define ' + name + r'\(.*?(?=\n\n)', commands, re.S).group(0)
    macro = re.sub(r'CMD_HH\((\([^\n]+?\)), startFrame\)',
                   r'CMD_BBH(0, \1, startFrame)', macro)
    body += '\n#undef ' + name + '\n' + macro + '\n'
asset_root = oot / 'extracted/ntsc-1.2'
for scene in ['overworld/spot18', 'overworld/spot20', 'overworld/spot16', 'dungeons/ddan',
              'indoors/nakaniwa', 'misc/hiral_demo']:
    path = asset_root / 'assets/scenes' / scene / (Path(scene).name + '_scene.c')
    definitions, _ = scene_scripts(path, asset_root)
    body += definitions
out.write_text(body)
