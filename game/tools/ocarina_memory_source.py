"""Original Skull Kid memory-game generator, with bounded Saturn storage."""
import re
from owl_sources import function


def source(oot):
    text=(oot/'src/audio/game/general.c').read_text(encoding='utf-8')
    pitch=re.search(r'u8 sButtonToPitchMap\[5\] = \{.*?\n\};',text,re.S).group()
    lengths=re.search(r'u8 sOcaMemoryGameNumNotes\[\] = \{[^}]+\};',text).group()
    body='''/* Source audio/game/general.c. Source maximum is eight notes plus
 * two terminators. Gameplay RNG replaces the absent N64 audio-thread RNG. */
static OcarinaNote sMemorySong[10];
static u8 sOcaMemoryGameAppendPos, sOcaMemoryGameEndPos;
'''
    body+='static const '+pitch+'\nstatic const '+lengths+'\n'
    init=function(text,'AudioOcarina_MemoryGameInit')
    init=init.replace('    sOcaMemoryGameAppendPos = 0;',
                      '    sOcaMemoryGameAppendPos = 0;\n    gOcarinaSongButtons[OCARINA_SONG_MEMORY_GAME].numButtons = 0;')
    next_note=function(text,'AudioOcarina_MemoryGameNextNote')
    next_note=next_note.replace('sOcarinaSongNotes[OCARINA_SONG_MEMORY_GAME]', 'sMemorySong')
    next_note=next_note.replace('AudioThread_NextRandom()', 'Rand_Next()')
    # The retail expression reads note -1 on the first append; no prior note
    # exists in the compact buffer. Repeat rejection applies from note two.
    next_note=next_note.replace('if (sMemorySong[sOcaMemoryGameAppendPos - 1].pitch',
                                'if (sOcaMemoryGameAppendPos && sMemorySong[sOcaMemoryGameAppendPos - 1].pitch')
    next_note=next_note.replace('    if (1) {}', '''    for (u8 button = 0; button < 5; ++button) {
        if (sButtonToPitchMap[button] == randomPitch)
            gOcarinaSongButtons[OCARINA_SONG_MEMORY_GAME].buttonsIndex[sOcaMemoryGameAppendPos - 1] = button;
    }
    gOcarinaSongButtons[OCARINA_SONG_MEMORY_GAME].numButtons = sOcaMemoryGameAppendPos;''')
    return body+init+next_note
