"""Three-digit wallets may never index outside the ten HUD digit sprites."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class WalletHud(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_all_wallet_values_use_valid_digit_sprites(self):
        self.run_c(r'''
#include <assert.h>
''' + '#include "' + (ROOT / 'src/gameplay.h').as_posix() + '"\n' + r'''
gameplay_t gameplay;
static bool talk;
bool gameplay_is_talking(void) { return talk; }
static const unsigned rupee_sprite[1]={200};
static const unsigned digit_sprite[10]={100,101,102,103,104,105,106,107,108,109};
static unsigned count,shown[3];
static void rupee_hud_sprite(unsigned sprite,int x,int width) {
    if(sprite==200) { assert(x==26 && width==16); return; }
    assert(count<3 && sprite>=100 && sprite<110);
    assert(x==42+(int)count*8 && width==8);
    shown[count++]=sprite-100;
}
''' + graphics.function(ROOT / 'src/kokiri_sgl.c', 'void kokiri_rupee_hud_draw(') + r'''
int main(void) {
    for(unsigned value=0;value<=500;++value) {
        gameplay.rupees=value; count=0;
        assert(gameplay.rupees==value);
        kokiri_rupee_hud_draw();
        if(value>=100) {
            assert(count==3 && shown[0]==value/100);
            assert(shown[1]==value/10%10 && shown[2]==value%10);
        } else {
            assert(count==2 && shown[0]==value/10 && shown[1]==value%10);
        }
    }
    gameplay.rupees=65535; count=0; kokiri_rupee_hud_draw(); assert(count==3);
    talk=true; count=0; kokiri_rupee_hud_draw(); assert(count==0);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
