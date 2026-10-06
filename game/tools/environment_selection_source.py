"""Read original scene/room skybox commands; preserve absent-command semantics.

Fields fit four bytes on OotSceneLayer: id, config, light mode, flags. They
describe authored defaults, not the dynamic weather state machine. Importer
must retain its existing alternate-header presence/fallback ordering.
"""
from functools import lru_cache
from pathlib import Path
import re

SETTINGS_PRESENT = 1
DISABLES_PRESENT = 2
SKY_DISABLED = 4
SUN_MOON_DISABLED = 8


def _without_comments(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def _enum(path, name):
    text = _without_comments(Path(path).read_text(encoding='utf-8'))
    match = re.search(r'typedef\s+enum\s+' + name + r'\s*\{(.*?)\}', text, re.S)
    if not match:
        raise ValueError('Missing source enum ' + name)
    values, current = {}, -1
    for row in match.group(1).split(','):
        row = row.strip()
        if not row:
            continue
        part = re.fullmatch(r'(\w+)(?:\s*=\s*(0x[0-9A-Fa-f]+|\d+))?', row)
        if not part:
            raise ValueError('Unsupported source enum expression: ' + row)
        current = int(part[2], 0) if part[2] else current + 1
        values[part[1]] = current
    return values


@lru_cache(maxsize=8)
def _constants(oot):
    oot = Path(oot)
    return dict(_enum(oot / 'include/skybox.h', 'SkyboxId'),
                **_enum(oot / 'include/environment.h', 'LightMode'), false=0, true=1)


def sky_settings(path, oot):
    """(skybox id, config, light mode, flags) from one resolved .inc.c header.

    No command means flags=0, so a header/room must not reset current scene
    settings. A NULL alternate header is handled by the caller's normal source
    fallback selection, never guessed here.
    """
    if path is None:
        return (0, 0, 0, 0)
    text = _without_comments(Path(path).read_text(encoding='utf-8'))
    values = _constants(str(Path(oot)))

    def command(name, expected):
        commands = re.findall(r'\b' + name + r'\(([^)]*)\)', text)
        if not commands:
            return None
        if len(commands) != 1:
            raise ValueError(f'{path}: multiple {name} commands')
        args = [arg.strip() for arg in commands[0].split(',')]
        if len(args) != expected:
            raise ValueError(f'{path}: invalid {name} arguments')
        return [values[arg] if arg in values else int(arg, 0) for arg in args]

    settings = command('SCENE_CMD_SKYBOX_SETTINGS', 3)
    disables = command('SCENE_CMD_SKYBOX_DISABLES', 2)
    identity, config, light, flags = 0, 0, 0, 0
    if settings is not None:
        identity, config, light = settings
        if not 0 <= identity <= 255 or not 0 <= config <= 3 or light not in (0, 1):
            raise ValueError(f'{path}: sky settings exceed known source range')
        flags |= SETTINGS_PRESENT
    if disables is not None:
        if any(value not in (0, 1) for value in disables):
            raise ValueError(f'{path}: sky disables must be booleans')
        flags |= DISABLES_PRESENT | (SKY_DISABLED if disables[0] else 0) | (SUN_MOON_DISABLED if disables[1] else 0)
    return identity, config, light, flags


def retained_weather_source(oot):
    """Import the integer-only retained-weather branch of Environment_Init.

    Call once after the selected scene header's sky settings, before room
    commands/actor initialization. This is initialization, not a replacement
    for En_Weather_Tag, Environment_UpdateStorm or sky transition updates.
    gWeatherMode must keep its original session-global lifetime.
    """
    text = (Path(oot) / 'src/code/z_kankyo.c').read_text(encoding='utf-8')
    init = text.index('void Environment_Init(')
    start = text.index('    if (gSaveContext.retainWeatherMode) {', init)
    end = text.index('\n    gInterruptSongOfStorms = false;', start)
    body = text[start:end]
    if body.count('envCtx->skyboxConfig = 1;') != 3 or 'gWeatherMode = WEATHER_MODE_CLEAR;' not in body:
        raise ValueError('Environment_Init retained-weather source changed')
    tail = text[end:text.index('\n#if DEBUG_FEATURES', end)]
    if '    gSaveContext.retainWeatherMode = false;' not in tail:
        raise ValueError('Environment_Init retained-weather reset changed')
    return ('/* Generated integer-only Environment_Init retained-weather branch. */\n'
            'static void OotCore_EnvironmentSkyInit(PlayState* play) {\n'
            '    EnvironmentContext* envCtx = &play->envCtx;\n' + body + '\n'
            '    gSaveContext.retainWeatherMode = false;\n}\n')
