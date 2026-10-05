"""Paired static-render and normal walking cost in the same visible emulator."""
import json
import time
import control as c


def main():
    import argparse
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--folder',default='tr-v6')
    args=ap.parse_args()
    p=c.Process(json.loads((c.RUN/'session.json').read_text(encoding='utf-8-sig'))['pid'])
    result=[]
    for mode in (0,2,2,0):
        p.command(4,hud=1+(mode<<8))
        p.command(1,pose=[37,185,4353,13714],camera=[-91,262,4320,13714,-1820],legacy=0)
        a=p.words()[22];t=time.monotonic()
        while time.monotonic()-t<3:time.sleep(.1)
        elapsed=time.monotonic()-t;fps=(p.words()[22]-a)/elapsed
        t=time.monotonic()
        state=p.command(2,steps=90,buttons=c.BUTTONS['b'],axis_x=128,axis_y=220)
        row=dict(mode=mode,static_frames_per_second=round(fps,2),
                 walk90_seconds=round(time.monotonic()-t,3),state=state)
        result.append(row);print(json.dumps(row),flush=True)
    p.command(4,hud=513)
    p.command(1,pose=[37,185,4353,13714],camera=[-91,262,4320,13714,-1820],legacy=0)
    (c.RUN/'verification'/args.folder/'performance.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':main()
