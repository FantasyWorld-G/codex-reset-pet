import importlib.util
import unittest
from pathlib import Path

script = Path(__file__).resolve().parents[1] / 'skills/reset-reminder/scripts/check_reset.py'
spec = importlib.util.spec_from_file_location('reminder', script)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = 1792656000


def account(reset=NOW+25000, remaining=40, account_id='test-account'):
    return m.account_snapshot({'captured_at': m.stamp(NOW), 'usage': {
        'accountId': account_id, 'rateLimitsByLimitId': {'codex': {
            'primary': {'resetsAt': reset, 'usedPercent': 100-remaining, 'windowDurationMins': 10080},
            'secondary': None}}}}, NOW)


def event(status='signal'):
    return {'id': '1', 'status': status, 'at': m.stamp(NOW), 'text': 'Tomorrow',
            'url': 'https://x.com/thsottiaux/status/1', 'countdown': None}


class ReminderTests(unittest.TestCase):
    def test_card_earliest_valid_ignores_used_and_expired(self):
        def credit(expiry, status='available'):
            return {'status': status, 'expiresAt': expiry, 'resetType': 'codexRateLimits'}
        cards = m.card_snapshot({'credits': [credit(NOW-10), credit(NOW+60, 'used'),
                                           credit(NOW+5000), credit(NOW+2000)]}, NOW)
        self.assertEqual(cards['available_count'], 2)
        snapshot = account()
        snapshot['reset_cards'] = cards
        display = m.display_status(snapshot, NOW)
        self.assertEqual(len(display['rows']), 2)
        self.assertEqual(display['reset_card']['marker'], '🔴')
        self.assertEqual(display['reset_card']['expiry_time'], cards['cards'][1]['expires_at_shanghai'])

    def test_card_unknown_empty_and_unknown_expiry(self):
        self.assertIsNone(m.card_snapshot(None, NOW))
        self.assertEqual(m.card_display({'reset_cards': m.card_snapshot({'credits': []}, NOW)}, NOW)['urgency'], 'none')
        cards = m.card_snapshot({'credits': [{'status': 'available', 'resetType': 'codexRateLimits'}]}, NOW)
        self.assertEqual(cards['available_count'], 1)
        self.assertEqual(m.card_display({'reset_cards': cards}, NOW)['urgency'], 'unknown')

    def test_card_rolls_to_next_expiry_after_use(self):
        raw = {'credits': [{'status': 'available', 'resetType': 'codexRateLimits', 'expiresAt': NOW+100},
                           {'status': 'available', 'resetType': 'codexRateLimits', 'expiresAt': NOW+90000}]}
        self.assertEqual(m.card_display({'reset_cards': m.card_snapshot(raw, NOW)}, NOW)['marker'], '🔴')
        raw['credits'][0]['status'] = 'used'
        self.assertEqual(m.card_display({'reset_cards': m.card_snapshot(raw, NOW)}, NOW)['marker'], '⚪')

    def test_display_color_thresholds_and_minute_precision(self):
        for seconds, expected in ((86401, '⚪'), (86400, '🟡'), (21600, '🟠'), (3600, '🔴'), (0, '🔴')):
            display = m.display_status(account(NOW+seconds), NOW)
            self.assertEqual(display['marker'], expected)
            self.assertRegex(display['reset_time'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        self.assertIn('待核实', m.display_status(account(NOW-1), NOW)['name'])
        self.assertEqual(m.display_status(None, NOW)['urgency'], 'unknown')

    def test_display_selects_earliest_window(self):
        payload = account(NOW+4000)
        payload['windows'].extend(account(NOW+2000)['windows'])
        display = m.display_status(payload, NOW)
        self.assertEqual(display['marker'], '🔴')
        self.assertIn('最近重置', display['name'])

    def test_threshold_crossing_and_no_repeats(self):
        state, alerts = m.evaluate({}, account(), None, {}, NOW)
        self.assertEqual(alerts, [])
        state, alerts = m.evaluate(state, account(), None, {}, NOW+4000)
        self.assertEqual([a['type'] for a in alerts], ['account_soon'])
        state, alerts = m.evaluate(state, account(), None, {}, NOW+4500)
        self.assertEqual(alerts, [])
        state, alerts = m.evaluate(state, account(), None, {}, NOW+22000)
        self.assertEqual(len(alerts), 1)

    def test_expired_is_not_confirmed_reset(self):
        state, _ = m.evaluate({}, account(), None, {}, NOW)
        _, alerts = m.evaluate(state, account(), None, {}, NOW+26000)
        self.assertEqual(alerts[0]['type'], 'account_due')

    def test_changed_account_has_separate_baseline(self):
        state, _ = m.evaluate({}, account(), None, {}, NOW)
        _, alerts = m.evaluate(state, account(NOW+100, account_id='another'), None, {}, NOW)
        self.assertEqual(alerts, [])

    def test_reset_window_rollover(self):
        state, _ = m.evaluate({}, account(), None, {}, NOW)
        _, alerts = m.evaluate(state, account(NOW+60000), None, {}, NOW)
        self.assertEqual(alerts[0]['type'], 'account_window_changed')

    def test_missing_window_and_unknown_values(self):
        envelope = {'captured_at': m.stamp(NOW), 'usage': {'accountId': 'a', 'rateLimits': {
            'primary': {'resetsAt': None, 'usedPercent': None}, 'secondary': None}}}
        out = m.account_snapshot(envelope, NOW)
        self.assertEqual(len(out['windows']), 1)
        self.assertIsNone(out['windows'][0]['remaining_percent'])
        self.assertIsNone(out['windows'][0]['remaining_seconds'])

    def test_reject_old_account(self):
        with self.assertRaises(ValueError):
            m.account_snapshot({'captured_at': m.stamp(NOW-700)}, NOW)

    def test_multiple_buckets(self):
        payload = {'captured_at': m.stamp(NOW), 'usage': {'accountId': 'a', 'rateLimitsByLimitId': {
            'codex': {'primary': {'usedPercent': 27}}, 'other': {'secondary': {'usedPercent': 10}}}}}
        out = m.account_snapshot(payload, NOW)
        self.assertEqual([x['remaining_percent'] for x in out['windows']], [73, 90])

    def test_signal_upgrades_notify_once(self):
        state, alerts = m.evaluate({}, None, {'events': [event()]}, {}, NOW)
        self.assertEqual(alerts, [])
        state, alerts = m.evaluate(state, None, {'events': [event('community_confirmed')]}, {}, NOW)
        self.assertEqual(alerts[0]['type'], 'tibo_update')
        _, alerts = m.evaluate(state, None, {'events': [event('community_confirmed')]}, {}, NOW)
        self.assertEqual(alerts, [])

    def test_false_confirmation_and_no_invented_deadline(self):
        feed = {'fetched_at': m.stamp(NOW), 'tweets': [{'id': '1', 'kind': 'signal', 'text': 'Tomorrow before 10am PST',
            'url': 'https://x.com/thsottiaux/status/1', 'at': m.stamp(NOW)}]}
        timeline = {'updated_at': m.stamp(NOW), 'events': [{'id': '1', 'type': 'reset', 'confirmed': False,
            'announced_at': m.stamp(NOW), 'url': 'https://x.com/thsottiaux/status/1'}]}
        out = m.community_snapshot(feed, timeline, NOW)
        self.assertEqual(out['events'][0]['status'], 'signal')
        self.assertIsNone(out['events'][0]['countdown'])
        feed['stale'] = True
        with self.assertRaises(ValueError):
            m.community_snapshot(feed, timeline, NOW)

    def test_errors_preserve_baseline_and_notify_at_three(self):
        state, _ = m.evaluate({}, None, {'events': [event()]}, {}, NOW)
        for count in range(1, 5):
            state, alerts = m.evaluate(state, None, None, {'community': 'offline'}, NOW)
            self.assertEqual(len(alerts), 1 if count == 3 else 0)
        state, alerts = m.evaluate(state, None, {'events': [event()]}, {}, NOW)
        self.assertEqual([a['type'] for a in alerts], ['source_recovered'])


if __name__ == '__main__':
    unittest.main()
