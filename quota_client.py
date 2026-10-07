"""Read Codex quota metadata over app-server stdio, without starting a turn."""
from __future__ import annotations

import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import json


def find_cli() -> str:
    override = os.environ.get('CODEX_CLI')
    if override:
        if not Path(override).is_file():
            raise FileNotFoundError('CODEX_CLI 指向的文件不存在')
        return override
    cli = shutil.which('codex.exe')
    if cli:
        return cli
    root = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI/Codex/bin'
    binaries = list(root.glob('*/codex.exe'))
    if binaries:
        return str(max(binaries, key=lambda p: p.stat().st_mtime))
    cli = shutil.which('codex')
    if cli:
        return cli
    raise FileNotFoundError('未找到 Codex；安装桌面应用或 CLI，并用 ChatGPT 账号登录')


def extract_windows(payload: dict) -> dict:
    buckets = payload.get('rateLimitsByLimitId') or {}
    limits = buckets.get('codex') or payload.get('rateLimits') or {}
    if limits.get('limitId') not in (None, 'codex'):
        return {}
    result = {}
    for key in ('primary', 'secondary'):
        window = limits.get(key)
        if not isinstance(window, dict):
            continue
        mode = {300: 'five', 10080: 'week'}.get(window.get('windowDurationMins'))
        used = window.get('usedPercent')
        if mode and isinstance(used, (int, float)) and not isinstance(used, bool) and math.isfinite(used):
            reset = window.get('resetsAt')
            result[mode] = {'remaining': max(0.0, min(100.0, 100.0 - used)),
                            'reset': reset if isinstance(reset, (int, float)) and math.isfinite(reset) else None}
    return result


class QuotaReader(threading.Thread):
    """Consume quota notifications immediately, with 10-second polling fallback."""
    def __init__(self, updates: queue.Queue, interval: float = 10):
        super().__init__(daemon=True)
        self.updates = updates
        self.interval = max(5, interval)
        self.stop_event = threading.Event()
        self.refresh_event = threading.Event()
        self.messages = queue.Queue()
        self.proc = None
        self.sequence = 0
        self.windows = {}

    def publish(self, payload, partial=False):
        windows = extract_windows(payload)
        if partial:
            if not windows:
                return
            self.windows.update(windows)
        else:
            self.windows = windows
        self.updates.put(('ok', dict(self.windows), time.time()))

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()

    def notification(self, msg):
        if msg.get('method') == 'account/rateLimits/updated':
            self.publish(msg.get('params') or {}, partial=True)

    def receive(self, request_id):
        deadline = time.monotonic() + 15
        while not self.stop_event.is_set() and time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise OSError('Codex 额度连接已断开')
            try:
                msg = self.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            if msg.get('id') == request_id:
                if 'error' in msg:
                    raise OSError('读取失败，请检查 Codex 的 ChatGPT 登录状态及网络')
                return msg.get('result') or {}
            self.notification(msg)
        raise TimeoutError('额度读取超时')

    def connect(self):
        cli = find_cli()
        command = [cli, 'app-server', '--listen', 'stdio://']
        if Path(cli).suffix.lower() in ('.cmd', '.bat'):
            command = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', *command]
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.messages = queue.Queue()
        messages, stream = self.messages, self.proc.stdout

        def read():
            try:
                for line in stream:
                    try:
                        messages.put(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            except (OSError, ValueError):
                pass
        threading.Thread(target=read, daemon=True).start()
        self.send({'id': 0, 'method': 'initialize', 'params': {'clientInfo': {
            'name': 'token_quota', 'title': 'Token Quota', 'version': '1.0.0'}}})
        self.receive(0)
        self.send({'method': 'initialized', 'params': {}})

    def disconnect(self):
        proc, self.proc = self.proc, None
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            for stream in (proc.stdin, proc.stdout):
                if stream:
                    stream.close()

    def run(self):
        try:
            while not self.stop_event.is_set():
                self.refresh_event.clear()
                try:
                    if self.proc is None:
                        self.connect()
                    self.sequence += 1
                    self.send({'id': self.sequence, 'method': 'account/rateLimits/read'})
                    self.publish(self.receive(self.sequence))
                    deadline = time.monotonic() + self.interval
                    while not self.stop_event.is_set() and time.monotonic() < deadline:
                        if self.refresh_event.is_set():
                            break
                        if self.proc.poll() is not None:
                            raise OSError('Codex 额度连接已断开')
                        try:
                            self.notification(self.messages.get(timeout=0.2))
                        except queue.Empty:
                            pass
                except (OSError, TimeoutError, ValueError) as exc:
                    if not self.stop_event.is_set():
                        self.updates.put(('error', str(exc), time.time()))
                    self.disconnect()
                    for _ in range(50):
                        if self.stop_event.wait(0.2) or self.refresh_event.is_set():
                            break
        finally:
            self.disconnect()

    def close(self):
        self.stop_event.set()
        self.refresh_event.set()
        self.join(timeout=4)
