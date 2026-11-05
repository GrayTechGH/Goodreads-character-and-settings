import json
import errno
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import nullcontext
from email.utils import formatdate
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import fetch_policy as policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.now = 1000.0
        self.logs = []
        self.coordinator = policy.RequestCoordinator(
            self.temporary.name, clock=lambda: self.now, sleep=self.advance,
            lock_factory=lambda *args, **kwargs: nullcontext(), log=self.logs.append,
        )

    def advance(self, seconds):
        self.now += seconds

    def test_retry_after_seconds_dates_invalid_and_past_values(self):
        for value, expected in [('120', 120), (formatdate(1120, usegmt=True), 120),
                                (formatdate(900, usegmt=True), 0), ('-1', 0), ('1.5', 0),
                                ('NaN', 0), ('not a date', 0), ('9' * 400, 0), ('', 0)]:
            with self.subTest(value=value):
                self.assertEqual(expected, policy.parse_retry_after(value, now=1000))

    def test_backoff_cap_and_jitter_are_bounded(self):
        self.assertEqual([2, 4, 8, 16, 32, 60, 60], [policy.retry_delay(n, jitter=0) for n in range(1, 8)])
        self.assertEqual(61, policy.retry_delay(10000, jitter=1))
        self.assertEqual(2, policy.retry_delay(1, jitter=-1))
        self.assertEqual(3, policy.retry_delay(1, jitter=100))

    def test_permission_errors_are_not_mistaken_for_lock_contention(self):
        denied = PermissionError(errno.EACCES, 'permission denied', '/cache/fetch.lock')
        contended = OSError(errno.EACCES, 'temporarily locked')
        with patch.object(policy.os, 'name', 'posix'):
            self.assertFalse(policy._lock_contended(denied))
            self.assertTrue(policy._lock_contended(contended))
        with patch.object(policy.os, 'name', 'nt'):
            self.assertFalse(policy._lock_contended(denied))
            contended.winerror = 32
            self.assertTrue(policy._lock_contended(contended))

    def test_previous_and_current_intervals_and_local_backoff(self):
        starts = []
        self.coordinator.run(lambda: starts.append(self.now), interval_seconds=30)
        self.coordinator.run(lambda: starts.append(self.now), interval_seconds=1)
        self.coordinator.run(lambda: starts.append(self.now), interval_seconds=40)
        self.coordinator.run(lambda: starts.append(self.now), interval_seconds=1, not_before=1200)
        self.assertEqual([1000, 1030, 1070, 1200], starts)

    def test_new_coordinator_observes_terminal_error_cooldown(self):
        def request():
            error = RuntimeError('challenge')
            error.cooldown_seconds = 60
            raise error
        with self.assertRaises(RuntimeError):
            self.coordinator.run(request, interval_seconds=1)
        other = policy.RequestCoordinator(self.temporary.name, clock=lambda: self.now, sleep=self.advance,
                                         lock_factory=lambda *a, **kw: nullcontext(), log=self.logs.append)
        other.run(lambda: self.assertEqual(1060, self.now), interval_seconds=1)

    def test_cooldown_is_rechecked_after_sleep(self):
        self.coordinator.run(lambda: None)
        extended = []
        def sleeper(seconds):
            self.advance(seconds)
            if not extended:
                state = self.coordinator._load()
                state['cooldown_until'] = 1100
                self.coordinator._save(state)
                extended.append(True)
        self.coordinator.sleep = sleeper
        self.coordinator.run(lambda: self.assertEqual(1100, self.now))

    def test_corrupt_or_unavailable_state_sends_no_request(self):
        for state in ('not json', 'null', '{}', '{"version":2}',
                      '{"version":1,"last_start":null,"interval":true,"cooldown_until":0}',
                      '{"version":1,"last_start":0,"interval":1,"cooldown_until":NaN}',
                      json.dumps({'version': 1, 'last_start': None, 'interval': 1, 'cooldown_until': 10 ** 400})):
            Path(self.coordinator.state_path).write_text(state, encoding='utf-8')
            with self.assertRaises(policy.FetchCoordinationError):
                self.coordinator.run(lambda: self.fail('must not send'))
        Path(self.coordinator.state_path).unlink()
        with patch.object(policy.os, 'replace', side_effect=PermissionError('read-only')):
            with self.assertRaises(policy.FetchCoordinationError):
                self.coordinator.run(lambda: self.fail('must not send'))
        self.assertEqual([], list(Path(self.temporary.name).glob('tmp*')))
        with patch.object(policy.os, 'makedirs', side_effect=PermissionError('read-only')):
            with self.assertRaises(policy.FetchCoordinationError):
                self.coordinator.run(lambda: self.fail('must not send'))

    def test_lock_release_on_request_and_storage_exceptions(self):
        released = []
        entered = []
        class Lock(object):
            def __enter__(self):
                entered.append(True)
            def __exit__(self, *args):
                released.append(True)
        self.coordinator.lock_factory = lambda *a, **kw: Lock()
        with self.assertRaises(ValueError):
            self.coordinator.run(lambda: (_ for _ in ()).throw(ValueError('programming error')))
        self.assertEqual([True], released)
        with patch.object(self.coordinator, '_save', side_effect=policy.FetchCoordinationError('disk full')):
            with self.assertRaises(policy.FetchCoordinationError):
                self.coordinator.run(lambda: self.fail('must not send'), not_before=0)
        self.assertEqual(len(entered), len(released))
        self.assertGreater(len(released), 1)

    def test_profile_paths_share_state_only_for_the_same_profile(self):
        import types
        constants = types.ModuleType('calibre.constants')
        constants.cache_dir = lambda: self.temporary.name
        constants.config_dir = os.path.join(self.temporary.name, 'profile1')
        with patch.dict(sys.modules, {'calibre.constants': constants}):
            first = policy.coordinator_directory()
            self.assertEqual(first, policy.coordinator_directory())
            constants.config_dir = os.path.join(self.temporary.name, 'profile2')
            self.assertNotEqual(first, policy.coordinator_directory())


