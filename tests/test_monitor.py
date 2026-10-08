import unittest
from codex_monitor import SessionTracker, is_codex_desktop


class MonitorTests(unittest.TestCase):
    def test_current_desktop_package(self):
        self.assertTrue(is_codex_desktop('ChatGPT.exe', r'C:\Program Files\WindowsApps\OpenAI.Codex_26.1002.0_x64__abc\app\ChatGPT.exe'))

    def test_exclude_cli_and_chatgpt_app(self):
        self.assertFalse(is_codex_desktop('codex.exe', r'C:\Users\user\AppData\Local\OpenAI\Codex\bin\hash\codex.exe'))
        self.assertFalse(is_codex_desktop('ChatGPT.exe', r'C:\Program Files\WindowsApps\OpenAI.ChatGPT_1.0\app\ChatGPT.exe'))

    def test_installer_desktop(self):
        self.assertTrue(is_codex_desktop('Codex.exe', r'C:\Users\user\AppData\Local\Programs\Codex\Codex.exe'))

    def test_launch_once_per_codex_session(self):
        tracker = SessionTracker()
        self.assertIsNone(tracker.update((), False))
        self.assertEqual(tracker.update((100,), False), 'launch')
        self.assertIsNone(tracker.update((100,), True))
        self.assertIsNone(tracker.update((100,), False))  # Manual Quit is respected.
        self.assertIsNone(tracker.update((), False))
        self.assertEqual(tracker.update((200,), False), 'launch')

    def test_close_only_managed_battery(self):
        tracker = SessionTracker()
        self.assertEqual(tracker.update((100,), False), 'launch')
        self.assertEqual(tracker.update((), True), 'close')
        self.assertIsNone(tracker.update((200,), True))
        self.assertIsNone(tracker.update((), True))  # Keep an independently opened battery.


if __name__ == '__main__':
    unittest.main()
