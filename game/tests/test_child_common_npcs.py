"""Common source NPC rewards and complete Hylian sprite recipe identities."""
import os
from pathlib import Path
import re
import sys
import unittest
import test_graphics_backend as graphics
from test_child_route_npcs import function

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import child_common_npcs as common

OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


@unittest.skipUnless((OOT / common.SOURCES[0]).exists(), 'local decomp required')
class ChildCommonNpcs(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_all_hylian_heads_costumes_and_action_clips_have_unique_keys(self):
        recipes = common.hy_recipes(OOT)
        self.assertEqual(len(recipes), 22)
        self.assertEqual(sum(len(r['clips']) for r in recipes), 27)
        identities = [(r['obj'], r['skeleton'], clip, r['variant']) for r in recipes for clip in r['clips']]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertTrue(all(r['variant'] < 16 for r in recipes))
        self.assertEqual(recipes[5]['clips'], ['gObjOsAnim_31B0', 'gObjOsAnim_33B4'])
        self.assertEqual(recipes[7]['clips'], ['gObjOsAnim_265C', 'gObjOsAnim_2160'])
        self.assertEqual(common.keys_header(OOT), (GAME / 'oot-core/include/child_common_keys.h').read_text())

    def test_original_rewards_and_no_character_pose_work(self):
        rewards = {'En_Hy': ('EnHy_GetTextId', 'EnHy_UpdateTalkState', 'EnHy_WaitDogFoundRewardGiven',
                            'EnHy_FinishGivingDogFoundReward'),
                   'En_Ani': ('func_809B0558', 'func_809B05F0'),
                   'En_Tg': ('EnTg_GetTextId', 'EnTg_UpdateTalkState', 'EnTg_SpinIfNotTalking')}
        for actor, rel in zip(common.ACTORS, common.SOURCES):
            text = (OOT / rel).read_text(encoding='utf-8')
            changed = common.adapt(rel, text)
            self.assertNotRegex(changed, r'\b(?:Matrix_\w+|SkelAnime_Draw\w*|SkelAnime_Init\w*|Npc_TrackPoint|Actor_TrackPlayer)\(')
            header = common.adapt(rel[:-2]+'.h', (OOT / (rel[:-2]+'.h')).read_text())
            self.assertNotRegex(header, r'Vec3s (?:jointTable|morphTable)\[')
            for name in rewards.get(actor, ()):
                self.assertEqual(function(text, name), function(changed, name), name)

    def test_roof_heart_piece_waits_for_source_parent_and_sets_one_time_flag(self):
        text = (OOT / common.SOURCES[3]).read_text(encoding='utf-8')
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef struct {void*parent;} Actor;
typedef struct {int unused;} PlayState;
typedef struct EnAni {Actor actor;void(*action)(struct EnAni*,PlayState*);} EnAni;
enum {GI_HEART_PIECE=62,ITEMGETINF_15=21};
static int adult,awarded,offers;
#define LINK_IS_ADULT adult
#define SET_ITEMGETINF(x) (awarded=1)
static int Actor_HasParent(Actor*a,PlayState*p){return a->parent!=NULL;}
static void Actor_OfferGetItem(Actor*a,PlayState*p,int id,float xz,float y){assert(id==GI_HEART_PIECE);++offers;}
static void func_809B04F0(EnAni*a,PlayState*p){}
static void func_809B0524(EnAni*a,PlayState*p){}
static void EnAni_SetupAction(EnAni*a,void(*f)(EnAni*,PlayState*)){a->action=f;}
''' + function(text, 'func_809B0558') + r'''
int main(void){PlayState p={0};EnAni a={0};func_809B0558(&a,&p);assert(offers==1 && !awarded);
 a.actor.parent=&p;func_809B0558(&a,&p);assert(offers==1 && awarded && !a.actor.parent && a.action==func_809B04F0);
 adult=1;a.actor.parent=&p;func_809B0558(&a,&p);assert(a.action==func_809B0524);return 0;}
''')

    def test_specific_bottle_scan_uses_all_four_slots_only(self):
        text = (GAME / 'oot-core/src/bridge_child_route.cpp').read_text()
        original = (OOT / 'src/code/z_parameter.c').read_text(encoding='utf-8')
        # Whitespace-only source extraction: branch and slot range unchanged.
        actual = function(text, 'Inventory_HasSpecificBottle')
        self.assertEqual(re.sub(r'\s+', '', actual), re.sub(r'\s+', '', function(original, 'Inventory_HasSpecificBottle')))
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
typedef unsigned char u8;typedef int s32;
enum {SLOT_BOTTLE_1=18,SLOT_BOTTLE_4=21};
static struct{struct{struct{struct{u8 items[24];}inventory;}info;}save;}gSaveContext;
''' + actual + r'''
int main(void){memset(&gSaveContext,255,sizeof(gSaveContext));assert(!Inventory_HasSpecificBottle(21));
 gSaveContext.save.info.inventory.items[17]=21;assert(!Inventory_HasSpecificBottle(21));
 for(int i=18;i<=21;i++){gSaveContext.save.info.inventory.items[i]=21;assert(Inventory_HasSpecificBottle(21));
 gSaveContext.save.info.inventory.items[i]=255;}return 0;}
''')


if __name__ == '__main__':
    unittest.main()
