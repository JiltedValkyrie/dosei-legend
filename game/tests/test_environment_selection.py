"""Authored sky theme metadata is independent of clock/room layer fallback."""
import ctypes as C
import os
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from environment_selection_source import sky_settings, retained_weather_source

OOT = Path(os.environ.get('OOT_DECOMP', 'D:/Workspace-Claude/game-decomps/n64/oot'))
GCC = shutil.which('gcc') or ('C:/msys64/mingw64/bin/gcc.exe' if Path('C:/msys64/mingw64/bin/gcc.exe').exists() else None)


class SkySettings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        (self.folder / 'include').mkdir()
        (self.folder / 'include/skybox.h').write_text('typedef enum SkyboxId { SKYBOX_NONE, SKYBOX_NORMAL_SKY, SKYBOX_OVERCAST_SUNSET=3, SKYBOX_CUTSCENE_MAP=5 } SkyboxId;')
        (self.folder / 'include/environment.h').write_text('typedef enum LightMode { LIGHT_MODE_TIME, LIGHT_MODE_SETTINGS } LightMode;')

    def tearDown(self):
        self.temp.cleanup()

    def parse(self, text):
        path = self.folder / 'header.inc.c'
        path.write_text(text)
        return sky_settings(path, self.folder)

    def test_settings_use_source_enums_and_keep_light_mode(self):
        self.assertEqual(self.parse('SCENE_CMD_SKYBOX_SETTINGS(SKYBOX_NORMAL_SKY, 1, LIGHT_MODE_SETTINGS),'),
                         (1, 1, 1, 1))
        self.assertEqual(self.parse('SCENE_CMD_SKYBOX_SETTINGS(SKYBOX_CUTSCENE_MAP, 0, LIGHT_MODE_TIME),'),
                         (5, 0, 0, 1))

    def test_absent_command_does_not_reset_and_disabled_false_is_present(self):
        self.assertEqual(self.parse('SCENE_CMD_END(),'), (0, 0, 0, 0))
        self.assertEqual(sky_settings(None, self.folder), (0, 0, 0, 0))
        self.assertEqual(self.parse('SCENE_CMD_SKYBOX_DISABLES(false /* enabled */, true /* no sun */),'),
                         (0, 0, 0, 10))
        self.assertEqual(self.parse('SCENE_CMD_SKYBOX_DISABLES(true, false),'), (0, 0, 0, 6))

    def test_comments_and_duplicate_commands(self):
        self.assertEqual(self.parse('/* SCENE_CMD_SKYBOX_SETTINGS(9,3,0) */\n// SCENE_CMD_SKYBOX_DISABLES(true,true)\n'),
                         (0, 0, 0, 0))
        with self.assertRaises(ValueError):
            self.parse('SCENE_CMD_SKYBOX_SETTINGS(1,0,0), SCENE_CMD_SKYBOX_SETTINGS(1,1,0),')
        with self.assertRaises(ValueError):
            self.parse('SCENE_CMD_SKYBOX_DISABLES(2,0)')

    @unittest.skipUnless((OOT / 'include/skybox.h').exists(), 'source decomp required')
    def test_real_field_clear_and_authored_cutscene_overcast(self):
        root = OOT / 'extracted/ntsc-1.2/assets/scenes/overworld/spot00'
        self.assertEqual(sky_settings(root / 'spot00_scene.inc.c', OOT), (1, 0, 0, 1))
        self.assertEqual(sky_settings(root / 'spot00_scene_02000068_AltHeaders_02011AD0_Cmds.inc.c', OOT),
                         (1, 1, 1, 1))
        self.assertEqual(sky_settings(root / 'spot00_room_0.inc.c', OOT), (0, 0, 0, 2))


@unittest.skipUnless(GCC and (OOT / 'src/code/z_kankyo.c').exists(), 'host GCC and source required')
class RetainedWeather(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder = Path(cls.temp.name)
        source = r'''
#include <stdbool.h>
typedef struct {int skyboxConfig,changeSkyboxNextConfig,lightConfig,changeLightNextConfig;int precipitation[5];} EnvironmentContext;
typedef struct {EnvironmentContext envCtx;int skyboxId;} PlayState;
static struct {int retainWeatherMode,sceneLayer;} gSaveContext;
static int gWeatherMode;
enum {WEATHER_MODE_CLEAR,WEATHER_MODE_CLOUDY_CONFIG3,WEATHER_MODE_CLOUDY_CONFIG2,WEATHER_MODE_SNOW,WEATHER_MODE_RAIN,WEATHER_MODE_HEAVY_RAIN};
enum {PRECIP_RAIN_MAX,PRECIP_RAIN_CUR,PRECIP_SNOW_MAX,PRECIP_SNOW_CUR,PRECIP_SOS_MAX};
#define SKYBOX_NORMAL_SKY 1
#define IS_CUTSCENE_LAYER (gSaveContext.sceneLayer>=4)
'''
        source += retained_weather_source(OOT)
        source += r'''
void run(int retained,int weather,int layer,int id,int config,int* out) {
    PlayState play={0};
    gSaveContext.retainWeatherMode=retained;gSaveContext.sceneLayer=layer;gWeatherMode=weather;
    play.skyboxId=id;play.envCtx.skyboxConfig=play.envCtx.changeSkyboxNextConfig=config;
    OotCore_EnvironmentSkyInit(&play);
    out[0]=gWeatherMode;out[1]=play.envCtx.skyboxConfig;out[2]=play.envCtx.changeSkyboxNextConfig;
    out[3]=play.envCtx.lightConfig;out[4]=play.envCtx.precipitation[PRECIP_RAIN_CUR];
    out[5]=play.envCtx.precipitation[PRECIP_SNOW_CUR];out[6]=gSaveContext.retainWeatherMode;
}
'''
        (folder / 'test.c').write_text(source)
        library = folder / ('test.dll' if os.name == 'nt' else 'test.so')
        env = dict(os.environ, PATH=str(Path(GCC).parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([GCC, '-shared', '-O2', '-Wall', '-Werror', str(folder / 'test.c'), '-o', str(library)], check=True, env=env)
        cls.lib = C.CDLL(str(library))
        cls.lib.run.argtypes = [C.c_int] * 5 + [C.POINTER(C.c_int)]

    @classmethod
    def tearDownClass(cls):
        cls.lib = None
        cls.temp.cleanup()

    def run_weather(self, retained, weather, layer=0, identity=1, config=2):
        out = (C.c_int * 7)()
        self.lib.run(retained, weather, layer, identity, config, out)
        return list(out)

    def test_authored_config_stays_when_weather_not_retained(self):
        self.assertEqual(self.run_weather(0, 5), [0, 2, 2, 0, 0, 0, 0])
        self.assertEqual(self.run_weather(1, 0), [0, 2, 2, 0, 0, 0, 0])

    def test_all_source_retained_weather_modes(self):
        for weather, light in ((1, 3), (2, 2), (3, 2), (4, 2), (5, 4)):
            rain = {4:20, 5:30}.get(weather, 0)
            self.assertEqual(self.run_weather(1, weather),
                             [weather, 1, 1, light, rain, 64 if weather == 3 else 0, 0])

    def test_cutscene_layer_excludes_override_and_static_sky_excludes_rain(self):
        self.assertEqual(self.run_weather(1, 5, layer=4), [5, 2, 2, 0, 0, 0, 0])
        self.assertEqual(self.run_weather(1, 4, identity=3), [4, 1, 1, 2, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
