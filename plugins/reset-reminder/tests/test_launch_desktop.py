"""Regression: a desktop pet must outlive the launcher's kill-on-close job."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'
sys.path.insert(0, str(SCRIPTS))
import launch_desktop


class LaunchTests(unittest.TestCase):
    def test_denied_launch_does_not_fall_back(self):
        with patch.object(launch_desktop.subprocess, 'Popen', side_effect=PermissionError) as popen:
            with self.assertRaises(PermissionError):
                launch_desktop.launch(['python', 'pet.py'])
        self.assertEqual(popen.call_count, 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows job lifetime regression')
    def test_child_survives_launch_job_termination(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory/'child.json'
            child = directory/'child.py'
            child.write_text(
                'import sys, time, json\nfrom pathlib import Path\n'
                f'sys.path.insert(0, {str(SCRIPTS)!r})\n'
                'from launch_desktop import in_windows_job, windows_job_flags\n'
                'time.sleep(0.8)\n'
                f'Path({str(output)!r}).write_text(json.dumps({{"in_job": in_windows_job(), "flags": windows_job_flags()}}))\n',
                encoding='utf-8')
            parent = directory/'parent.py'
            parent.write_text('''import ctypes as c, sys
from ctypes import wintypes as w
sys.path.insert(0, sys.argv[1])
from launch_desktop import launch
class Basic(c.Structure):
    _fields_=[('ProcessTime',c.c_int64),('JobTime',c.c_int64),('Flags',w.DWORD),
              ('MinWorking',c.c_size_t),('MaxWorking',c.c_size_t),('ActiveLimit',w.DWORD),
              ('Affinity',c.c_size_t),('Priority',w.DWORD),('Scheduling',w.DWORD)]
class Extended(c.Structure):
    _fields_=[('Basic',Basic),('IO',c.c_uint64*6),('Memory',c.c_size_t*4)]
k=c.WinDLL('kernel32',use_last_error=True)
k.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR]
k.CreateJobObjectW.restype=w.HANDLE
k.GetCurrentProcess.restype=w.HANDLE
k.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
k.TerminateJobObject.argtypes=[w.HANDLE,w.UINT]
job=k.CreateJobObjectW(None,None)
limits=Extended(); limits.Basic.Flags=0x2800
assert k.SetInformationJobObject(job,9,c.byref(limits),c.sizeof(limits)),c.get_last_error()
assert k.AssignProcessToJobObject(job,k.GetCurrentProcess()),c.get_last_error()
launch([sys.executable,sys.argv[2]])
k.TerminateJobObject(job,77)
''', encoding='utf-8')
            # Windows supports nested jobs. Keep the test parent in the host's
            # job; only the real launcher must let its child survive teardown.
            # Hosted CI explicitly denies CREATE_BREAKAWAY_FROM_JOB.
            result = subprocess.run([sys.executable, str(parent), str(SCRIPTS), str(child)],
                                    creationflags=subprocess.CREATE_NO_WINDOW,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 77, result.stderr.decode(errors='replace'))
            deadline = time.monotonic()+8
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(output.exists(), 'Child was killed with the launcher job')
            self.assertFalse(json.loads(output.read_text())['flags'] & 0x2000,
                             output.read_text())


if __name__ == '__main__':
    unittest.main()
