import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPT = Path(__file__).with_name('persistent_policy.py')


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'profile'
        self.home.mkdir()
        self.repo = self.root / 'repo'
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'add', 'origin',
                        'git@gitlab.x2robot.com:echo/memory_module.git'], check=True)

    def call(self, action, *, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), action, '--repo', str(self.repo),
                                 '--codex-home', str(self.home)], capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result.stdout

    def test_idempotence_preservation_backup_and_disable(self):
        path = self.home / 'AGENTS.md'
        original = '# Other project\nKeep these instructions.\n'
        path.write_text(original)
        self.call('enable')
        enabled = path.read_bytes()
        self.assertTrue(enabled.decode().startswith(original))
        self.call('enable')
        self.assertEqual(path.read_bytes(), enabled)
        backups = list((self.home / 'mapdb-autorelease-backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.assertTrue(self.call('status').startswith('enabled'))
        self.call('disable')
        self.assertTrue(path.read_text().startswith(original))
        self.assertNotIn('mapdb-session-autorelease:begin', path.read_text())
        self.assertTrue(self.call('status').startswith('disabled'))

    def test_override_is_effective_target(self):
        base = self.home / 'AGENTS.md'
        base.write_text('base instructions\n')
        override = self.home / 'AGENTS.override.md'
        override.write_text('temporary instructions\n')
        self.call('enable')
        self.assertEqual(base.read_text(), 'base instructions\n')
        self.assertIn('mapdb-session-autorelease:begin', override.read_text())
        self.call('disable')
        self.assertTrue(override.read_text().startswith('temporary instructions\n'))

    def test_unrelated_repo_cannot_enable(self):
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'set-url', 'origin',
                        'git@gitlab.x2robot.com:echo/other.git'], check=True)
        self.call('enable', ok=False)
        self.assertFalse((self.home / 'AGENTS.md').exists())

    def test_malformed_block_is_preserved(self):
        path = self.home / 'AGENTS.md'
        original = 'original\n<!-- mapdb-session-autorelease:begin -->\n'
        path.write_text(original)
        self.call('enable', ok=False)
        self.assertEqual(path.read_text(), original)

    def test_symlink_is_not_replaced(self):
        target = self.root / 'other.md'
        target.write_text('original')
        (self.home / 'AGENTS.md').symlink_to(target)
        self.call('enable', ok=False)
        self.assertEqual(target.read_text(), 'original')

    def test_https_remote_is_supported(self):
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'set-url', 'origin',
                        'https://gitlab.x2robot.com/echo/memory_module.git'], check=True)
        self.call('enable')
        self.assertTrue(self.call('status').startswith('enabled'))


if __name__ == '__main__':
    unittest.main()
