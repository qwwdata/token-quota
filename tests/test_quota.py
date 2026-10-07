import queue
import unittest

from battery import HEIGHT, WIDTH, render_battery
from quota_client import QuotaReader, extract_windows


class QuotaTests(unittest.TestCase):
    def test_remaining_and_actual_windows(self):
        payload = {'rateLimits': {'primary': {'windowDurationMins': 10080, 'usedPercent': 17},
                                 'secondary': {'windowDurationMins': 300, 'usedPercent': 18}}}
        self.assertEqual(extract_windows(payload)['five']['remaining'], 82)
        self.assertEqual(extract_windows(payload)['week']['remaining'], 83)

    def test_missing_is_not_zero(self):
        self.assertEqual(extract_windows({}), {})
        self.assertEqual(extract_windows({'rateLimits': {'primary': None}}), {})
        payload = {'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': 100}}}
        self.assertEqual(extract_windows(payload)['five']['remaining'], 0)

    def test_ignore_other_buckets(self):
        other = {'limitId': 'another_model', 'primary': {'windowDurationMins': 300, 'usedPercent': 1}}
        self.assertEqual(extract_windows({'rateLimits': other}), {})
        correct = {'primary': {'windowDurationMins': 300, 'usedPercent': 45}}
        self.assertEqual(extract_windows({'rateLimits': other, 'rateLimitsByLimitId': {'codex': correct}})['five']['remaining'], 55)

    def test_reject_invalid_numbers_and_unknown_window(self):
        for used in (None, True, '20', float('nan'), float('inf')):
            self.assertEqual(extract_windows({'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': used}}}), {})
        self.assertEqual(extract_windows({'rateLimits': {'primary': {'windowDurationMins': 60, 'usedPercent': 20}}}), {})

    def test_notification_keeps_other_window(self):
        updates = queue.Queue()
        reader = QuotaReader(updates)
        reader.publish({'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': 10},
                                      'secondary': {'windowDurationMins': 10080, 'usedPercent': 20}}})
        reader.notification({'method': 'account/rateLimits/updated', 'params': {
            'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': 30}}}})
        updates.get_nowait()
        _, windows, _ = updates.get_nowait()
        self.assertEqual(windows['five']['remaining'], 70)
        self.assertEqual(windows['week']['remaining'], 80)

    def test_full_read_removes_no_longer_available_window(self):
        reader = QuotaReader(queue.Queue())
        reader.windows = {'week': {'remaining': 50}}
        reader.publish({'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': 1}}})
        self.assertNotIn('week', reader.windows)


class BatteryTests(unittest.TestCase):
    def test_size_and_true_transparency(self):
        image = render_battery(75)
        self.assertEqual(image.size, (WIDTH, HEIGHT))
        self.assertEqual(image.mode, 'RGBA')
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertEqual(image.getpixel((63, 27))[3], 0)
        self.assertGreater(image.getpixel((10, 14))[3], 200)

    def test_empty_unknown_and_stale_are_distinct(self):
        empty = render_battery(0)
        unknown = render_battery(None)
        stale = render_battery(75, stale=True)
        self.assertNotEqual(empty.tobytes(), unknown.tobytes())
        self.assertNotEqual(stale.tobytes(), render_battery(75).tobytes())

    def test_low_quota_red(self):
        red, green, blue, _ = render_battery(15).getpixel((8, 14))
        self.assertGreater(red, green * 2)
        self.assertGreater(red, blue * 2)

    def test_light_and_dark_contrast(self):
        self.assertLess(render_battery(80, light=True).getpixel((10, 14))[0], 50)
        self.assertGreater(render_battery(80, light=False).getpixel((10, 14))[0], 200)


if __name__ == '__main__':
    unittest.main()
