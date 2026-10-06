"""Import the source day-sequence state machine without taking audio ownership.

The C music backend still owns BGM and ambience. Their source call statements
are removed explicitly; state branches, dawn inventory changes and animal SFX
remain. This is not a claim that source BGM/ambience sequencing is implemented.
"""
from functools import lru_cache
from pathlib import Path
import re

from environment_selection_source import _enum, _without_comments


def _masked(text):
    """Keep offsets while hiding comments, strings and character literals."""
    pattern = r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    return re.sub(pattern, lambda m: re.sub(r'[^\n]', ' ', m[0]), text, flags=re.S)


def _function(text, name):
    masked = _masked(text)
    match = re.search(r'\b(?:void|s32)\s+' + name + r'\([^;{}]*\)\s*\{', masked)
    if match is None:
        raise ValueError('Missing source function ' + name)
    opening = masked.index('{', match.start())
    depth = 1
    end = opening + 1
    while depth and end < len(masked):
        depth += (masked[end] == '{') - (masked[end] == '}')
        end += 1
    if depth:
        raise ValueError('Unclosed source function ' + name)
    return text[match.start():end]


def _remove_calls(text, expected, comment):
    """Remove complete statements, including nested/multiline arguments."""
    masked = _masked(text)
    edits = []
    for name, count in expected.items():
        calls = list(re.finditer(r'\b' + re.escape(name) + r'\s*\(', masked))
        if len(calls) != count:
            raise ValueError(f'{name}: expected {count} source calls, found {len(calls)}')
        for call in calls:
            pos = call.end()
            depth = 1
            while depth and pos < len(masked):
                depth += (masked[pos] == '(') - (masked[pos] == ')')
                pos += 1
            while pos < len(masked) and masked[pos].isspace():
                pos += 1
            if depth or pos == len(masked) or masked[pos] != ';':
                raise ValueError(name + ': expected a complete call statement')
            edits.append((call.start(), pos + 1, f'; /* {comment}: {name} */'))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


@lru_cache(maxsize=8)
def _sound_constants(oot):
    oot = Path(oot)
    text = _without_comments((oot / 'include/tables/sequence_table.h').read_text(encoding='utf-8'))
    names = re.findall(r'\bDEFINE_SEQUENCE(?:_PTR)?\s*\(\s*\w+\s*,\s*(\w+)\s*,', text)
    if not names or len(names) != len(set(names)):
        raise ValueError('Invalid source sequence table')
    values = {name: i for i, name in enumerate(names)}
    header = _without_comments((oot / 'include/sequence.h').read_text(encoding='utf-8'))
    values.update({name: int(number, 0) for name, number in
                   re.findall(r'\b(NA_BGM_\w+)\s*=\s*(0x[\dA-Fa-f]+|\d+)', header)})
    values.update(_enum(oot / 'include/sequence.h', 'NatureAmbienceId'))
    return values


def sound_settings(path, oot):
    """Return (sequence ID, nature ID, present) for one resolved scene header.

    Audio spec/heap selection stays with the C backend. Alternate-header
    presence/fallback is handled by the importer, just like sky metadata.
    """
    if path is None:
        return (0, 0, 0)
    text = _without_comments(Path(path).read_text(encoding='utf-8'))
    rows = re.findall(r'\bSCENE_CMD_SOUND_SETTINGS\(([^)]*)\)', text)
    if not rows:
        return (0, 0, 0)
    if len(rows) != 1:
        raise ValueError(f'{path}: multiple sound settings commands')
    values = _sound_constants(str(Path(oot)))
    args = [arg.strip() for arg in rows[0].split(',')]
    if len(args) != 3:
        raise ValueError(f'{path}: invalid sound settings arguments')
    spec, nature, seq = [values[arg] if arg in values else int(arg, 0) for arg in args]
    if not all(0 <= value <= 255 for value in (spec, nature, seq)):
        raise ValueError(f'{path}: sound settings exceed command byte range')
    return (seq, nature, 1)


def sequence_source(oot):
    """Generate source initialization and all nine day-sequence states.

    Caller invokes Init once per scene, then stores the source scene sequence
    IDs as Play_Init does. Update runs while pause is off, before dayTime
    advances, independently of the message/game-over clock-advance gates.
    """
    text = (Path(oot) / 'src/code/z_kankyo.c').read_text(encoding='utf-8')
    init = _function(text, 'Environment_PlaySceneSequence')
    update = _function(text, 'Environment_PlayTimeBasedSequence')
    forced = _function(text, 'Environment_IsForcedSequenceDisabled')
    if len(re.findall(r'case TIMESEQ_', update)) != 9:
        raise ValueError('Expected nine source time-sequence states')
    if ('gSaveContext.save.totalDays++;' not in update or
            'gSaveContext.save.bgsDayCount++;' not in update or
            update.count('Inventory_ReplaceItem(') != 2 or
            update.count('Player_InCsMode(') != 1):
        raise ValueError('Source dawn lifecycle changed')
    init = _remove_calls(init, {'PRINTF': 6}, 'Source debug output omitted')
    update = _remove_calls(update, {'PRINTF': 1}, 'Source debug output omitted')
    init = _remove_calls(init, {
        'Audio_PlayNatureAmbienceSequence': 3, 'Audio_PlaySceneSequence': 2,
        'Audio_SetEnvReverb': 1, 'SEQCMD_PLAY_SEQUENCE': 1,
    }, 'C music owns audio; source mapping pending')
    update = _remove_calls(update, {
        'Audio_PlayMorningSceneSequence': 1, 'Audio_PlayNatureAmbienceSequence': 1,
        'Audio_SetNatureAmbienceChannelIO': 6, 'SEQCMD_STOP_SEQUENCE': 1,
    }, 'C music owns audio; source mapping pending')
    update = update.replace('Inventory_ReplaceItem(', 'OotCore_ReplaceDayItem(')
    update = update.replace('Player_InCsMode(', 'OotCore_DayPlayerInCsMode(')
    result = forced + '\n\n' + init + '\n\n' + update
    result = result.replace('Environment_IsForcedSequenceDisabled', 'OotCore_DayForcedSequenceDisabled')
    result = result.replace('void Environment_PlaySceneSequence', 'static void OotCore_DaySequenceInit')
    result = result.replace('void Environment_PlayTimeBasedSequence', 'static void OotCore_DaySequenceUpdate')
    result = result.replace('s32 OotCore_DayForcedSequenceDisabled', 'static s32 OotCore_DayForcedSequenceDisabled')
    result = re.sub(r'CLOCK_TIME\((\d+),\s*(\d+)\)',
                    lambda m: str(((int(m[1]) * 60 + int(m[2])) * 65536 + 720) // 1440), result)
    if re.search(r'\b(?:Audio_\w+|SEQCMD_\w+|PRINTF|CLOCK_TIME)\s*\(', _masked(result)):
        raise ValueError('Unmapped audio/debug/clock expression in source day sequence')
    return ('/* Imported z_kankyo day state machine; BGM/ambience stay C-owned.\n'
            ' * Original audio timing is deferred, not silently implemented. */\n' + result + '\n')
