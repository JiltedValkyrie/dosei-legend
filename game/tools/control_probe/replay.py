"""Focused runtime verification. Requires the controlled disc in visible Kronos.

Two ten-step walks from the same state, a real jump, then the human's camera pair.
Outputs are evidence, not an automatic visual acceptance or performance claim.
"""
import json
from pathlib import Path
import time
import control as c


def main():
    session = json.loads((c.RUN / "session.json").read_text(encoding="utf-8-sig"))
    p = c.Process(session["pid"])
    deadline = time.monotonic() + 50
    while True:
        try: p.words(); break
        except RuntimeError:
            if time.monotonic() >= deadline: raise
            time.sleep(.1)
    out = c.RUN / "verification"
    out.mkdir(exist_ok=True)
    results = []
    # The old small 'L' HUD printed eye Y=275; actual feet are 185.
    pose = [37,185,4353,13714]
    close = [-91,262,4320,13714,-1820]
    for run in range(2):
        p.command(1,pose=pose,camera=close,legacy=0)
        result = p.command(2,steps=10,buttons=c.BUTTONS['b'],axis_x=128,axis_y=190)
        record = c.trace(p)
        (out / f"walk-{run}.json").write_text(json.dumps(record,indent=2))
        results.append((result,record))
        print(f"Walk {run}: {result['link']} camera {result['camera']}",flush=True)
    a,b = results
    if a[0]['link'] != b[0]['link'] or a[0]['camera'] != b[0]['camera']:
        raise AssertionError("Repeated Link/camera movement differs")
    def surfaces(record):
        return sorted((f['child_key'],f['world'],f['view'],f['command'],f['texture_sha256'])
                      for f in record['faces'])
    if surfaces(a[1]) != surfaces(b[1]):
        raise AssertionError("Repeated ground trace differs")
    p.command(1,pose=pose,camera=close,legacy=0)
    settled = p.command(2,steps=15,buttons=0,axis_x=128,axis_y=128)
    jumped = p.command(2,steps=4,buttons=c.BUTTONS['y'])
    if jumped['link'][1] <= settled['link'][1]:
        raise AssertionError("Normal jump did not raise Link")
    summary = dict(disc=session['iso_sha256'],repeat_walk=True,repeat_ground=True,
                   settled=settled,jumped=jumped,cameras={})
    for name,eye,legacy in [('oot',close,0),('legacy',[-214,235,4282,13714,0],1)]:
        p.command(1,pose=pose,camera=eye,legacy=legacy)
        record=c.trace(p)
        (out / f'{name}.json').write_text(json.dumps(record,indent=2))
        summary['cameras'][name] = [dict(source=f['source_face'],child=f['child_key'],
            z=[round(v[2],3) for v in f['view']],commands=f['matches']) for f in record['faces']]
        # Compare actual slCalcPoint outputs against captured matrix on the host.
        mat=record['matrix_q16']
        for f in record['faces']:
            if f['source_face'] is None:raise AssertionError('Unknown child')
            for world,view in zip(f['world'],f['view']):
                x,y,z=world;y=-y
                for axis in range(3):
                    expected=(x*mat[axis]+y*mat[3+axis]+z*mat[6+axis]+mat[9+axis])/65536
                    if abs(expected-view[axis]) > .02:
                        raise AssertionError('Matrix layout/sign does not match slCalcPoint')
    summary['matrix_matches_sgl']=True
    (out / 'summary.json').write_text(json.dumps(summary,indent=2))
    print('PASS: repeated walk/ground, normal jump, matrix agrees with SGL in both modes',flush=True)


if __name__=='__main__':main()