@unittest.skipUnless(shutil.which('calibre-debug'), 'Requires the actual Calibre file lock')
class ProcessCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.children = []
        self.addCleanup(self.cleanup_children)

    def cleanup_children(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)

    def start(self, *extra):
        index = len(self.children)
        config = os.path.join(self.temporary.name, 'profile-{}'.format(index))
        env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=config, CALIBRE_CACHE_DIRECTORY=config)
        child = subprocess.Popen([shutil.which('calibre-debug'), '-e', str(ROOT / '_dev_tools' / 'qa_fetch_runtime.py'),
                                  '--', 'coordinate', '--directory', self.temporary.name, *extra],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        self.children.append(child)
        return child

    def finish(self, child):
        output, _ = child.communicate(timeout=20)
        self.assertEqual(0, child.returncode, output)
        return [json.loads(line) for line in output.splitlines() if line.startswith('{')]

    def test_parallel_processes_serialize_requests_with_shared_pacing(self):
        children = [self.start('--interval', '1') for _ in range(3)]
        events = [self.finish(child)[0] for child in children]
        starts = sorted(event['time'] for event in events)
        self.assertTrue(all(b - a >= 0.98 for a, b in zip(starts, starts[1:])), starts)

    def test_exception_shares_cooldown_and_releases_real_lock(self):
        first = self.finish(self.start('--cooldown', '2'))
        second = self.finish(self.start())
        self.assertGreaterEqual(second[0]['time'] - first[1]['time'], 1.98)

    def test_contention_longer_than_lock_timeout_waits_instead_of_failing(self):
        holder = self.start('--hold', '3')
        started = json.loads(holder.stdout.readline())
        follower = self.start()
        self.finish(holder)
        events = self.finish(follower)
        self.assertGreaterEqual(events[0]['time'] - started['time'], 2.98)

    def test_terminated_worker_releases_real_lock_and_keeps_reserved_start(self):
        child = self.start('--hold', '30')
        # Read the callback event: it proves the worker owns the lock and has reserved its start.
        line = child.stdout.readline()
        started = json.loads(line)
        child.kill()
        child.communicate(timeout=10)
        events = self.finish(self.start())
        self.assertGreaterEqual(events[0]['time'] - started['time'], 0.98)


if __name__ == '__main__':
    unittest.main()
