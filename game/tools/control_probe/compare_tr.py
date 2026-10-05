"""Matched-camera/movement A/B in the real visible Kronos window."""
import json
import struct
import subprocess
import time
import re
import shutil
import control as c


def snapshot(p, out, name):
    data=c.trace(p)
    # Field streaming can take more than the mailbox's three settling frames.
    # Every fixture covers both local pieces: do not compare a partial load.
    end=time.monotonic()+10
    while len(data['faces'])!=10:
        if time.monotonic()>end:raise RuntimeError('Local patch did not fully stream')
        time.sleep(.2);data=c.trace(p)
    data['tr_vram']=struct.unpack('>I',c.t2(p.read(p.ptrs['HighWram']+p.tr_offset,4)))[0]
    work=c.t2(p.read(p.ptrs['LowWram']+0x1f000,460))
    data['tr_counts']=struct.unpack_from('>3I',work,448)
    raw=p.read(p.ptrs['Vdp1Ram'],0x13300)
    commands=[];at=0;ret=0
    for _ in range(2456):
        cmd=struct.unpack_from('>16H',raw,at)
        if cmd[0]&0x8000:break
        jp=(cmd[0]>>12)&7
        if not jp&4:commands.append(dict(address=at,words=cmd))
        nxt=at+32
        if jp&3==1:nxt=cmd[1]*8
        elif jp&3==2:ret,nxt=at+32,cmd[1]*8
        elif jp&3==3:nxt=ret
        if nxt>=len(raw) or nxt==at:break
        at=nxt
    data['commands']=commands
    (out/(name+'.json')).write_text(json.dumps(data,indent=2))
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(c.ROOT/'game/tools/capture-kronos.ps1'),'-ViewerId',str(p.pid),
        '-OutputPath',str(out/(name+'.png'))],check=True,capture_output=True)
    print(name, data['status']['link'],data['tr_counts'],len(commands),flush=True)


def main():
    import argparse
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--folder',default='tr-v6')
    args=ap.parse_args()
    p=c.Process(json.loads((c.RUN/'session.json').read_text(encoding='utf-8-sig'))['pid'])
    symbols=subprocess.check_output([str(c.ROOT.parent/'sh2eb-elf/bin/sh2eb-elf-nm.exe'),
        '--target=coff-sh',str(c.RUN/'oot-sat/game/build/game.elf')],text=True)
    p.tr_offset=int(re.search(r'^([0-9a-f]+) [a-zA-Z] _tr_vram$',symbols,re.M)[1],16)-0x06000000
    end=time.monotonic()+60
    while True:
        try:p.words();break
        except (RuntimeError,OSError):
            if time.monotonic()>end:raise
            time.sleep(.2)
            ready=c.Process(p.pid);ready.tr_offset=p.tr_offset;p=ready
    # Video RAM can be allocated after Work RAM during GUI startup.
    ready=c.Process(p.pid);ready.tr_offset=p.tr_offset;p=ready
    out=c.RUN/'verification'/args.folder;out.mkdir(exist_ok=True)
    shutil.copy2(c.RUN/'verification/tr-assets.json',out/'assets.json')
    for mode in (0,2):
        p.command(4,hud=1+(mode<<8))
        # Enter both local streaming cells before each pass. Hysteresis can
        # otherwise leave the first baseline pose on a different LOD set.
        p.command(1,pose=[736,360,4675,13714],camera=[500,440,4675,13714,-1820],legacy=0)
        time.sleep(1.5)
        for name,eye,legacy in [('oot',[-91,262,4320,13714,-1820],0),
                                ('far',[-214,235,4282,13714,0],1)]:
            p.command(1,pose=[37,185,4353,13714],camera=eye,legacy=legacy)
            snapshot(p,out,f'm{mode}-{name}')
        p.command(1,pose=[37,185,4353,13714],camera=[-91,262,4320,13714,-1820],legacy=0)
        for n in (10,20,30):
            p.command(2,steps=10,buttons=c.BUTTONS['b'],axis_x=128,axis_y=220)
            snapshot(p,out,f'm{mode}-walk{n}')
        for name,pose,eye,legacy in [
            ('corner',[23,4,3407,44546],[-206,54,3226,11317,0],1),
            ('center',[1192,328,4114,14082],[1066,415,4078,14082,-1820],0)]:
            p.command(1,pose=pose,camera=eye,legacy=legacy)
            snapshot(p,out,f'm{mode}-{name}')
            p.command(2,steps=15,buttons=0,axis_x=128,axis_y=128)
            p.command(2,steps=8,buttons=c.BUTTONS['y'],axis_x=128,axis_y=128)
            snapshot(p,out,f'm{mode}-{name}-jump')
            p.command(2,steps=20,buttons=0,axis_x=200,axis_y=128)
            snapshot(p,out,f'm{mode}-{name}-turn')
    p.command(1,pose=[37,185,4353,13714],camera=[-91,262,4320,13714,-1820],legacy=0)


if __name__=='__main__':main()
