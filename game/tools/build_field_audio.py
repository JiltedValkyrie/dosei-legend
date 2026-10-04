"""Pack original day Field phrases into one resident SCSP bank.

Source seq_2.prg.seq selects init 3, moving 4..14, still entry 20 then 21..23.
Enemy/night branches are outside the agreed day-only, no-Field-enemy scope.
No PCM or level file is read when changing phrases during gameplay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import build_cutscene_audio as audio
import build_cart_tables as tables

SEQUENCES=tuple(range(3,15))+tuple(range(20,24))

def build(oot,out):
    source=oot/'extracted/ntsc-1.2/assets/audio'
    parts=out/'field-parts';parts.mkdir(parents=True,exist_ok=True)
    inputs=[Path(__file__),Path(audio.__file__),Path(audio.audio.__file__),
            source/'soundfonts/Soundfont_3.xml']
    inputs.extend(source/('samples/SampleBank_0/Sample%03d.wav'%int(sample.attrib['Name'].split('_')[-1]))
                  for sample in ET.parse(inputs[-1]).getroot().find('Samples'))
    inputs += [source/('sequences/seq_%d.seq'%s) for s in SEQUENCES]
    digest=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
    stamp=out/'FIELD.stamp'
    outputs=['FIELD_PCM.RAW','FIELD_LEVELS.RAW','field_score.h','field_phrases.h','field_manifest.json']
    if stamp.exists() and stamp.read_text()==digest and all((out/p).is_file() for p in outputs):return
    levels=bytearray();triggers=[];sections=[];frame=0;pcm=None;header=None
    for seq in SEQUENCES:
        name='F%02d'%seq
        audio.build_one(source,parts,name,seq,name,pitch_automation=True)
        h=(parts/(name.lower()+'_score.h')).read_text()
        raw=(parts/(name+'_PCM.RAW')).read_bytes()
        if pcm is None:pcm=raw;header=h.replace(name,'FIELD').replace(name.lower(),'field')
        elif raw!=pcm:raise ValueError('Field phrases must share exactly one sample bank')
        count=tables.define(h,name+'_FRAMES')
        sections.append((frame,frame+count,seq))
        triggers.extend((t[0]+frame,*t[1:]) for t in tables.rows(h,name.lower()+'_triggers'))
        levels.extend((parts/(name+'_LEVELS.RAW')).read_bytes());frame+=count
    if frame>65535:raise ValueError('Field phrase bank exceeds frame format')
    for key,value in [('FRAMES',frame),('LOOP_FRAME',sections[1][0]),('LEVEL_BYTES',len(levels)),('TRIGGER_COUNT',len(triggers))]:
        header=re.sub(r'(#define FIELD_'+key+r' )\d+',lambda m:m[1]+str(value),header)
    body='\n'.join('    { %d, %d, %d, %d, %d },'%t for t in triggers)
    header=re.sub(r'(static const field_trigger_t field_triggers\[\] = \{).*?\n\};',
                  lambda m:m[1]+'\n'+body+'\n};',header,flags=re.S)
    (out/'field_score.h').write_text(header)
    (out/'FIELD_PCM.RAW').write_bytes(pcm);(out/'FIELD_LEVELS.RAW').write_bytes(levels)
    (out/'field_phrases.h').write_text('/* Original source phrase boundaries, 60 Hz. */\n'
        'static const unsigned short field_phrases[][2]={'+','.join('{%d,%d}'%r[:2] for r in sections)+'};\n')
    (out/'field_manifest.json').write_text(json.dumps(dict(sequence=2,source_sequences=SEQUENCES,
        source_sha256=digest,frames=frame,phrases=sections,pcm_bytes=len(pcm),levels_bytes=len(levels),
        triggers=len(triggers),loop_frame=sections[1][0],soundfont=3),indent=2)+'\n')
    stamp.write_text(digest)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot',type=Path,default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'build/generated')
    a=ap.parse_args();build(a.oot,a.out)
