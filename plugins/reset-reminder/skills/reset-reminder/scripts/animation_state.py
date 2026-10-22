"""Deterministic pet state machine; resolve transitions before rendering a frame."""
from enum import Enum
import math


class State(str, Enum):
    IDLE = 'idle'
    CLICK = 'click'
    POUT = 'pout'
    DRAG = 'drag'
    LAND = 'land'
    SLEEP = 'sleep'


class AnimationStateMachine:
    SLEEP_AFTER = 10.0
    ACTION_DURATION = 1.6
    TIMED = {State.CLICK, State.POUT, State.LAND}

    def __init__(self, now):
        self.state = State.IDLE
        self.started_at = self.last_touch = now
        self.held = False
        self.revision = 0

    def _enter(self, state, now):
        self.state, self.started_at = state, now
        self.revision += 1

    def touch(self, now):
        self.last_touch = now
        if self.state == State.SLEEP:
            self._enter(State.IDLE, now)

    def press(self, now):
        self.held = True
        self.touch(now)

    def release(self, now):
        self.held = False
        self.touch(now)

    def play(self, state, now):
        # User actions interrupt any current state directly, with no bridge pose.
        state = State(state)
        self.last_touch = now
        self._enter(state, now)

    def cancel(self, now):
        self.held = False
        self.play(State.IDLE, now)

    def update(self, now):
        if not self.held and now-self.last_touch >= self.SLEEP_AFTER:
            if self.state != State.SLEEP:
                self._enter(State.SLEEP, now)
        elif self.state in self.TIMED and now-self.started_at >= self.ACTION_DURATION:
            self._enter(State.IDLE, now)
        return self.state, max(0, now-self.started_at)


def animation_pose(action, elapsed, drag_angle=0):
    state = State(action)
    if state == State.SLEEP:
        return 5,0,0,'睡眠中 · 触碰唤醒'
    if state == State.DRAG:
        return 2,drag_angle,-3+math.sin(elapsed*8)*2,'轻一点呀'
    if state == State.LAND:
        return 4,0,-abs(math.sin(elapsed*9))*14*max(0,1-elapsed/1.6),'着陆成功'
    if state == State.POUT:
        return 3,6*math.sin(elapsed*9),0,'哼，再戳就生气'
    if state == State.CLICK:
        return 1,0,-math.sin(min(1,elapsed/1.6)*math.pi)*9,'你好呀'
    return 0,0,math.sin(elapsed*2)*2,'点击互动'


def sleep_particles(elapsed):
    """A new zzz every 0.75 s; each grows and rises for 2.4 s, then fades."""
    interval,lifetime = .75,2.4
    latest = math.floor(max(0,elapsed)/interval)
    particles = []
    for index in range(max(0,latest-3),latest+1):
        age = elapsed-index*interval
        if not 0 <= age < lifetime:
            continue
        progress = age/lifetime
        alpha = round(235*min(1,age/.15)*min(1,(lifetime-age)/.45))
        particles.append((160+28*progress,55-34*progress,9+14*progress,alpha))
    return particles
