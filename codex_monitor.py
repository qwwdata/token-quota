"""Start the quota battery when the Codex desktop app starts (Windows)."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import time


def is_codex_desktop(name, path):
    """Do not mistake Codex CLI/app-server or the ChatGPT app for the desktop app."""
    name, path = name.lower(), path.lower().replace('/', '\\')
    if name not in ('chatgpt.exe', 'codex.exe'):
        return False
    return any(part in path for part in (
        '\\openai.codex_', '\\programs\\codex\\', '\\openai\\codex\\app\\',
    ))


class SessionTracker:
    def __init__(self):
        self.session = ()
        self.owns_widget = False

    def update(self, roots, has_widget):
        roots = tuple(sorted(roots))
        if roots == self.session:
            return None  # Respect "Quit" until Codex starts a new session.
        self.session = roots
        if not roots:
            close = self.owns_widget and has_widget
            self.owns_widget = False
            return 'close' if close else None
        if not has_widget:
            self.owns_widget = True
            return 'launch'
        return None


class ProcessEntry(C.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD),
                ('heap', C.c_size_t), ('module', W.DWORD), ('threads', W.DWORD),
                ('parent', W.DWORD), ('priority', W.LONG), ('flags', W.DWORD),
                ('name', W.WCHAR * 260)]


class WindowsDesktop:
    def __init__(self):
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.user = C.WinDLL('user32', use_last_error=True)
        self.callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        self.kernel.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
        self.kernel.CreateToolhelp32Snapshot.restype = W.HANDLE
        for name in ('Process32FirstW', 'Process32NextW'):
            getattr(self.kernel, name).argtypes = [W.HANDLE, C.POINTER(ProcessEntry)]
        self.kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.kernel.OpenProcess.restype = W.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
        self.kernel.CloseHandle.argtypes = [W.HANDLE]
        self.kernel.CreateMutexW.argtypes = [C.c_void_p, W.BOOL, W.LPCWSTR]
        self.kernel.CreateMutexW.restype = W.HANDLE
        self.user.EnumWindows.argtypes = [self.callback, W.LPARAM]
        self.user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
        self.user.IsWindowVisible.argtypes = [W.HWND]
        self.user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]

    def codex_roots(self):
        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot in (None, C.c_void_p(-1).value):
            raise C.WinError(C.get_last_error())
        matching = {}
        try:
            entry = ProcessEntry(size=C.sizeof(ProcessEntry))
            more = self.kernel.Process32FirstW(snapshot, C.byref(entry))
            while more:
                if entry.name.lower() in ('chatgpt.exe', 'codex.exe'):
                    process = self.kernel.OpenProcess(0x1000, False, entry.pid)
                    if process:
                        try:
                            path = C.create_unicode_buffer(4096)
                            length = W.DWORD(len(path))
                            if self.kernel.QueryFullProcessImageNameW(process, 0, path, C.byref(length)):
                                if is_codex_desktop(entry.name, path.value):
                                    matching[entry.pid] = entry.parent
                        finally:
                            self.kernel.CloseHandle(process)
                more = self.kernel.Process32NextW(snapshot, C.byref(entry))
        finally:
            self.kernel.CloseHandle(snapshot)
        return tuple(sorted(pid for pid, parent in matching.items() if parent not in matching))

    def quota_window(self):
        found = []
        @self.callback
        def visit(hwnd, unused):
            title = C.create_unicode_buffer(100)
            self.user.GetWindowTextW(hwnd, title, len(title))
            if title.value == 'Token Quota' and self.user.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True
        self.user.EnumWindows(visit, 0)
        return found[0] if found else None


def main():
    desktop = WindowsDesktop()
    mutex = desktop.kernel.CreateMutexW(None, False, 'Local\\TokenQuotaCodexMonitor')
    if not mutex:
        raise C.WinError(C.get_last_error())
    if C.get_last_error() == 183:
        desktop.kernel.CloseHandle(mutex)
        return
    tracker = SessionTracker()
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    widget = Path(__file__).with_name('token_quota.py')
    log = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'TokenQuota' / 'monitor.log'
    try:
        while True:
            try:
                hwnd = desktop.quota_window()
                action = tracker.update(desktop.codex_roots(), bool(hwnd))
                if action == 'launch':
                    subprocess.Popen([str(pythonw), '-X', 'utf8', str(widget)],
                                     cwd=str(widget.parent), creationflags=subprocess.CREATE_NO_WINDOW)
                elif action == 'close':
                    desktop.user.PostMessageW(hwnd, 0x10, 0, 0)
            except (OSError, ValueError) as exc:
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text(f'{datetime.now().isoformat(timespec="seconds")} {type(exc).__name__}: {exc}\n', encoding='utf-8')
            time.sleep(2)
    finally:
        desktop.kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
