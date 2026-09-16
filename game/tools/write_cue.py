"""Write a cue for the selected build only, preserving other variants."""
from pathlib import Path
import sys

image, cue = map(Path, sys.argv[1:])
if not image.is_file() or image.parent.resolve() != cue.parent.resolve():
    raise SystemExit('Expected adjacent existing ISO and output cue')
cue.write_text(f'FILE "{image.name}" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n')
