"""Source lift/put/throw event frames, including strengthless bush refusal."""
import ctypes as C
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
GCC=pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
class Lift(C.Structure):
    _fields_=[('phase',C.c_int),('timer',C.c_int),('attached',C.c_bool),
              ('throw_only',C.c_bool),('events',C.c_uint),
              ('speed',C.c_int32),('vertical',C.c_int32)]

@unittest.skipUnless(GCC.is_file(),'host compiler required')
class PlayerLift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll=pathlib.Path(cls.tmp.name)/'lift.dll'
        # link_anim.c needs SGL, so the upper-body overlay is stubbed here and
        # recorded, which is what these tests assert against.
        stub=pathlib.Path(cls.tmp.name)/'upper_stub.c'
        stub.write_text(
            'int upper_overlay_clip=-1;\n'
            'unsigned int upper_overlay_frame;\n'
            'unsigned int upper_overlay_fraction;\n'
            'unsigned int upper_overlay_sets;\n'
            'unsigned int upper_overlay_clears;\n'
            'void link_anim_upper_overlay(unsigned int c,unsigned int f,'
            'unsigned int fr){\n'
            '    upper_overlay_clip=(int)c;upper_overlay_frame=f;'
            'upper_overlay_fraction=fr;++upper_overlay_sets;}\n'
            'void link_anim_upper_clear(void){\n'
            '    upper_overlay_clip=-1;++upper_overlay_clears;}\n')
        env=dict(os.environ)
        env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
            '-I'+str(ROOT.parent/'shared/lib/camera'),
            '-I'+str(ROOT.parent/'shared/lib/collision'),
            str(ROOT/'src/player_lift.c'),str(ROOT/'src/link_anim_state.c'),
            str(ROOT/'build/generated/link_clips.c'),str(stub),'-o',str(dll)],
            check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        cls.lib.player_lift_begin.argtypes=[C.POINTER(Lift),C.c_bool,C.c_uint,C.c_bool]
        cls.lib.player_lift_update.argtypes=[C.POINTER(Lift),C.c_bool,C.c_int32]
        cls.lib.player_lift_cancel.argtypes=[C.POINTER(Lift)]

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.p=Lift()
        self.lib.link_anim_reset_state()
    def step(self,action=False,speed=0):
        self.lib.player_lift_update(C.byref(self.p),action,speed)
        return self.p.events
    def begin(self,bush=False,strength=0,throw_only=False):
        self.lib.player_lift_begin(C.byref(self.p),bush,strength,throw_only)
    def held(self,throw_only=False):
        self.begin(throw_only=throw_only)
        for frame in range(1,5):
            self.assertEqual(self.step(),1 if frame==4 else 0)
        for _ in range(100):
            if self.p.phase==5: break
            self.step()
        self.assertEqual(self.p.phase,5)
        self.assertTrue(self.p.attached)

    def test_bush_without_strength_never_attaches_or_drops(self):
        self.begin(bush=True)
        wait=0
        for _ in range(250):
            if self.p.phase==2: wait+=1
            self.assertEqual(self.step(),0)
            self.assertFalse(self.p.attached)
            if not self.p.phase: break
        self.assertEqual(wait,23)
        self.assertEqual(self.p.phase,0)
        self.assertEqual(self.lib.link_anim_state(),0)

    def test_attach_frame_four_and_put_frame_four(self):
        self.held()
        self.assertEqual(self.step(True),0)
        self.assertEqual(self.p.phase,7)
        self.step();self.step()
        self.assertEqual(self.step(),2)
        self.assertFalse(self.p.attached)
        self.assertEqual((self.p.speed,self.p.vertical),(0,0))
        self.assertEqual(self.step(),0)

    def test_throw_frame_three_and_motion_threshold(self):
        self.held()
        self.assertEqual(self.step(True,282),0)
        self.assertEqual(self.p.phase,6)
        self.assertEqual(self.step(speed=282),0)
        self.assertEqual(self.step(speed=282),2)
        self.assertEqual((self.p.speed,self.p.vertical),(282+2048,3072))
        self.assertEqual(self.step(),0)

    def test_throw_only_at_rest_and_cancel_releases_once(self):
        self.held(throw_only=True)
        self.step(True)
        self.assertEqual(self.p.phase,6)
        self.lib.player_lift_cancel(C.byref(self.p))
        self.assertEqual(self.p.events,2)
        self.assertEqual(self.p.phase,0)
        self.assertEqual(self.step(),0)

    def test_bush_with_strength_can_attach(self):
        self.begin(bush=True,strength=1)
        for _ in range(4): self.step()
        self.assertTrue(self.p.attached)

    # Carrying is the OoT upper-body scheme (Player_UpperAction_CarryActor):
    # LIFT_HOLD leaves the animation state machine in locomotion and loops
    # carryB_wait on the upper limbs only, so the legs keep walking.
    LIFT_HOLD = 5
    LINK_CLIP_CARRY_WAIT = 90   # generated link_clips.h
    CARRY_WAIT_FRAMES = 55      # LINK_FRAMES_CARRY_WAIT
    LINK_STATE_PUSH = 15        # link_anim_state.h; PUSH freezes locomotion

    def _overlay_clip(self):
        return C.c_int.in_dll(self.lib, 'upper_overlay_clip').value

    def _overlay_frame(self):
        return C.c_uint.in_dll(self.lib, 'upper_overlay_frame').value

    def _overlay_fraction(self):
        return C.c_uint.in_dll(self.lib, 'upper_overlay_fraction').value

    def _clears(self):
        return C.c_uint.in_dll(self.lib, 'upper_overlay_clears').value

    def test_hold_releases_push_state_so_legs_animate(self):
        """The regression: holding must not pin Link in PUSH, which blocks
        locomotion in demo.c and freezes the legs while he slides."""
        self.held()
        self.assertEqual(self.p.phase, self.LIFT_HOLD)
        self.assertNotEqual(self.lib.link_anim_state(), self.LINK_STATE_PUSH)

    def test_hold_drives_carry_wait_on_the_upper_body(self):
        self.held()
        self.step(action=False, speed=0)
        self.assertEqual(self._overlay_clip(), self.LINK_CLIP_CARRY_WAIT)

    def test_overlay_runs_at_the_locomotion_cadence(self):
        """link_anim_state.c advance() moves six ninths of a source frame per
        step. The overlay must match, or the arms outrun the legs."""
        self.held()
        seen = []
        for _ in range(9):
            self.step(action=False, speed=0)
            seen.append((self._overlay_frame(), self._overlay_fraction()))
        # 6/9 per step: frame 0 (fr 170), 1 (fr 85), 2 (fr 0), 2 (fr 170), ...
        self.assertEqual([f for f, _ in seen[:5]], [0, 1, 2, 2, 3])
        self.assertEqual([fr for _, fr in seen[:5]],
                         [170, 85, 0, 170, 85])

    def test_overlay_loop_wraps_at_the_clip_length(self):
        self.held()
        frames = set()
        for _ in range(self.CARRY_WAIT_FRAMES * 2):
            self.step(action=False, speed=0)
            frames.add(self._overlay_frame())
        self.assertLess(max(frames), self.CARRY_WAIT_FRAMES)

    def test_overlay_is_independent_of_speed(self):
        """No carry-walk clip exists: the upper loop runs at the same rate
        whether Link is still or moving; only the legs differ."""
        self.held()
        for _ in range(3):
            self.step(action=False, speed=0)
        still = (self._overlay_frame(), self._overlay_fraction())
        self.setUp()
        self.held()
        for _ in range(3):
            self.step(action=False, speed=600)
        self.assertEqual((self._overlay_frame(), self._overlay_fraction()), still)
        self.assertEqual(self._overlay_clip(), self.LINK_CLIP_CARRY_WAIT)

    def test_throw_clears_the_overlay(self):
        """Throw and put are full-body one-shots, not upper-body poses."""
        self.held()
        before = self._clears()
        self.step(action=True, speed=282)
        self.assertGreater(self._clears(), before)
        self.assertEqual(self._overlay_clip(), -1)

    def test_cancel_clears_the_overlay(self):
        self.held()
        self.lib.player_lift_cancel(C.byref(self.p))
        self.assertEqual(self._overlay_clip(), -1)

    def test_attach_release_frames_unchanged(self):
        """Attach still fires at frame 4; throw release still fires at frame 3."""
        self.begin()
        events = [self.step() for _ in range(4)]
        self.assertEqual(events[-1], 1)  # LIFT_ATTACH at frame 4
        # advance to HOLD
        for _ in range(100):
            if self.p.phase == self.LIFT_HOLD: break
            self.step()
        self.assertEqual(self.p.phase, self.LIFT_HOLD)
        self.step(action=True, speed=282)
        # throw: release fires at source frame 3 within the throw clip
        for _ in range(3):
            ev = self.step(speed=282)
            if ev == 2: break
        self.assertFalse(self.p.attached)
        self.assertEqual(ev, 2)  # LIFT_RELEASE

if __name__=='__main__': unittest.main()
