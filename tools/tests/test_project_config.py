"""Focused checks for portable launcher/build settings (no ROM or SDK needed)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/launcher'))
import project_config as config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'config.example.ini').write_text(
            (ROOT/'config.example.ini').read_text(), encoding='utf-8')

    def save(self, text):
        (self.root/'config.ini').write_text('[Paths]\n'+text, encoding='utf-8')

    def test_relative_paths_and_default_rom_directory(self):
        self.save('oot_decomp = sources/oot\njo_engine = SDK with spaces\n')
        paths = config.read_paths(self.root)
        self.assertEqual(Path(paths['jo_engine']), self.root/'SDK with spaces')
        self.assertEqual(Path(paths['oot_roms']), self.root/'sources/oot/baseroms/ntsc-1.2')

    def test_separate_rom_directory_and_literal_percent(self):
        self.save('oot_decomp = sources/oot\noot_roms = ROMs 100%/US 1.2\n')
        paths = config.read_paths(self.root)
        self.assertEqual(Path(paths['oot_roms']), self.root/'ROMs 100%/US 1.2')
        self.assertEqual(Path(paths['oot_decomp']), self.root/'sources/oot')

    def test_absolute_python_path_is_preserved(self):
        self.save('python = '+sys.executable+'\n')
        self.assertEqual(config.read_paths(self.root)['python'], sys.executable)

    @unittest.skipUnless(os.name == 'nt', 'Windows launcher')
    def test_powershell_save_and_python_read_agree(self):
        self.save('oot_decomp = sources/oot\noot_roms = ROMs 100%/US 1.2\n')
        script = """
$ErrorActionPreference = 'Stop'
. (Join-Path $env:DOSEI_TEST_REPO 'tools/launcher/project-config.ps1')
$ProjectRoot = $env:DOSEI_TEST_ROOT
$ConfigFile = Join-Path $ProjectRoot 'config.ini'
$values = Get-ProjectPaths
Save-ProjectPaths $values
Get-ProjectPaths | ConvertTo-Json -Compress
"""
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy',
                                 'Bypass', '-Command', script], check=True,
                                capture_output=True, text=True,
                                env=dict(os.environ, DOSEI_TEST_ROOT=str(self.root),
                                         DOSEI_TEST_REPO=str(ROOT)))
        powershell_paths = json.loads(result.stdout)
        python_paths = config.read_paths(self.root)
        self.assertEqual(powershell_paths.keys(), python_paths.keys())
        for key in python_paths:
            self.assertEqual(Path(powershell_paths[key]), Path(python_paths[key]), key)


if __name__ == '__main__':
    unittest.main()
