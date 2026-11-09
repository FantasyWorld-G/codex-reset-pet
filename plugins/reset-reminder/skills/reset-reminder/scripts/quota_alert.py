"""Fresh, account-scoped exhaustion notices; never consume a reset credit."""
import hashlib
import math
from check_reset import account_snapshot, epoch
from auto_redeem import valid_policy


class QuotaAlert:
    def __init__(self, history=None):
        self.history = {key: value for key, value in (history or {}).items()
                        if isinstance(key, str) and isinstance(value, dict)
                        and type(value.get('captured')) in (int, float)
                        and math.isfinite(value['captured'])
                        and type(value.get('notified')) is bool} if isinstance(history, dict) else {}
        self.changed = False

    def evaluate(self, sources, policy, now):
        self.changed = False
        candidates = [s for s in sources if isinstance(s, dict)
                      and epoch(s.get('captured_at')) is not None]
        if not candidates:
            return None, False
        # Do not fall back to another account or older cache when the newest fails.
        source = max(candidates, key=lambda s: epoch(s['captured_at']))
        try:
            account = account_snapshot(source, now)
        except (ValueError, TypeError, KeyError, OverflowError):
            return None, False
        identity = str(source['usage']['accountId'])
        key = hashlib.sha256(identity.encode()).hexdigest()
        captured = epoch(source['captured_at'])
        previous = self.history.get(key, {})
        if not isinstance(previous, dict):
            previous = {}
        if captured < previous.get('captured', 0):
            return None, False
        windows = account['windows']
        exhausted = [w for w in windows if w['remaining_percent'] == 0
                     and (w['resets_at'] is None or w['resets_at'] > now)]
        recovered = bool(windows) and all(w['remaining_percent'] is not None
                                         and w['remaining_percent'] > 0 for w in windows)
        notified = previous.get('notified', False)
        if recovered:
            notified = False
        suppressed = valid_policy(policy) and policy['account_id'] == identity
        trigger = bool(exhausted) and not suppressed and not notified
        current = {'captured': captured, 'notified': notified or trigger}
        if previous != current:
            self.history[key] = current
            # Bound local history; keys are hashes, never emails or credentials.
            if len(self.history) > 20:
                oldest = min(self.history, key=lambda k: self.history[k].get('captured', 0))
                del self.history[oldest]
            self.changed = True
        if not exhausted or suppressed:
            return None, False
        cards = account['reset_cards']
        if cards is None or any(c['expires_at'] is None for c in cards['cards']):
            detail = '重置卡状态待确认，请在 Codex 中查看'
        elif cards['available_count']:
            detail = f"有 {cards['available_count']} 张有效重置卡，可在 Codex 中使用"
        else:
            detail = '暂无有效重置卡，请等待额度重置'
        return {'title': '额度已用完', 'detail': detail}, trigger
