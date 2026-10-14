"""Exact CD directory keys: fs_low.c and check_disc_directory.py must agree.

Compiles fs_low.c's own fs_symbol/fs_key/fs_key_less with the host compiler,
then checks every staged name, ordering against the checker and rejections.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_disc_directory as disc  # noqa: E402


def functions(source, names):
    out = []
    for name in names:
        m = re.search(r'^static [^\n]*\b' + name + r'\([^)]*\)\n\{', source, re.M)
        out.append(source[m.start():source.index('\n}\n', m.end()) + 3])
    return '\n'.join(out)


class FsDirectoryKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('gcc') or shutil.which('cc')
        if not cc:
            raise unittest.SkipTest('host C compiler unavailable')
        source = (ROOT / 'src/fs_low.c').read_text().replace('\r\n', '\n')
        body = functions(source, ('fs_symbol', 'fs_key', 'fs_key_less'))
        cls.tmp = tempfile.TemporaryDirectory()
        c = Path(cls.tmp.name) / 'keys.c'
        c.write_text('#include <stdbool.h>\n#include <stdio.h>\n#include <string.h>\n' + body + r'''
int main(void){char line[64];unsigned int k[2];
while(fgets(line,sizeof line,stdin)){char*n=strchr(line,'\n');if(n)*n=0;
 int disc=line[0]=='D';const char*s=line+2;
 if(fs_key(s,0xffffu,disc,k))printf("%u %u\n",k[0],k[1]);else puts("-");}
return 0;}
''')
        cls.exe = Path(cls.tmp.name) / 'keys'
        subprocess.run([cc, '-O1', '-o', str(cls.exe), str(c)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_keys(self, rows):
        text = ''.join(rows)
        out = subprocess.run([str(self.exe)], input=text, capture_output=True, text=True, check=True)
        return [None if l == '-' else tuple(map(int, l.split())) for l in out.stdout.splitlines()]

    def test_staged_names_match_checker_and_order(self):
        cd = ROOT / 'build/cd'
        if not cd.is_dir():
            self.skipTest('no staging')
        names = sorted(p.name.upper() for p in cd.iterdir() if p.is_file())
        keys = self.run_keys('R %s\n' % n for n in names)
        for name, key in zip(names, keys):
            self.assertEqual(key, disc.key(name), name)
        self.assertEqual(len(set(keys)), len(keys))
        # ISO/GFS order (dot and end lowest) equals key order.
        def iso(n):
            base, _, ext = n.partition('.')
            return base.ljust(8, '\0'), ext.ljust(3, '\0')
        self.assertEqual(sorted(names, key=iso), sorted(names, key=disc.key))

    def test_exact_rejections_and_disc_suffix(self):
        rows = ['R 0.BIN\n', 'D 0.BIN;1\n', 'R 0.BIN;1\n', 'R 0.bin\n', 'R TOOLONGNM.BIN\n',
                'R A.BINX\n', 'R .BIN\n', 'R CD\n', 'R CD.\n', 'R Z2S.OAP\n']
        k = self.run_keys(rows)
        self.assertEqual(k[0], k[1])
        self.assertEqual(k[2:7], [None] * 5)
        self.assertNotEqual(k[7], k[8])  # "CD" directory differs from "CD."
        self.assertEqual(k[9], disc.key('Z2S.OAP'))


if __name__ == '__main__':
    unittest.main()
