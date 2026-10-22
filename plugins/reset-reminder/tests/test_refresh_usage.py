import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'))
import refresh_usage as refresh
import desktop_pet as pet
from test_desktop_pet import snapshot, NOW


class RefreshTests(unittest.TestCase):
    def manual(self):
        data = snapshot()
        data['captured_at'] = pet.datetime.fromtimestamp(NOW+60,pet.CN).isoformat()
        data['usage']['rateLimits']['primary']['usedPercent'] = 40
        data['usage']['rateLimitResetCredits'] = {'availableCount':1}
        return data

    def test_new_quota_does_not_make_old_card_fresh(self):
        model = pet.display_model(snapshot(),self.manual(),NOW+60)
        self.assertEqual(model['remaining_percent'],60)
        self.assertEqual(model['rows'][1]['deadline'],NOW+7200)
        self.assertIn('上次记录',model['rows'][1]['title'])
        self.assertEqual(model['rows'][1]['color'],pet.MUTED)

    def test_newer_full_sync_takes_priority(self):
        model = pet.display_model(self.manual(),snapshot(),NOW+60)
        self.assertEqual(model['remaining_percent'],60)
        self.assertEqual(model['rows'][1]['title'],'重置卡到期')

    def test_first_manual_refresh_can_display_quota_without_cards(self):
        model = pet.display_model(None,self.manual(),NOW+60)
        self.assertEqual(model['remaining_percent'],60)
        self.assertIn('待完整同步',model['rows'][1]['title'])

    def test_invalid_cache_falls_back_to_full_snapshot(self):
        self.assertEqual(pet.display_model(snapshot(),{'usage':{}},NOW)['remaining_percent'],75)

    def test_complete_card_response_uses_new_card(self):
        manual = self.manual()
        manual['usage']['rateLimitResetCredits'] = {'credits':[]}
        row = pet.display_model(snapshot(),manual,NOW+60)['rows'][1]
        self.assertIn('暂无',row['date'])
        self.assertEqual(row['title'],'重置卡到期')

    def test_rejects_signed_out_and_invalid_quota(self):
        for account,limits in [(None,{}),({'type':'apiKey'},{}),
                               ({'type':'chatgpt'},{'rateLimits':{'primary':{'usedPercent':None}}})]:
            with self.assertRaises(refresh.RefreshError):
                refresh.make_snapshot(account,limits)

    def test_account_email_not_saved_and_full_snapshot_not_overwritten(self):
        data = refresh.make_snapshot({'type':'chatgpt','email':'test@example.invalid'},snapshot()['usage'])
        self.assertNotIn('test@example.invalid',json.dumps(data))
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder)/'usage.json'
            original.write_text('original')
            target = Path(folder)/'desktop-usage.json'
            refresh.save_snapshot(target,data)
            self.assertEqual(json.loads(target.read_text())['source'],'codex-app-server')
            self.assertEqual(original.read_text(),'original')
            self.assertEqual(len(list(Path(folder).glob('*.tmp'))),0)

    def test_protocol_only_requests_account_reads_and_reaps_process(self):
        class Process:
            def __init__(self):
                self.stdin = io.StringIO()
                self.stdout = io.StringIO('\n'.join(json.dumps({'id':i,'result':result}) for i,result in [
                    (1,{}),(2,{'account':{'type':'chatgpt'}}),(3,snapshot()['usage'])])+'\n')
                self.finished = False
                self.sent = None
            def poll(self):return None
            def terminate(self):self.sent = self.stdin.getvalue();self.finished = True
            def wait(self,timeout):return 0
        process = Process()
        with patch.object(refresh.subprocess,'Popen',return_value=process):
            result = refresh.fetch_snapshot(executable='mock-codex')
        methods = [json.loads(line)['method'] for line in process.sent.splitlines()]
        self.assertEqual(methods,['initialize','initialized','account/read','account/rateLimits/read'])
        self.assertTrue(process.finished)
        self.assertEqual(result['usage']['rateLimits']['primary']['usedPercent'],25)


if __name__ == '__main__':
    unittest.main()
