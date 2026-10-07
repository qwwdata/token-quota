"""Windows layered battery widget. No rectangular background or title bar."""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import sys
import time
import winreg

from battery import HEIGHT, WIDTH, render_battery
from quota_client import QuotaReader

if sys.platform != 'win32':
    raise SystemExit('Token Quota 的悬浮窗口目前仅支持 Windows。')

user = C.WinDLL('user32', use_last_error=True)
gdi = C.WinDLL('gdi32', use_last_error=True)
kernel = C.WinDLL('kernel32', use_last_error=True)
LRESULT = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)


class WindowClass(C.Structure):
    _fields_ = [('size', W.UINT), ('style', W.UINT), ('procedure', WNDPROC),
                ('class_extra', C.c_int), ('window_extra', C.c_int), ('instance', W.HINSTANCE),
                ('icon', W.HICON), ('cursor', W.HANDLE), ('background', W.HBRUSH),
                ('menu', W.LPCWSTR), ('name', W.LPCWSTR), ('small_icon', W.HICON)]


class BitmapHeader(C.Structure):
    _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG),
                ('planes', W.WORD), ('bit_count', W.WORD), ('compression', W.DWORD),
                ('image_size', W.DWORD), ('x_ppm', W.LONG), ('y_ppm', W.LONG),
                ('colors_used', W.DWORD), ('colors_important', W.DWORD)]


class Blend(C.Structure):
    _fields_ = [('operation', W.BYTE), ('flags', W.BYTE), ('alpha', W.BYTE), ('format', W.BYTE)]


def bind(lib, name, restype, *argtypes):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = restype, list(argtypes)
    return fn


bind(user, 'RegisterClassExW', W.WORD, C.POINTER(WindowClass))
bind(user, 'CreateWindowExW', W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
     C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p)
