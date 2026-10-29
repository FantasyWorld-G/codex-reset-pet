"""Single-channel asynchronous nonverbal audio tied to animation transitions."""
import logging
import json
import os
from pathlib import Path
import time
import wave


class PetAudio:
    DRAG_HAPPY_DISTANCE = 180
    DRAG_HAPPY_SECONDS = .94

    def __init__(self, assets, enabled=True, backend=None, clock=time.monotonic, personal_assets=None):
        self.assets = Path(assets)
        self.provider = 'original-synthesis'
        if personal_assets is not None:
            personal = Path(personal_assets)
            try:
                metadata = json.loads((personal/'manifest.json').read_text('utf-8'))
                names = ('click_1','click_2','pout','drag','drag_happy','land','sleep','wake')
                if metadata.get('provider') != 'amitaro' or not all((personal/(n+'.wav')).is_file() for n in names):
                    raise ValueError('Incomplete personal voice pack')
                self.assets, self.provider = personal, 'amitaro'
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError, AttributeError):
                logging.exception('Personal voice pack unavailable; using bundled sounds')
        try:
            with wave.open(str(self.assets/'drag_happy.wav'), 'rb') as clip:
                self.drag_happy_seconds = clip.getnframes()/clip.getframerate()
        except (OSError, wave.Error, EOFError, ZeroDivisionError):
            self.drag_happy_seconds = self.DRAG_HAPPY_SECONDS
        self.enabled = enabled
        self.clock = clock
        if backend is None and os.name == 'nt':
            import winsound
            backend = winsound
        self.backend = backend
        self.last_state = 'idle'
        self.last_revision = -1
        self.last_play = float('-inf')
        self.clicks = 0
        self.closed = False
        self.warned = set()
        self.drag_happy = False
        self.happy_until = float('-inf')

    def stop(self):
        if self.backend:
            try:
                self.backend.PlaySound(None, 0)
            except Exception:
                logging.exception('Pet audio stop failed')

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop()

    def play(self, name):
        if self.closed or not self.enabled or self.backend is None:
            return False
        now = self.clock()
        # Ignore rapid repeated clicks; distinct actions interrupt the old clip.
        if now-self.last_play < .18 and name.startswith('click'):
            return False
        path = self.assets/(name+'.wav')
        if name == 'pet' and not path.is_file():
            path = self.assets/'click_2.wav'
        try:
            if not path.is_file():
                raise FileNotFoundError(path)
            flags = self.backend.SND_FILENAME | self.backend.SND_ASYNC | self.backend.SND_NODEFAULT
            self.backend.PlaySound(str(path), flags)
            self.last_play = now
            return True
        except Exception:
            if name not in self.warned:
                self.warned.add(name)
                logging.exception('Pet audio unavailable: %s', name)
            return False

    def observe(self, state, revision):
        state = str(getattr(state, 'value', state))
        if self.closed or revision == self.last_revision:
            return
        previous = self.last_state
        self.last_state, self.last_revision = state, revision
        if previous == 'sleep' and state != 'sleep':
            self.stop()
            if state == 'idle':
                self.play('wake')
        if state == 'click':
            self.clicks += 1
            self.play('click_'+str(1+(self.clicks-1)%2))
        elif state == 'pat':
            self.play('pet')
        elif state == 'drag':
            self.drag_happy = False
            self.happy_until = float('-inf')
            self.play('drag')
        elif state == 'land' and previous == 'drag' and self.clock() < self.happy_until:
            # The landing animation remains immediate; let the travel chuckle finish.
            pass
        elif state in ('pout', 'land', 'sleep'):
            self.play(state)
        # Timed animations returning to idle and ordinary frames stay silent.

    def drag_distance(self, distance, revision):
        # Observe immediately so a single large motion cannot play happy first,
        # then have the next animation frame overwrite it with the pickup sound.
        self.observe('drag', revision)
        if not self.drag_happy and distance >= self.DRAG_HAPPY_DISTANCE:
            self.drag_happy = True
            if self.enabled and not self.closed:
                if self.play('drag_happy'):
                    self.happy_until = self.clock()+self.drag_happy_seconds

    def close(self):
        if not self.closed:
            self.closed = True
            self.stop()
