import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name == 'nt', 'Windows upgrade process handling')
class UpgradeCloseTests(unittest.TestCase):
    def test_graceful_close_and_stale_pid_identity_guard(self):
        with tempfile.TemporaryDirectory(prefix='pet upgrade ') as temporary:
            root = Path(temporary).resolve()
            app, data = root/'app', root/'data'
            data.mkdir()
            script = app/'plugins/reset-reminder/skills/reset-reminder/scripts/desktop_pet.py'
            script.parent.mkdir(parents=True)
            script.write_text('''import tkinter as tk,sys,json,os
from pathlib import Path
data=Path(sys.argv[2]).parent
root=tk.Tk()
root.withdraw()
def close():
    (data/'closed.txt').write_text('graceful')
    root.destroy()
root.protocol('WM_DELETE_WINDOW',close)
root.update()
(data/'desktop-runtime.json').write_text(json.dumps(dict(pid=os.getpid(),lifecycle='running')))
root.mainloop()
''', 'utf-8')
            process = subprocess.Popen([sys.executable, str(script), '--settings', str(data/'desktop-settings.json')],
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic()+10
                while not (data/'desktop-runtime.json').exists() and time.monotonic()<deadline:
                    time.sleep(.05)
                self.assertTrue((data/'desktop-runtime.json').exists())
                record = root/'install.json'
                def run():
                    result = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
                        '-File',str(ROOT/'scripts/stop_installed_pet.ps1'),'-InstallRoot',str(root)],
                        capture_output=True,text=True,timeout=25)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                # A mismatched installation must leave a reused/live PID alone.
                record.write_text(json.dumps(dict(appRoot=str(root/'other-app'),dataDir=str(data))))
                run()
                self.assertIsNone(process.poll())
                self.assertFalse((data/'closed.txt').exists())
                record.write_text(json.dumps(dict(appRoot=str(app),dataDir=str(data))))
                run()
                process.wait(timeout=5)
                self.assertEqual((data/'closed.txt').read_text(),'graceful')
                # Repeated upgrades tolerate stale status with an absent process.
                run()
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