bind(user, 'DefWindowProcW', LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
bind(user, 'GetMessageW', W.BOOL, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
bind(user, 'TranslateMessage', W.BOOL, C.POINTER(W.MSG))
bind(user, 'DispatchMessageW', LRESULT, C.POINTER(W.MSG))
bind(user, 'PostMessageW', W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
bind(user, 'SendMessageW', LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
bind(user, 'GetWindowRect', W.BOOL, W.HWND, C.POINTER(W.RECT))
bind(user, 'ShowWindow', W.BOOL, W.HWND, C.c_int)
bind(user, 'DestroyWindow', W.BOOL, W.HWND)
bind(user, 'SetForegroundWindow', W.BOOL, W.HWND)
bind(user, 'SetTimer', C.c_size_t, W.HWND, C.c_size_t, W.UINT, C.c_void_p)
bind(user, 'KillTimer', W.BOOL, W.HWND, C.c_size_t)
bind(user, 'GetDC', W.HDC, W.HWND)
bind(user, 'ReleaseDC', C.c_int, W.HWND, W.HDC)
bind(user, 'CreatePopupMenu', W.HMENU)
bind(user, 'AppendMenuW', W.BOOL, W.HMENU, W.UINT, C.c_size_t, W.LPCWSTR)
bind(user, 'DestroyMenu', W.BOOL, W.HMENU)
bind(user, 'TrackPopupMenu', W.UINT, W.HMENU, W.UINT, C.c_int, C.c_int, C.c_int, W.HWND, C.c_void_p)
bind(user, 'GetCursorPos', W.BOOL, C.POINTER(W.POINT))
bind(user, 'LoadCursorW', W.HANDLE, W.HINSTANCE, C.c_void_p)
bind(user, 'MessageBoxW', C.c_int, W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT)
bind(user, 'UpdateLayeredWindow', W.BOOL, W.HWND, W.HDC, C.POINTER(W.POINT),
     C.POINTER(W.SIZE), W.HDC, C.POINTER(W.POINT), W.DWORD, C.POINTER(Blend), W.DWORD)
bind(gdi, 'CreateCompatibleDC', W.HDC, W.HDC)
bind(gdi, 'CreateDIBSection', W.HBITMAP, W.HDC, C.c_void_p, W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD)
bind(gdi, 'SelectObject', W.HANDLE, W.HDC, W.HANDLE)
bind(gdi, 'DeleteObject', W.BOOL, W.HANDLE)
bind(gdi, 'DeleteDC', W.BOOL, W.HDC)
bind(kernel, 'GetModuleHandleW', W.HMODULE, W.LPCWSTR)
bind(kernel, 'CreateMutexW', W.HANDLE, C.c_void_p, W.BOOL, W.LPCWSTR)
bind(kernel, 'CloseHandle', W.BOOL, W.HANDLE)

CONFIG = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'TokenQuota' / 'position.json'


def light_theme():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return bool(winreg.QueryValueEx(key, 'AppsUseLightTheme')[0])
    except OSError:
        return False


class QuotaWidget:
    def __init__(self, mode='five', interval=10, config=CONFIG):
        self.config = config
        self.mode = mode  # Every ordinary launch starts with the five-hour window.
        self.light = light_theme()
        self.windows = {}
        self.updated = None
        self.error = None
        self.paint_state = None
        self.updates = queue.Queue()
        self.reader = QuotaReader(self.updates, interval=interval)
        self.instance = kernel.GetModuleHandleW(None)
        self.callback = WNDPROC(self.procedure)
        klass = WindowClass()
        klass.size, klass.instance = C.sizeof(klass), self.instance
        klass.procedure, klass.name = self.callback, 'TokenQuotaBattery'
        klass.cursor = user.LoadCursorW(None, C.c_void_p(32649))
        if not user.RegisterClassExW(C.byref(klass)):
            raise C.WinError(C.get_last_error())
        x, y = self.position()
        # WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW; WS_POPUP.
        self.hwnd = user.CreateWindowExW(0x80000 | 0x8 | 0x80, klass.name, 'Token Quota',
                                         0x80000000, x, y, WIDTH, HEIGHT, None, None, self.instance, None)
        if not self.hwnd:
            raise C.WinError(C.get_last_error())
        self.render()
        user.ShowWindow(self.hwnd, 4)  # Show without taking keyboard focus.
        user.SetTimer(self.hwnd, 1, 200, None)
        self.reader.start()

    def position(self):
        vx, vy, vw, vh = [user.GetSystemMetrics(i) for i in (76, 77, 78, 79)]
        x, y = user.GetSystemMetrics(0) - WIDTH - 40, user.GetSystemMetrics(1) - HEIGHT - 100
        try:
            data = json.loads(self.config.read_text(encoding='utf-8'))
            x, y = int(data['x']), int(data['y'])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return max(vx, min(x, vx + vw - WIDTH)), max(vy, min(y, vy + vh - HEIGHT))

    def save_position(self):
        rect = W.RECT()
        user.GetWindowRect(self.hwnd, C.byref(rect))
        try:
            self.config.parent.mkdir(parents=True, exist_ok=True)
            temp = self.config.with_suffix('.tmp')
            temp.write_text(json.dumps({'x': rect.left, 'y': rect.top}), encoding='utf-8')
            temp.replace(self.config)
        except OSError:
            pass

    def select(self, mode):
        self.mode = mode
        self.render()

    def current_image(self):
        value = self.windows.get(self.mode)
        stale = self.error is not None or (self.updated is not None and time.time() - self.updated > 30)
        return render_battery(value['remaining'] if value else None, stale, light=self.light)

    def render(self):
        value = self.windows.get(self.mode)
        stale = self.error is not None or (self.updated is not None and time.time() - self.updated > 30)
        state = (self.mode, value['remaining'] if value else None, stale, self.light)
        if state == self.paint_state:
            return
        image = self.current_image()
        # UpdateLayeredWindow requires premultiplied BGRA, not straight RGBA.
        rgba = image.tobytes()
        pixels = bytearray(len(rgba))
        for i in range(0, len(rgba), 4):
            red, green, blue, alpha = rgba[i:i+4]
            pixels[i:i+4] = bytes((blue * alpha // 255, green * alpha // 255, red * alpha // 255, alpha))
        screen = user.GetDC(None)
        memory = gdi.CreateCompatibleDC(screen)
        header = BitmapHeader(size=C.sizeof(BitmapHeader), width=WIDTH, height=-HEIGHT,
                              planes=1, bit_count=32, compression=0)
        bits = C.c_void_p()
        bitmap = gdi.CreateDIBSection(screen, C.byref(header), 0, C.byref(bits), None, 0)
        if not bitmap or not bits.value:
            gdi.DeleteDC(memory)
            user.ReleaseDC(None, screen)
            raise C.WinError(C.get_last_error())
        old = gdi.SelectObject(memory, bitmap)
        try:
            C.memmove(bits, bytes(pixels), len(pixels))
            size, source, blend = W.SIZE(WIDTH, HEIGHT), W.POINT(0, 0), Blend(0, 0, 255, 1)
            if not user.UpdateLayeredWindow(self.hwnd, screen, None, C.byref(size), memory,
                                            C.byref(source), 0, C.byref(blend), 2):
                raise C.WinError(C.get_last_error())
            self.paint_state = state
        finally:
            gdi.SelectObject(memory, old)
            gdi.DeleteObject(bitmap)
            gdi.DeleteDC(memory)
            user.ReleaseDC(None, screen)

    def drain(self):
        while True:
            try:
                kind, value, timestamp = self.updates.get_nowait()
            except queue.Empty:
                break
            if kind == 'ok':
                self.windows, self.updated, self.error = value, timestamp, None
            else:
                self.error = value
        self.render()

    def popup(self):
        menu = user.CreatePopupMenu()
        try:
            for command, mode, label in ((101, 'five', '5 小时'), (102, 'week', '每周')):
                value = self.windows.get(mode)
                text = f'{label} · 剩余 {value["remaining"]:.0f}%' if value else f'{label} · 暂不可用'
                user.AppendMenuW(menu, 0x8 if mode == self.mode else 0, command, text)
            user.AppendMenuW(menu, 0x800, 0, None)
            value = self.windows.get(self.mode)
            if value and value.get('reset'):
                try:
                    reset = datetime.fromtimestamp(value['reset']).strftime('%m/%d %H:%M')
                    user.AppendMenuW(menu, 0x2, 0, f'重置 {reset}（本机时区）')
                except (ValueError, OSError, OverflowError):
                    pass
            if self.error:
                status = '连接异常 · 电池灰色为上次数据' if value else '连接异常 · 尚无数据'
            elif self.updated is None:
                status = '正在连接 Codex…'
            else:
                status = '更新 ' + datetime.fromtimestamp(self.updated).strftime('%H:%M:%S')
            user.AppendMenuW(menu, 0x2, 0, status)
            user.AppendMenuW(menu, 0, 103, '立即刷新')
            user.AppendMenuW(menu, 0, 104, '退出')
            point = W.POINT()
            user.GetCursorPos(C.byref(point))
            user.SetForegroundWindow(self.hwnd)
            command = user.TrackPopupMenu(menu, 0x100 | 0x2, point.x, point.y, 0, self.hwnd, None)
            user.PostMessageW(self.hwnd, 0, 0, 0)
            if command in (101, 102):
                self.select('five' if command == 101 else 'week')
            elif command == 103:
                self.reader.refresh_event.set()
            elif command == 104:
                user.PostMessageW(self.hwnd, 0x10, 0, 0)
        finally:
            user.DestroyMenu(menu)

    def procedure(self, hwnd, message, wparam, lparam):
        # Never let Python exceptions escape across a Windows callback boundary.
        try:
            if message == 0x201:  # WM_LBUTTONDOWN: native window dragging.
                user.ReleaseCapture()
                user.SendMessageW(hwnd, 0xA1, 2, 0)
                return 0
            if message == 0x232:  # WM_EXITSIZEMOVE
                self.save_position()
                return 0
            if message == 0x205:  # WM_RBUTTONUP
                self.popup()
                return 0
            if message == 0x113:  # WM_TIMER
                self.drain()
                return 0
            if message == 0x1A:  # WM_SETTINGCHANGE: follow the Windows light/dark theme.
                self.light = light_theme()
                self.render()
                return 0
            if message == 0x10:  # WM_CLOSE
                self.save_position()
                user.DestroyWindow(hwnd)
                return 0
            if message == 0x2:  # WM_DESTROY
                user.KillTimer(hwnd, 1)
                user.PostQuitMessage(0)
                return 0
        except Exception:
            self.error = '窗口更新异常，请重新启动'
        return user.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self):
        message = W.MSG()
        try:
            while True:
                result = user.GetMessageW(C.byref(message), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    raise C.WinError(C.get_last_error())
                user.TranslateMessage(C.byref(message))
                user.DispatchMessageW(C.byref(message))
        finally:
            self.reader.close()


def main():
    parser = argparse.ArgumentParser(description='透明的 Codex 额度电池条（Windows）')
    parser.add_argument('--mode', choices=['five', 'week'], default='five')
    parser.add_argument('--interval', type=float, default=10, help='轮询秒数，最小 5 秒')
    args = parser.parse_args()
    user.SetProcessDPIAware()
    mutex = kernel.CreateMutexW(None, False, 'Local\\TokenQuotaBattery')
    if not mutex:
        raise C.WinError(C.get_last_error())
    try:
        if C.get_last_error() == 183:
            return
        QuotaWidget(args.mode, args.interval).run()
    finally:
        kernel.CloseHandle(mutex)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        user.MessageBoxW(None, str(exc), 'Token Quota 启动失败', 0x10)
        raise SystemExit(1)
