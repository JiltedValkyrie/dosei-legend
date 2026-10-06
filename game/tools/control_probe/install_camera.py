"""Copy the production camera correction into the isolated control snapshot."""
import shutil
from control import ROOT,RUN


def main():
    game=RUN/'oot-sat/game'
    for name in ('player_camera.c','player_camera.h'):
        shutil.copy2(ROOT/'game/src'/name,game/'src'/name)
    p=game/'src/recomp.c';s=p.read_text()
    old='''    oot_follow_update(&link_follow, &recomp_link, recomp_link_yaw, false,
                      &recomp_camera, &recomp_yaw, &recomp_pitch);'''
    addition='''
    player_camera_constrain(&link_follow,&recomp_link,
        recomp_link.y-RECOMP_LINK_EYE_HEIGHT+oot_follow_scale.height+oot_follow_scale.y_offset,
        &recomp_camera,&recomp_pitch);'''
    assert s.count(old)==1
    s=s.replace(addition.replace('&recomp_camera,&recomp_pitch);','&recomp_camera);'),addition)
    if addition not in s:s=s.replace(old,old+addition)
    p.write_text(s,newline='\n')
    print('Camera fix copied to',game)


if __name__=='__main__':main()
