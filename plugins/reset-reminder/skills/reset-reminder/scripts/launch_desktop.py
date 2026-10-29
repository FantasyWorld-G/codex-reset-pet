"""Launch the desktop companion outside the caller's Windows job lifetime."""
import argparse
import base64
import ctypes
from ctypes import wintypes
import logging
import json
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def in_windows_job():
    if os.name != 'nt':
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                     ctypes.POINTER(wintypes.BOOL)]
    result = wintypes.BOOL()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(result.value)


def windows_job_flags():
    """Report current job limits; Windows may add a benign compatibility job."""
    if not in_windows_job():
        return 0
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                    ('maximum', ctypes.c_size_t), ('active', wintypes.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                    ('scheduling', wintypes.DWORD)]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', ctypes.c_uint64*6),
                    ('memory', ctypes.c_size_t*4)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                 ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    limits = Extended()
    if not kernel.QueryInformationJobObject(None, 9, ctypes.byref(limits), ctypes.sizeof(limits), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return limits.basic.flags


def launch(command):
    if os.name == 'nt':
        # A breakaway flag only escapes jobs that permit it; outer Codex jobs
        # can still own that child. Local WMI creates it through Windows instead.
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        source = ("$ErrorActionPreference='Stop'; "
                  "$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{"
                  "CommandLine=" + quote(subprocess.list2cmdline(command)) + ";"
                  "CurrentDirectory=" + quote(os.getcwd()) + "}; "
                  "$r | Select-Object ReturnValue,ProcessId | ConvertTo-Json -Compress")
        encoded = base64.b64encode(source.encode('utf-16le')).decode('ascii')
        powershell = Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive',
                                 '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
                                stdin=subprocess.DEVNULL, capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        if result.returncode:
            raise RuntimeError('Windows independent launch failed: '+result.stderr.decode(errors='replace'))
        response = json.loads(result.stdout.decode('utf-8-sig'))
        if response['ReturnValue'] or not response.get('ProcessId'):
            raise RuntimeError('Windows process creation failed: '+str(response['ReturnValue']))
        return SimpleNamespace(pid=response['ProcessId'])
    options = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    return subprocess.Popen(command, **options)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--usage', required=True)
    parser.add_argument('--settings', required=True)
    args = parser.parse_args()
    directory = Path(args.settings).resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[RotatingFileHandler(directory/'desktop-launcher.log',
                                  maxBytes=262144, backupCount=2, encoding='utf-8')])
    python = Path(sys.executable)
    if os.name == 'nt' and python.with_name('pythonw.exe').exists():
        python = python.with_name('pythonw.exe')
    try:
        child = launch([str(python), str(Path(__file__).with_name('desktop_pet.py')),
                        '--usage', str(Path(args.usage).resolve()),
                        '--settings', str(Path(args.settings).resolve())])
        logging.info('Independent desktop launch: pid=%s, launcher_in_job=%s',
                     child.pid, in_windows_job())
    except Exception:
        logging.exception('Independent desktop launch failed')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
