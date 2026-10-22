import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'))
from animation_state import AnimationStateMachine, State, animation_pose, sleep_particles


class AnimationTests(unittest.TestCase):
    def test_ten_seconds_then_persistent_sleep(self):
        machine = AnimationStateMachine(0)
        self.assertEqual(machine.update(9.999)[0],State.IDLE)
        self.assertEqual(machine.update(10),(State.SLEEP,0))
        self.assertEqual(machine.update(100),(State.SLEEP,90))
        self.assertEqual(animation_pose(*machine.update(100))[0],5)

    def test_action_completion_never_inserts_sleep_frame(self):
        for action in (State.CLICK,State.POUT,State.LAND):
            machine = AnimationStateMachine(0)
            machine.play(action,1)
            self.assertEqual(machine.update(2.59)[0],action)
            for now in (2.61,2.62,2.8,6.5,10.99):
                self.assertEqual(animation_pose(*machine.update(now))[0],0)
            self.assertEqual(machine.update(11)[0],State.SLEEP)

    def test_idle_and_sleep_can_switch_directly_to_every_action(self):
        for source_time in (0,11):
            for target,frame in ((State.CLICK,1),(State.POUT,3),(State.DRAG,2),(State.LAND,4)):
                machine = AnimationStateMachine(0)
                machine.update(source_time)
                machine.play(target,source_time)
                self.assertEqual(animation_pose(*machine.update(source_time))[0],frame)

    def test_press_and_hold_prevents_sleep_and_release_restarts_timeout(self):
        machine = AnimationStateMachine(0)
        machine.update(20)
        machine.press(21)
        self.assertEqual(machine.update(40)[0],State.IDLE)
        machine.play(State.DRAG,40)
        self.assertEqual(machine.update(100)[0],State.DRAG)
        machine.release(100)
        machine.play(State.LAND,100)
        self.assertEqual(machine.update(109.99)[0],State.IDLE)
        self.assertEqual(machine.update(110)[0],State.SLEEP)

    def test_interrupt_and_cancel_have_no_bridge_action(self):
        machine = AnimationStateMachine(0)
        machine.play(State.CLICK,1)
        machine.play(State.POUT,1.2)
        self.assertEqual(machine.update(1.2),(State.POUT,0))
        machine.press(2)
        machine.play(State.DRAG,2.2)
        machine.cancel(3)
        self.assertFalse(machine.held)
        self.assertEqual(machine.update(3),(State.IDLE,0))

    def test_repeated_touch_moves_sleep_deadline(self):
        machine = AnimationStateMachine(0)
        machine.touch(9)
        self.assertEqual(machine.update(18.99)[0],State.IDLE)
        self.assertEqual(machine.update(19)[0],State.SLEEP)

    def test_zzz_grows_rises_and_keeps_emitting_without_accumulation(self):
        early,late = sleep_particles(.1)[0],sleep_particles(.6)[0]
        self.assertGreater(late[2],early[2])
        self.assertLess(late[1],early[1])
        for elapsed in (1,2.4,10,3600,86400):
            particles = sleep_particles(elapsed)
            self.assertTrue(1 <= len(particles) <= 4)
            self.assertTrue(any(p[3]>0 for p in particles))


if __name__ == '__main__':
    unittest.main()
