"""Cached Player poses remain exact across real banks, seeks and buffer reuse."""
import ctypes
import random
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / 'build/cd/PLAYANIM.PFB'


@unittest.skipUnless(BANK.exists(), 'staged Player frame bank required')
class PlayerPoseCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        hooks = folder / 'hooks.cpp'
        hooks.write_text('extern "C" void PlayerFrameBank_Fail(int,unsigned,unsigned) {}\n')
        compiler, env = compiler_env()
        library = folder / 'poses.so'
        result = subprocess.run(
            [compiler, '-std=gnu++17', '-O2', '-fPIC', '-shared',
             '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
             '-DPFB_DECODE_WORK_TEST', str(ROOT / 'oot-core/src/player_frame_decode.cpp'),
             str(ROOT / 'oot-core/src/player_frame_bank.cpp'), str(hooks), '-o', str(library)],
            capture_output=True, text=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(library))
        pointer = ctypes.c_void_p
        word = ctypes.c_uint32
        for name in ('PlayerFrameBank_Decode', 'PlayerFrameBank_DecodeCached'):
            getattr(cls.lib, name).argtypes = [pointer, word, pointer, pointer]
        cls.lib.PlayerFrameBank_Register.argtypes = [pointer, word]
        cls.lib.PlayerFrameBank_Unregister.argtypes = [pointer, word]
        cls.lib.PlayerFrameBank_PublishBlock.argtypes = [word, pointer, word, word]
        cls.lib.PlayerFrameBank_Retract.argtypes = [word, pointer]
        for name in ('PlayerFrameBank_Load', 'PlayerFrameBank_LoadCached'):
            getattr(cls.lib, name).argtypes = [word, word, pointer]
        cls.fields = word.in_dll(cls.lib, 'PlayerFrameBank_DecodeFields')
        cls.bank_bytes = BANK.read_bytes()
        count = struct.unpack_from('>I', cls.bank_bytes, 4)[0]
        cls.clips = []
        for index in range(count):
            offset = struct.unpack_from('>I', cls.bank_bytes, 8 + 4 * index)[0]
            end = (struct.unpack_from('>I', cls.bank_bytes, 12 + 4 * index)[0]
                   if index + 1 < count else len(cls.bank_bytes) - 4)
            clip_id = struct.unpack_from('>H', cls.bank_bytes, 8 + 4 * count + 2 * index)[0]
            frames = struct.unpack_from('>H', cls.bank_bytes, offset)[0]
            cls.clips.append((offset, frames, clip_id, end))

    def setUp(self):
        self.bank = ctypes.create_string_buffer(self.bank_bytes)
        self.base = ctypes.addressof(self.bank)
        self.out = (ctypes.c_int16 * 67)()
        self.scratch = (ctypes.c_int16 * 67)()
        self.reference = (ctypes.c_int16 * 67)()
        self.ref_scratch = (ctypes.c_int16 * 67)()
        self.lib.PlayerFrameBank_DecodeReset()

    def compare(self, clip, frame):
        offset = clip[0]
        self.lib.PlayerFrameBank_Decode(self.base + offset, frame, self.reference, self.ref_scratch)
        self.lib.PlayerFrameBank_DecodeCached(self.base + offset, frame, self.out, self.scratch)
        self.assertEqual(bytes(self.out), bytes(self.reference), (clip[2], frame))

    def test_all_real_frames_forward_then_backward_and_loop(self):
        self.assertEqual({self.bank_bytes[c[0] + 4] for c in self.clips}, {1, 2, 3})
        for clip in self.clips:
            for frame in range(clip[1]):
                self.compare(clip, frame)
            for frame in range(clip[1] - 1, -1, -1):
                self.compare(clip, frame)
            self.compare(clip, 0)
            self.compare(clip, clip[1] - 1)

    def test_random_seeks_blend_interleaving_and_repeated_aim_poses(self):
        rng = random.Random(0xA17B)
        for _ in range(100):
            blend = rng.sample(self.clips, 6)  # deliberately exceeds four slots
            for step in range(100):
                clip = blend[step % len(blend)]
                frame = rng.randrange(clip[1]) if step % 4 == 0 else step % clip[1]
                self.compare(clip, frame)
                if step % 7 == 0:
                    for _ in range(3):
                        self.compare(clip, frame)

    def test_forward_decode_reuses_delta_prefixes(self):
        clip = next(c for c in self.clips if c[1] >= 16 and self.bank_bytes[c[0] + 4] == 1)
        self.fields.value = 0
        for frame in range(16):
            self.lib.PlayerFrameBank_Decode(self.base + clip[0], frame, self.reference, self.ref_scratch)
        old_fields = self.fields.value
        self.fields.value = 0
        for frame in range(16):
            self.lib.PlayerFrameBank_DecodeCached(self.base + clip[0], frame, self.out, self.scratch)
        cached_fields = self.fields.value
        self.assertLess(cached_fields, old_fields // 2, (cached_fields, old_fields))
        # A held pose only decodes the four exact root/face fields.
        self.fields.value = 0
        self.lib.PlayerFrameBank_DecodeCached(self.base + clip[0], 15, self.out, self.scratch)
        self.assertEqual(self.fields.value, 4)

    def assert_loads_match(self, clip, frame):
        self.assertEqual(self.lib.PlayerFrameBank_Load(clip[2], frame, self.reference), 0)
        self.assertEqual(self.lib.PlayerFrameBank_LoadCached(clip[2], frame, self.out), 0)
        self.assertEqual(bytes(self.out), bytes(self.reference))

    def change_rotation_base(self, clip):
        address = self.base + clip[0] + 12 + 6  # rotation channel 3 base
        value = int.from_bytes(ctypes.string_at(address, 2), 'big')
        ctypes.memmove(address, ((value + 17) & 65535).to_bytes(2, 'big'), 2)

    def test_unregister_reload_same_address_discards_cached_poses(self):
        clip = next(c for c in self.clips if c[1] >= 8)
        self.assertGreater(self.lib.PlayerFrameBank_Register(self.base, len(self.bank_bytes)), 0)
        try:
            self.assert_loads_match(clip, 5)
            before = bytes(self.out)
            self.lib.PlayerFrameBank_Unregister(self.base, len(self.bank_bytes))
            self.change_rotation_base(clip)
            self.assertGreater(self.lib.PlayerFrameBank_Register(self.base, len(self.bank_bytes)), 0)
            self.assert_loads_match(clip, 5)
            self.assertNotEqual(bytes(self.out), before)
        finally:
            self.lib.PlayerFrameBank_Unregister(self.base, len(self.bank_bytes))

    def test_retract_publish_reused_block_discards_cached_poses(self):
        clip = next(c for c in self.clips if c[1] >= 8)
        offset, _, clip_id, end = clip
        pointer = self.base + offset
        length = end - offset
        slack = len(self.bank_bytes) - end
        self.assertEqual(self.lib.PlayerFrameBank_PublishBlock(clip_id, pointer, length, slack), 0)
        try:
            self.assert_loads_match(clip, 6)
            before = bytes(self.out)
            self.lib.PlayerFrameBank_Retract(clip_id, pointer)
            self.change_rotation_base(clip)
            self.assertEqual(self.lib.PlayerFrameBank_PublishBlock(clip_id, pointer, length, slack), 0)
            self.assert_loads_match(clip, 6)
            self.assertNotEqual(bytes(self.out), before)
        finally:
            self.lib.PlayerFrameBank_Retract(clip_id, pointer)


if __name__ == '__main__':
    unittest.main()
