"""Independent read-only quota polling; never enables credit redemption."""
import time


class QuotaRefresh:
    INTERVAL = 300

    def __init__(self, enabled=True, clock=time.monotonic):
        self.enabled = enabled
        self.clock = clock
        self.next_due = 0
        self.failures = 0
        self.last_error = ''

    def due(self, busy=False):
        return self.enabled and not busy and self.clock() >= self.next_due

    def complete(self, success, error=''):
        if success:
            self.failures = 0
            self.last_error = ''
            delay = self.INTERVAL
        else:
            self.failures = min(self.failures+1, 5)
            self.last_error = error
            delay = min(300, 30 * 2**(self.failures-1))
        self.next_due = self.clock()+delay

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if self.enabled:
            self.next_due = 0
            self.failures = 0

