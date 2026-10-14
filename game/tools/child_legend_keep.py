"""Resolve two implicit-layout keep effects against original extracted bytes."""
import re
import struct

DLISTS={'gEffDustDL':('gEffDustVtx',8,11), 'gEffFlash1DL':('gEffFlashVtx',12,15)}


def unique(data, needle, label):
    first=data.find(needle)
    if first<0 or data.find(needle,first+1)>=0:
        raise ValueError('Nonunique or absent original keep bytes: '+label)
    return first


def display_offset(oot,data,name):
    vname,index,count=DLISTS[name]
    path=oot/'extracted/ntsc-1.2/assets/objects/gameplay_keep'/(vname+'.inc.c')
    raw=bytearray()
    for row in re.findall(r'VTX\(([^)]+)\)',path.read_text()):
        values=[int(v.strip(),0) for v in row.split(',')]
        raw+=struct.pack('>3hH2h4B',*values[:3],0,*values[3:])
    if len(raw)!=64:raise ValueError('Keep effect quad changed: '+vname)
    vertex=unique(data,raw,vname)
    command=struct.pack('>II',0x01004008,0x04000000|vertex)
    candidates=[]
    for m in re.finditer(re.escape(command),data):
        start=m.start()-index*8
        first=0xD7 if name=='gEffDustDL' else 0xE7
        if start>=0 and data[start]==first and data[start+(count-1)*8:start+count*8]==struct.pack('>II',0xDF000000,0):
            candidates.append(start)
    if len(candidates)!=1:raise ValueError('Keep effect layout is not unique: '+name)
    return candidates[0]


def texture_offset(oot,data,name):
    from PIL import Image
    path=oot/'extracted/ntsc-1.2/assets/objects/gameplay_keep'/(name+'.i8.png')
    raw=Image.open(path).convert('L').tobytes()
    if len(raw)!=1024:raise ValueError('Keep dust texture changed: '+name)
    return unique(data,raw,name)
