"""Regression tests for delayed and transient recurrence; no desktop input injected."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'release_keys', Path(__file__).resolve().parents[1] / 'scripts/release_keys.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CTRL = {'keycode': 105, 'name': 'Control_R'}


class ObservationTests(unittest.TestCase):
    def observe(self, states, initial=None):
        now = [0.0]
        samples = iter(states)
        def sleep(seconds):
            now[0] += seconds
        return module.observe(lambda: next(samples), initial or [], 0.6,
                              clock=lambda: now[0], sleep=sleep)

    def test_stays_clear(self):
        self.assertEqual(self.observe([[], [], []]), ([], [], []))

    def test_delayed_recurrence(self):
        after, seen, changes = self.observe([[], [], [CTRL]])
        self.assertEqual(after, [CTRL])
        self.assertEqual(seen, [CTRL])
        self.assertGreater(changes[0]['elapsed_seconds'], 0.2)

    def test_transient_recurrence_remains_reported(self):
        after, seen, changes = self.observe([[], [CTRL], []])
        self.assertEqual(after, [])
        self.assertEqual(seen, [CTRL])
        self.assertEqual(len(changes), 2)

    def test_immediate_failure_remains_reported(self):
        after, seen, _ = self.observe([[], [], []], [CTRL])
        self.assertEqual(after, [])
        self.assertEqual(seen, [CTRL])


if __name__ == '__main__':
    unittest.main()
