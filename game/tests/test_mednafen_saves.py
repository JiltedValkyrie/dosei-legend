"""Save migration only; never starts an emulator or alters real save files."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'nt', 'PowerShell launcher')
class MednafenSaves(unittest.TestCase):
    def test_disc_hash_changes_preserve_latest_active_save(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            sav = base / 'sav'
            sav.mkdir()
            def backup(digit, active, time):
                data = bytearray(32768)
                data[:16] = b'BackUpRam Format'
                data[128] = 128 if active else 0
                data[132:139] = b'DOSEI0\0'
                data[200] = int(digit)
                p = sav / ('game-clean.' + digit * 32 + '.bkr')
                p.write_bytes(data)
                os.utime(p, (time, time))
                return p
            old = backup('1', True, 100)
            latest_save = backup('2', True, 200)
            empty_new_disc = backup('3', False, 300)
            script = base / 'probe.ps1'
            helper = str(ROOT / 'tools/launcher/mednafen-saves.ps1').replace("'", "''")
            literal_base = str(base).replace("'", "''")
            script.write_text(". '" + helper + "'\nInitialize-MednafenSaves -Executable '" +
                              literal_base + "/mednafen.exe' -Image 'game-clean.cue'\n")
            def run():
                subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                '-File', str(script)], check=True, capture_output=True, text=True)
            run()
            stable = sav / 'game-clean.bkr'
            self.assertEqual(stable.read_bytes(), latest_save.read_bytes())
            backup('4', True, 400)
            run()
            self.assertEqual(stable.read_bytes(), latest_save.read_bytes())
            self.assertTrue(old.exists() and empty_new_disc.exists())
            stable.unlink()
            (base / 'mednafen.cfg').write_text('filesys.fname_sav custom.%f.%x\n')
            run()
            self.assertFalse(stable.exists())


if __name__ == '__main__':
    unittest.main()
