"""Windows native-input regression, isolated because the old bug aborts Python."""
import ctypes
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'


def exercise_native_input(directory):
    faulthandler.enable()
    sys.path.insert(0,str(SCRIPTS))
    from desktop_pet import Companion
    app = Companion(Path(directory)/'missing-usage.json',Path(directory)/'settings.json',tibo_enabled=False,sound_enabled=False)
    sprite = app.layered_sprite
    errors, moves, phases = [], [], set()
    finished = threading.Event()
    moving_enabled = threading.Event()
    moving_enabled.set()
    original_move = sprite.on_move
    original_release = sprite.on_release
    original_react = app.react

    def react(action):
        original_react(action)
        phases.add(action)

    app.react = react

    def move(x,y):
        # Displace only this app's event. Do not move the real desktop pointer.
        if not moving_enabled.is_set():
            original_move(x,y)
            return
        original_move(x+20+len(moves)%100,y+10+len(moves)%30)
        moves.append(app.root.geometry())
        phases.add(app.interaction)

    def release(x,y):
        original_release(x,y)
        phases.add(app.interaction)

    sprite.on_move,sprite.on_release = move,release
    sprite.on_menu = lambda x,y: phases.add('menu')
    app.root.report_callback_exception = lambda kind,value,tb: errors.append(str(value))
    send = sprite.user.SendMessageW
    send.argtypes = [ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    send.restype = ctypes.c_ssize_t

    def producer():
        try:
            for _ in range(30):
                send(sprite.hwnd,0x201,0,0)
                for _ in range(50):
                    send(sprite.hwnd,0x200,0,0)
                    time.sleep(.001)
                send(sprite.hwnd,0x202,0,0)
                time.sleep(.02)
            moving_enabled.clear()
            # Capture loss must clear drag state without clicking the bubble.
            send(sprite.hwnd,0x201,0,0)
            send(sprite.hwnd,0x1F,0,0)
            time.sleep(.05)
            send(sprite.hwnd,0x201,0,0)
            send(sprite.hwnd,0x202,0,0)
            time.sleep(.5)  # Let the single-click/double-click decision settle.
            send(sprite.hwnd,0x201,0,0)
            send(sprite.hwnd,0x202,0,0)
            time.sleep(.08)
            send(sprite.hwnd,0x201,0,0)
            send(sprite.hwnd,0x202,0,0)
            send(sprite.hwnd,0x205,0,0)
        except Exception as exc:
            errors.append(str(exc))
        finally:
            finished.set()

    def verify():
        if not finished.is_set():
            app.root.after(50,verify)
            return
        try:
            sprite.drain_events()
            assert not errors, errors
            assert len(moves)>20, len(moves)
            assert len(set(moves))>5, 'Drag must actually move the window'
            assert {'drag','land','click','pat','menu'} <= phases, (phases,app.click_count,app.drag_start,sprite.pointer_down)
            assert app.drag_start is None
            assert app.click_count == 1, app.click_count
            assert not sprite.pointer_down
            assert len(app.frame_times)>60, len(app.frame_times)
            try:
                sprite.present(b'bad buffer',0,0)
                raise AssertionError('Invalid pixel buffer accepted')
            except ValueError:
                pass
            # Shut down with a held pointer, then close again (idempotently).
            send(sprite.hwnd,0x201,0,0)
            app.close()
            app.close()
            assert sprite.closed and not sprite.pointer_down and not sprite.events
            print(json.dumps({'drags':30,'native_moves_sent':1500,
                              'ui_moves_handled':len(moves),'states':sorted(phases)}),flush=True)
        except Exception as exc:
            errors.append(str(exc))
            app.close()

    app.root.after(400,lambda:threading.Thread(target=producer,daemon=True).start())
    app.root.after(600,verify)
    app.root.mainloop()
    if errors:
        raise AssertionError(errors)


class NativeDragTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt','Windows layered window integration')
    def test_sent_mouse_messages_do_not_reenter_tk(self):
        with tempfile.TemporaryDirectory(prefix='reset-pet-regression-') as directory:
            result = subprocess.run([sys.executable,'-X','faulthandler',__file__,
                                     '--worker',directory],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('"drags": 30',result.stdout)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        exercise_native_input(sys.argv[2])
    else:
        unittest.main()
