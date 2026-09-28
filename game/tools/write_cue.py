"""Write a cue for the selected build only, preserving other variants.

Track 01 is the data ISO. Red Book tracks from build_cdda.py (TRACKnn.BIN
next to the ISO) follow as AUDIO tracks with the standard 2 s pregap.
"""
from pathlib import Path
import sys

image, cue = map(Path, sys.argv[1:])
if not image.is_file() or image.parent.resolve() != cue.parent.resolve():
    raise SystemExit('Expected adjacent existing ISO and output cue')
lines = [f'FILE "{image.name}" BINARY', '  TRACK 01 MODE1/2048', '    INDEX 01 00:00:00']
for number in range(2, 100):
    track = image.parent / ('TRACK%02d.BIN' % number)
    if not track.is_file():
        break
    if track.stat().st_size % 2352:
        raise SystemExit(f'{track.name} is not whole 2352-byte sectors')
    lines += [f'FILE "{track.name}" BINARY', f'  TRACK {number:02d} AUDIO',
              '    PREGAP 00:02:00', '    INDEX 01 00:00:00']
cue.write_text('\n'.join(lines) + '\n')
