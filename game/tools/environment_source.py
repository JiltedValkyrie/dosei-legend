"""Import the NTSC environment clock statements, not a second clock model.

Rendering, audio and sky DMA remain Saturn backend responsibilities. Fail on
changed source anchors rather than silently importing another version's rules.
"""
import pathlib
import re
import struct


def _integer_clocks(body):
    body = re.sub(r'CLOCK_TIME\((\d+),\s*(\d+)\)',
                  lambda m: str(((int(m[1])*60+int(m[2]))*65536+720)//1440), body)
    # These environment.h macros contain CLOCK_TIME too. Do not let the
    # fixed-point imported header turn constant clock values into Fx math.
    body = re.sub(r'\bNEXT_TIME_DAY\b', '32769', body)
    return re.sub(r'\bNEXT_TIME_NIGHT\b', '0', body)


def _block(source, anchor):
    start = source.index(anchor)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def room_behavior(path, oot):
    """Room type and warp-song restriction, from the room's own command."""
    if path is None:
        return (0, 0)
    from environment_selection_source import _enum, _without_comments
    text = _without_comments(pathlib.Path(path).read_text(encoding='utf-8'))
    rows = re.findall(r'SCENE_CMD_ROOM_BEHAVIOR\(([^)]+)\)', text)
    if not rows:
        return (0, 0)
    if len(rows) != 1:
        raise ValueError(f'{path}: multiple room behavior commands')
    args = [v.strip() for v in rows[0].split(',')]
    values = _enum(pathlib.Path(oot)/'include/room.h', 'RoomType')
    kind = values[args[0]] if args[0] in values else int(args[0], 0)
    warp = {'false': 0, 'true': 1}.get(args[3])
    if warp is None:
        warp = int(args[3], 0)
    if not 0 <= kind <= 255 or warp not in (0, 1):
        raise ValueError(f'{path}: invalid room behavior')
    return kind, 1 | (warp << 1)


def room_time(path):
    """Bake Scene_CommandTimeSettings' float conversion offline, byte exact."""
    text = pathlib.Path(path).read_text(encoding='utf-8')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    commands = re.findall(r'SCENE_CMD_TIME_SETTINGS\(([^)]+)\)', text)
    if not commands:
        return (0, 0, 0)
    if len(commands) != 1:
        raise ValueError(f'{path}: multiple time settings')
    hour, minute, speed = [int(v.strip(), 0) for v in commands[0].split(',')]
    if any(not 0 <= v <= 255 for v in (hour, minute, speed)):
        raise ValueError(f'{path}: invalid time command')
    def f32(v):
        return struct.unpack('f', struct.pack('f', v))[0]
    set_time = hour != 255 and minute != 255
    time = int(f32(f32(f32(hour + f32(minute / 60)) * 60) /
                   f32(1440 / 65536))) & 65535 if set_time else 0
    return time, 0 if speed == 255 else speed, 1 | (2 if set_time else 0)


def clock_source(oot):
    source = (pathlib.Path(oot) / 'src/code/z_kankyo.c').read_text(encoding='utf-8')
    start = source.index('        if ((pauseCtx->state == PAUSE_STATE_OFF) && (gameOverCtx->state == GAMEOVER_INACTIVE))')
    end = source.index('\n#if DEBUG_FEATURES', start)
    body = source[start:end]
    body = re.sub(r'^\s*PRINTF\([^\n]*\);\s*$', '', body, flags=re.M)
    if 'gSaveContext.save.dayTime += gTimeSpeed * 2;' not in body:
        raise ValueError('Environment_Update clock source changed')
    # CLOCK_TIME uses floating constants upstream. All arguments here are
    # literals; resolve them offline with the source rounding rule.
    def clock(match):
        minutes = int(match[1]) * 60 + int(match[2])
        return str((minutes * 65536 + 720) // 1440)
    body = re.sub(r'CLOCK_TIME\((\d+),\s*(\d+)\)', clock, body)
    return ('/* Generated from z_kankyo.c Environment_Update; NTSC source guards retained. */\n'
            'static void OotCore_EnvironmentClock(PlayState* play) {\n'
            '    PauseContext* pauseCtx = &play->pauseCtx;\n'
            '    GameOverContext* gameOverCtx = &play->gameOverCtx;\n'
            '    MessageContext* msgCtx = &play->msgCtx;\n'
            '    EnvironmentContext* envCtx = &play->envCtx;\n'
            '    u16 time;\n'
            '    if (pauseCtx->state != PAUSE_STATE_OFF) return;\n' + body + '\n}\n')


def clock_events_source(oot):
    """Unpaused day effects run before and independently of time advancement."""
    source = (pathlib.Path(oot)/'src/code/z_kankyo.c').read_text(encoding='utf-8')
    body = _block(source, '        if (((void)0, gSaveContext.nextDayTime) >= 0xFF00')
    body = re.sub(r'^\s*PRINTF\([^\n]*\);\s*$', '', body, flags=re.M)
    return ('/* Source Environment_Update event ordering; not dialogue gated. */\n'
            'static void OotCore_EnvironmentEvents(PlayState* play) {\n'
            '    if (play->pauseCtx.state != PAUSE_STATE_OFF) return;\n'
            '    OotCore_DaySequenceUpdate(play);\n' + body + '\n}\n')


def player_clock_gate_source(oot):
    source = (pathlib.Path(oot)/'src/code/z_player_lib.c').read_text(encoding='utf-8')
    parts = [_block(source, signature) for signature in (
        's32 Player_ActionToMagicSpell(', 'int Player_InBlockingCsMode(', 'int Player_InCsMode(')]
    body = '\n'.join(parts)
    for name in ('Player_ActionToMagicSpell', 'Player_InBlockingCsMode', 'Player_InCsMode'):
        body = body.replace(name, 'OotCore_Clock' + name)
    return '/* Source integer-only dawn textbox cutscene predicate. */\n' + re.sub(r'\bthis\b', 'player', body) + '\n'


def room_clock_source(oot):
    source = (pathlib.Path(oot) / 'src/code/z_scene.c').read_text(encoding='utf-8')
    start = source.index('    if (((play->envCtx.sceneTimeSpeed == 0)')
    end = source.index('\n}\n', start)
    body = re.sub(r'CLOCK_TIME\((\d+),\s*(\d+)\)',
                  lambda m: str(((int(m[1])*60+int(m[2]))*65536+720)//1440),
                  source[start:end])
    return ('/* Scene_CommandTimeSettings: command values preconverted offline. */\n'
            'static void OotCore_EnvironmentRoom(PlayState* play, const OotSceneLayer* layer) {\n'
            '    if (layer->behavior_flags & 1) {\n'
            '        play->roomCtx.curRoom.type = layer->room_type;\n'
            '        play->msgCtx.disableWarpSongs = (layer->behavior_flags >> 1) & 1;\n'
            '    }\n'
            '    if (!(layer->time_flags & 1)) return;\n'
            '    if (layer->time_flags & 2)\n'
            '        gSaveContext.skyboxTime = gSaveContext.save.dayTime = layer->time;\n'
            '    play->envCtx.sceneTimeSpeed = layer->time_speed;\n'
            '    if (gSaveContext.sunsSongState == SUNSSONG_INACTIVE)\n'
            '        gTimeSpeed = play->envCtx.sceneTimeSpeed;\n' + body + '\n}\n')


def sun_song_source(oot):
    """Clock state machine from Interface_Update, with an explicit audio adapter.

    The caller triggers the source effect-end guard when the Saturn song UI
    completes. The unimported Oceff_Spot visual effect timing is not reproduced.
    """
    oot = pathlib.Path(oot)
    source = (oot/'src/code/z_parameter.c').read_text(encoding='utf-8')
    body = _block(source[source.index('void Interface_Update('):],
                  '    if (gSaveContext.sunsSongState != SUNSSONG_INACTIVE)')
    body = body.replace('func_800F6964(30);', 'OotCore_SunSongAudioFade(30);')
    effect = (oot/'src/overlays/actors/ovl_Oceff_Spot/z_oceff_spot.c').read_text(encoding='utf-8')
    start = effect.index('        if (gTimeSpeed != 400')
    end = effect.index('\n    }\n}', start)
    begin = re.sub(r'^\s*PRINTF[^\n]*\n', '', effect[start:end], flags=re.M)
    return ('/* Source OceffSpot_End guard; Saturn completion timing adapter. */\n'
            'void OotCore_SunSongStart(PlayState* play) {\n' + begin + '\n}\n'
            '/* Source Interface_Update Sun\'s Song state machine. */\n'
            'static void OotCore_SunSongUpdate(PlayState* play) {\n'
            '    static u8 D_80125B60 = false;\n'
            '    static s16 sPrevTimeSpeed = 0;\n'
            '    MessageContext* msgCtx = &play->msgCtx;\n'
            '    InterfaceContext* interfaceCtx = &play->interfaceCtx;\n' +
            _integer_clocks(body) + '\n}\n')


def destination_layer_source(oot):
    """Source Play_Init layer choice, parameterized by destination base scene.

    It deliberately does not mutate the currently loaded scene layer. Pending
    Sun's Song time is used before choosing the destination entrance variant.
    Conditional entrance cutscenes remain the transition backend's work.
    """
    source = (pathlib.Path(oot)/'src/code/z_play.c').read_text(encoding='utf-8')
    start = source.index('    if (gSaveContext.gameMode != GAMEMODE_NORMAL || gSaveContext.save.cutsceneIndex >= CS_INDEX_0)')
    end = source.index('\n    Play_SpawnScene(', start)
    body = source[start:end]
    body = body.replace('        gSaveContext.nayrusLoveTimer = 0;\n        Magic_Reset(this);\n', '')
    body = re.sub(r'^\s*baseSceneLayer = gSaveContext.sceneLayer;\s*$', '', body, flags=re.M)
    body = body.replace('gEntranceTable[((void)0, gSaveContext.save.entranceIndex)].sceneId', 'destination')
    body = body.replace('gSaveContext.sceneLayer', 'layer').replace('IS_CUTSCENE_LAYER', '(layer >= SCENE_LAYER_CUTSCENE_FIRST)')
    body = body.replace('IS_DAY', 'day')
    body = body.replace('gSaveContext.save.cutsceneIndex', 'cutsceneIndex')
    return ('/* Source Play_Init entrance-layer choice; current layer stays fixed. */\n'
            'static unsigned int OotCore_DestinationLayer(unsigned int destination) {\n'
            '    u16 cutsceneIndex = gSaveContext.nextCutsceneIndex != NEXT_CS_INDEX_NONE ?\n'
            '        gSaveContext.nextCutsceneIndex : gSaveContext.save.cutsceneIndex;\n'
            '    if (cutsceneIndex == CS_INDEX_D) cutsceneIndex = CS_INDEX_NONE;\n'
            '    u16 time = gSaveContext.nextDayTime != NEXT_TIME_NONE ?\n'
            '        gSaveContext.nextDayTime : gSaveContext.save.dayTime;\n'
            '    s32 day = !(time > 49152 || time < 17749);\n'
            '    s32 layer;\n' + body + '\n    return layer;\n}\n')


def transition_clock_source(oot):
    """Source Play_Init pending-time consumption and day-change notification."""
    source = (pathlib.Path(oot)/'src/code/z_play.c').read_text(encoding='utf-8')
    anchor = '    if (gSaveContext.nextDayTime != NEXT_TIME_NONE)'
    start = source.index('    if (gSaveContext.nextCutsceneIndex != NEXT_CS_INDEX_NONE)')
    end = source.index('\n    Cutscene_HandleConditionalTriggers(this);', start)
    begin = _integer_clocks(source[start:end])
    finish = _block(source[source.index('    Interface_Init(this);', end):], anchor)
    finish = finish.replace('Inventory_ReplaceItem(this,', 'OotCore_ReplaceDayItem(play,')
    finish = finish.replace('Message_StartTextbox(this,', 'Message_StartTextbox(play,')
    return ('/* Source Play_Init time assignment precedes layer selection. */\n'
            'static void OotCore_TransitionTimeBegin(void) {\n' + begin + '\n}\n'
            'static void OotCore_TransitionTimeFinish(PlayState* play) {\n' + _integer_clocks(finish) + '\n}\n')


def sky_schedule(oot):
    """All original clear/overcast/cutscene schedules, including +1 boundaries."""
    source = (pathlib.Path(oot) / 'src/code/z_kankyo.c').read_text(encoding='utf-8')
    start = source.index('TimeBasedSkyboxEntry gTimeBasedSkyboxConfigs[][9] = {')
    end = source.index('\n};', start)
    entries = re.findall(
        r'\{ CLOCK_TIME\((\d+), (\d+)\)(\s*[+-]\s*\d+)?, '
        r'CLOCK_TIME\((\d+), (\d+)\)(\s*[+-]\s*\d+)?, '
        r'(true|false), (\d+), (\d+) \}', source[start:end])
    if len(entries) != 36:
        raise ValueError('Expected four original nine-entry sky schedules')
    def value(hour, minute, offset):
        return (((int(hour) * 60 + int(minute)) * 65536 + 720) // 1440
                + (int(offset.replace(' ', '')) if offset else 0))
    rows = [(value(a,b,c),value(d,e,f),int(g=='true'),int(h),int(i))
            for a,b,c,d,e,f,g,h,i in entries]
    return [rows[i:i+9] for i in range(0,36,9)]
