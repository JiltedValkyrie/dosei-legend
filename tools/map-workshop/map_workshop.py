"""Map Workshop entry point; shares asset tools without requiring their UI."""
import argparse
from pathlib import Path
import sys
import tkinter as tk

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'mesh-workshop'))
from level_viewport import RoomViewport


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    root=tk.Tk(); root.withdraw()
    viewport=RoomViewport(root,autoload=not args.smoke_test)
    viewport.bind('<Destroy>',lambda event:root.quit() if event.widget==viewport else None)
    if args.smoke_test:
        viewport.withdraw(); root.update()
        assert viewport.title()=='Dosei Legend - Map Workshop'
        viewport.close(); print('Map Workshop UI smoke passed; no assets changed.')
    else: root.mainloop()
    root.destroy()


if __name__=='__main__': main()
