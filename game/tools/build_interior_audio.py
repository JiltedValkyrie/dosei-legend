"""Bake the original house/shop sequences through the shared music pipeline."""
import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
import build_cutscene_audio as bank


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'build/generated')
    args=ap.parse_args()
    source=args.oot/'extracted/ntsc-1.2/assets/audio'
    args.out.mkdir(parents=True,exist_ok=True)
    # sequence_table.h: NA_BGM_LINK_HOUSE 31; NA_BGM_SHOP 85.
    for name,sequence in (('HOUSE',31),('SHOP',85)):
        inputs=[Path(__file__),Path(bank.__file__),Path(bank.audio.__file__),
                source/('sequences/seq_%d.seq'%sequence)]
        font=source/('soundfonts/Soundfont_%d.xml'%bank.soundfont_of(inputs[-1]))
        inputs.append(font)
        inputs.extend(source/('samples/SampleBank_0/Sample%03d.wav'%
                             int(s.attrib['Name'].split('_')[-1]))
                      for s in ET.parse(font).getroot().find('Samples'))
        digest=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
        stamp=args.out/(name+'.stamp')
        outputs=[args.out/(name+'_PCM.RAW'),args.out/(name+'_LEVELS.RAW'),
                 args.out/(name.lower()+'_score.h'),args.out/(name.lower()+'_manifest.json')]
        if stamp.exists() and stamp.read_text()==digest and all(p.exists() for p in outputs):
            continue
        bank.build_one(source,args.out,name,sequence,name,preserve_intro=True)
        stamp.write_text(digest)

if __name__=='__main__':main()
