"""Request timing shared by this plugin's workers in one Calibre profile.

The stable lock file is separate from the atomically replaced state file.
Reserve the start before opening a socket, and hold the lock through the HTTP
attempt so a challenge cooldown is visible before another worker can request.
"""

__license__ = 'GPL v3'
__copyright__ = '2026, GrayTechGH'

import errno
import hashlib
import json
import math
import os
import random
import tempfile
import time
from contextlib import contextmanager
from email.utils import parsedate_to_datetime


class FetchCoordinationError(RuntimeError):
    pass


def parse_retry_after(value, now=None):
    value = str(value or '').strip()
    if not value:
        return 0.0
    try:
        if value.isascii() and value.isdigit():
            delay = float(value)
        else:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return 0.0
            delay = date.timestamp() - (time.time() if now is None else now)
        return max(0.0, delay) if math.isfinite(delay) else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


def retry_delay(retry_number, base=2, jitter=None):
    jitter = random.random() if jitter is None else jitter
    exponent = min(30, max(0, retry_number - 1))
    backoff = min(60.0, max(0.0, float(base)) * 2 ** exponent)
    return backoff + min(1.0, max(0.0, jitter))


def coordinator_directory():
    from calibre.constants import cache_dir, config_dir
    profile = os.path.normcase(os.path.realpath(config_dir))
    key = hashlib.sha256(profile.encode('utf-8')).hexdigest()
    return os.path.join(cache_dir(), 'goodreads-character-and-settings', key)


def _lock_contended(error):
    if os.name == 'nt':
        return getattr(error, 'winerror', None) in (32, 33)
    # A denied open has a filename; flock contention does not. Do not turn a
    # persistent directory/file permission error into an endless lock wait.
    if error.errno == errno.EACCES:
        return error.filename is None
    return error.errno in (errno.EAGAIN, errno.EINTR, errno.ENOLCK)


class RequestCoordinator(object):

    def __init__(self, directory=None, clock=None, sleep=None, lock_factory=None, log=None):
        self.directory = directory if directory is not None else coordinator_directory()
        self.clock = clock or time.time
        self.sleep = sleep or time.sleep
        if lock_factory is None:
            from calibre.utils.lock import ExclusiveFile
            lock_factory = ExclusiveFile
        self.lock_factory = lock_factory
        self.log = log or (lambda message: print('Goodreads fetch: ' + message, flush=True))
        self.state_path = os.path.join(self.directory, 'fetch-state.json')

    @contextmanager
    def _locked(self):
        try:
            os.makedirs(self.directory, exist_ok=True)
            waiting = False
            while True:
                lock = self.lock_factory(os.path.join(self.directory, 'fetch.lock'), timeout=1, sleep_time=0.1)
                try:
                    lock.__enter__()
                    break
                except OSError as error:
                    if not _lock_contended(error):
                        raise
                    if not waiting:
                        self.log('waiting for another worker')
                        waiting = True
                    self.sleep(0.1)
        except OSError as error:
            raise FetchCoordinationError('Cannot lock the Goodreads request coordinator: {}'.format(error)) from error
        try:
            yield
        finally:
            lock.__exit__(None, None, None)

    def _load(self):
        try:
            with open(self.state_path, 'r', encoding='utf-8') as source:
                state = json.load(source)
        except FileNotFoundError:
            return {'version': 1, 'last_start': None, 'interval': 0.0, 'cooldown_until': 0.0}
        except (OSError, ValueError) as error:
            raise FetchCoordinationError('Cannot read Goodreads request timing: {}'.format(error)) from error
        if not isinstance(state, dict) or type(state.get('version')) is not int or state['version'] != 1:
            raise FetchCoordinationError('Invalid Goodreads request timing state (unsupported version).')
        for key in ('last_start', 'interval', 'cooldown_until'):
            value = state.get(key)
            if key == 'last_start' and key in state and value is None:
                continue
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise FetchCoordinationError('Invalid Goodreads request timing state ({}).'.format(key))
        return state

    def _save(self, state):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory, delete=False) as target:
                temporary = target.name
                json.dump(state, target, allow_nan=False)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.state_path)
        except (OSError, ValueError) as error:
            raise FetchCoordinationError('Cannot save Goodreads request timing: {}'.format(error)) from error
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    def run(self, operation, interval_seconds=30, not_before=0):
        interval = max(1.0, float(interval_seconds))
        logged_deadline = 0
        while True:
            with self._locked():
                state = self._load()
                now = self.clock()
                deadline = max(not_before, state['cooldown_until'])
                if state['last_start'] is not None:
                    deadline = max(deadline, state['last_start'] + max(interval, state['interval']))
                delay = deadline - now
                if delay <= 0:
                    state.update(last_start=now, interval=interval)
                    self._save(state)
                    try:
                        return operation()
                    except Exception as error:
                        cooldown = getattr(error, 'cooldown_seconds', 0)
                        if cooldown > 0:
                            state['cooldown_until'] = max(state['cooldown_until'], self.clock() + cooldown)
                            self._save(state)
                        raise
            if deadline > logged_deadline + 0.5:
                self.log('waiting {:.1f}s for pacing/backoff/cooldown'.format(delay))
                logged_deadline = deadline
            self.sleep(min(1.0, delay))
