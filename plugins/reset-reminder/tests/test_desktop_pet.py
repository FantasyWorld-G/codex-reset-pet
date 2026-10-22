import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/reset-reminder/scripts'))
import desktop_pet as pet

NOW = 1792656000


def snapshot():
    return {'captured_at': pet.datetime.fromtimestamp(NOW, pet.CN).isoformat(), 'usage': {
        'accountId': 'test-account', 'rateLimits': {'primary': {'resetsAt': NOW+172800, 'usedPercent': 25}},
        'rateLimitResetCredits': {'credits': [{'status': 'available', 'resetType': 'codexRateLimits', 'expiresAt': NOW+7200}]}}}


class DesktopTests(unittest.TestCase):
    def test_native_alpha_is_premultiplied_without_color_key(self):
        from PIL import Image
        image = Image.new('RGBA',(2,1))
        image.putdata([(100,200,50,128),(255,0,255,0)])
        pixels = pet.premultiplied_bgra(image)
        self.assertEqual(list(pixels[:4]),[25,100,50,128])
        self.assertEqual(list(pixels[4:]),[0,0,0,0])

    def test_pout_motion_is_continuous(self):
        a = pet.animation_pose('pout',.16)[1]
        b = pet.animation_pose('pout',.161)[1]
        self.assertLess(abs(a-b),.1)

    def test_click_drag_and_landing_use_distinct_expressions(self):
        self.assertEqual(pet.animation_pose('click',.3)[0],1)
        self.assertEqual(pet.animation_pose('drag',.3,12)[:2],(2,12))
        self.assertEqual(pet.animation_pose('pout',.3)[0],3)
        self.assertEqual(pet.animation_pose('land',.3)[0],4)
        self.assertLess(pet.animation_pose('land',.3)[2],0)
        self.assertEqual(pet.animation_pose('idle',0)[0],0)

    def test_generated_sprite_atlas_has_six_transparent_cells(self):
        from PIL import Image
        path = Path(__file__).resolve().parents[1] / 'assets/maid-sprites.png'
        with Image.open(path) as image:
            self.assertEqual(image.mode,'RGBA')
            self.assertEqual(image.size,(1536,1024))
            for i in range(6):
                cell = image.crop((i%3*512,i//3*512,i%3*512+512,i//3*512+512))
                self.assertEqual(cell.getchannel('A').getextrema()[0],0)
                self.assertGreater(cell.getchannel('A').getextrema()[1],240)

    def test_two_rows_and_earliest_controls_pet(self):
        model = pet.view_model(snapshot(), NOW)
        self.assertEqual(len(model['rows']), 2)
        self.assertEqual(model['pet_color'], pet.time_color(7200))
        self.assertNotEqual(model['rows'][0]['color'], model['rows'][1]['color'])

    def test_local_countdown_advances_without_account_fetch(self):
        a = pet.view_model(snapshot(), NOW)
        b = pet.view_model(snapshot(), NOW+60)
        self.assertEqual(a['rows'][1]['seconds']-b['rows'][1]['seconds'], 60)
        self.assertNotEqual(a['rows'][1]['remaining'], b['rows'][1]['remaining'])

    def test_color_continuity_and_expiration(self):
        for threshold in [3600,21600,86400]:
            a,b = pet.time_color(threshold),pet.time_color(threshold+1)
            self.assertTrue(all(abs(int(a[i:i+2],16)-int(b[i:i+2],16))<=1 for i in [1,3,5]))
        self.assertEqual(pet.time_color(-10),pet.time_color(0))

    def test_stale_data_is_labelled_and_muted(self):
        model = pet.view_model(snapshot(), NOW+5401)
        self.assertTrue(model['stale'])
        self.assertIn('上次记录', model['footer'])
        self.assertEqual(model['pet_color'],pet.MUTED)

    def test_expired_card_removed_and_used_card_removed(self):
        raw = snapshot()
        raw['usage']['rateLimitResetCredits']['credits'][0]['status'] = 'used'
        self.assertIn('暂无', pet.view_model(raw,NOW)['rows'][1]['date'])
        self.assertIn('暂无', pet.view_model(snapshot(),NOW+7201)['rows'][1]['date'])


if __name__ == '__main__':
    unittest.main()
