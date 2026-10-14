"""Creation cue/action preservation and explicit sprite/variant boundaries."""
import os
from pathlib import Path
import sys
import unittest

GAME=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME/'tools'))
import child_legend_sources as legend
from child_route_effects import functions
OOT=Path(os.environ.get('DOSEI_OOT','D:/Workspace-Claude/game-decomps/n64/oot'))


@unittest.skipUnless((OOT/legend.SOURCES[0]).exists(),'local decomp required')
class LegendSource(unittest.TestCase):
    def test_original_cues_children_and_timers(self):
        before=(OOT/legend.SOURCES[0]).read_text(encoding='utf-8')
        after=legend.adapt(legend.SOURCES[0],before)
        original,adapted=functions(before),functions(after)
        for name in ('DemoEffect_UpdateGodLgtDin','DemoEffect_UpdateGodLgtNayru',
                     'DemoEffect_UpdateGodLgtFarore','DemoEffect_UpdateTriforceSpot',
                     'DemoEffect_UpdateCreationFireball','DemoEffect_InitCreationFireball',
                     'DemoEffect_UpdateBlueOrbGrow','DemoEffect_UpdateBlueOrbShrink',
                     'DemoEffect_UpdateLightRingTriforce','DemoEffect_UpdateLightRingExpanding',
                     'DemoEffect_UpdateLightRingShrinking','DemoEffect_UpdateLgtShower',
                     'DemoEffect_SetPosRotFromCue','DemoEffect_SetStartPosFromCue'):
            self.assertEqual(original[name],adapted[name],name)
        self.assertNotIn('gGoldenGoddessBodyDL',adapted['DemoEffect_DrawGodLgt'])
        self.assertNotIn('gGoldenGoddessAuraDL',adapted['DemoEffect_DrawGodLgt'])
        self.assertNotIn('SkelCurve_', '\n'.join(adapted.values()))
        self.assertIn('NA_SE_EV_GOD_FLYING',adapted['DemoEffect_SaturnGodPresentation'])
        self.assertIn('this->godLgt.rotation++',adapted['DemoEffect_SaturnGodPresentation'])
        self.assertNotIn('vertices[',adapted['DemoEffect_DrawTriforceSpot'])

    def test_all_source_rain_particles_survive(self):
        before=(OOT/legend.SOURCES[1]).read_text(encoding='utf-8')
        after=legend.adapt(legend.SOURCES[1],before)
        original,adapted=functions(before),functions(after)
        self.assertEqual(original['DemoKankyo_DrawRain'].replace('j < 5','j < 1'),adapted['DemoKankyo_DrawRain'])
        for name in ('func_80989B54','DemoKankyo_UpdateRock','DemoKankyo_UpdateClouds'):
            self.assertEqual(original[name],adapted[name])
        self.assertIn('case DEMOKANKYO_BLUE_RAIN_2:',adapted['DemoKankyo_SetupType'])
        self.assertNotIn('DemoKankyo_DrawWarpSparkles',adapted)


if __name__=='__main__': unittest.main()
