"""Isolated M6/M7 source tracks and audio; no runtime registration or CD staging.

Unmapped cues remain explicitly listed. Never turn this audit into a shortcut
that grants the ocarina or skips the bridge to make Field appear reachable.
"""
import argparse
import hashlib
import json
from pathlib import Path

import build_cutscenes as cs
import build_cutscene_audio as music


def build(oot, out, audio=False):
    out.mkdir(parents=True, exist_ok=True)
    scenes=oot/'extracted/ntsc-1.2/assets/scenes/overworld'
    tracks=[]
    for stem, path, scene in (
        ('BRIDGECS','spot10/gLostWoodsFairyOcarinaCs.csdata.inc.c','SPOT10'),
        ('FIELDCS','spot00/gHyruleFieldIntroCs.csdata.inc.c','FIELD_GAMEPLAY')):
        source=scenes/path
        entry=dict(key=stem,path=source,scene=scene,scene_bgm=None,
                   audit_misc=('CS_MISC_SHOW_TITLE_CARD',))
        parsed=cs.read_cutscene(entry)
        (out/(stem+'.BIN')).write_bytes(cs.pack_track(parsed['track']))
        parsed.pop('track')
        parsed['ignored']=sorted(parsed['ignored'])
        parsed['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        parsed['unmapped_player_cues']=sorted({c['id'] for c in parsed['player_cues'] if c['clip'] is None})
        parsed['unmapped_music']=[m['sequence'] for m in parsed['music'] if m['bank'] is None]
        tracks.append(parsed)
    audio_banks=[]
    if audio:
        for name, sequence in (('OWL',90),('FAIRYGET',61)):
            audio_banks.append(music.build_one(oot/'extracted/ntsc-1.2/assets/audio',
                out/'audio',name,sequence,name,preserve_intro=True))
    result=dict(runtime_registered=False,tracks=tracks,audio_banks=audio_banks,
        route=[
            dict(step='Boss blue warp',implemented=True,requirement='Cleared Gohma room 1; commit Emerald only after forest load succeeds'),
            dict(step='Tree aftermath',implemented=False,requirement='Source post-boss story chain remains open'),
            dict(step='Forest exit',implemented=True,requirement='Emerald unlocks guard; exit 2 reaches Woods spawn 9 / bridge room 5'),
            dict(step='Saria farewell',implemented=False,requirement='Source EVENTCHKINF_C1 and Fairy Ocarina grant; destination Field spawn 3'),
            dict(step='Field intro',implemented=False,requirement='EVENTCHKINF_A0 once-only; source stop tick 330'),
            dict(step='Outside-Kokiri owl',implemented=False,requirement='Params 0x004C, switch 12, EVENTCHKINF_6F; repeat choice 0, finish choice 1'),
            dict(step='Return to Woods',implemented=False,requirement='Field exit 4 to Woods spawn 8; no repeated bridge grant')],
        field_music=dict(controller_sequence=2,init_sequence=3,default_sequences=list(range(4,15)),
                         still_sequences=list(range(20,24)),runtime_implemented=False),
        limitations=['Camera assets are not live story hooks.',
                     'Saria and Link farewell animations, title card, item grant, save/skip ownership remain required.',
                     'Owl audio requires conversation ownership and area music restoration.',
                     'Field logic controller must select musical phrases; sequence 2 is not a standalone theme.'])
    (out/'story_preflight.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot',type=Path,default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'build/field-preflight/story')
    parser.add_argument('--audio',action='store_true')
    args=parser.parse_args()
    print(json.dumps(build(args.oot,args.out,args.audio),indent=2))
