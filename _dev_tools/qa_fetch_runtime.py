"""Isolated Calibre runtime checks; never run against the user's config/library."""

import argparse
import json
import os
import sys
import time
import types
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def bootstrap():
    if not os.environ.get('CALIBRE_CONFIG_DIRECTORY'):
        raise SystemExit('Use run_calibre_check.py or supply a disposable CALIBRE_CONFIG_DIRECTORY.')
    sys.modules.setdefault('calibre_plugins', types.ModuleType('calibre_plugins'))
    package = types.ModuleType('calibre_plugins.Goodreads_character_and_settings')
    package.__path__ = [str(ROOT)]
    sys.modules[package.__name__] = package


def event(**data):
    print(json.dumps(data), flush=True)


def gui_check():
    from unittest.mock import patch
    from qt.core import QApplication, QProgressBar

    # Install only into the disposable profile so actual arbitrary_n workers can
    # resolve the plugin, just as they do after a normal Calibre installation.
    with tempfile.TemporaryDirectory(prefix='goodreads-cs-package-') as temporary:
        package = Path(temporary) / 'Goodreads-character-and-settings.zip'
        runtime = list(ROOT.glob('*.py')) + list(ROOT.glob('plugin-import-name-*.txt'))
        for folder in ('resources', 'images', 'translations'):
            runtime.extend(path for path in (ROOT / folder).rglob('*') if path.is_file())
        with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in runtime:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(package) as archive:
            assert 'fetch_policy.py' in archive.namelist()
            assert not any(name.startswith(('_dev_tools/', '_docs/')) for name in archive.namelist())
        subprocess.run([shutil.which('calibre-customize'), '-a', str(package)], check=True)

    from calibre.gui2 import Dispatcher
    from calibre.gui2.ui import JobManager
    from calibre_plugins.Goodreads_character_and_settings import main as plugin_main
    from calibre_plugins.Goodreads_character_and_settings.fetch_policy import RequestCoordinator

    app = QApplication.instance() or QApplication([])
    manager = JobManager()
    progress = QProgressBar()
    progress.setRange(0, 1000)
    completed = []
    messages = []
    progress_values = []
    runner = plugin_main.GoodreadsPreviewRunner(types.SimpleNamespace())
    runner.show_status = lambda message, **kwargs: messages.append(message)

    def wait_until(condition, timeout=30):
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() >= deadline:
                raise AssertionError('Timed out waiting for Calibre job')
            app.processEvents()
            manager.update()
            time.sleep(0.05)

    def submit(books, options):
        runner.pending_jobs = 1
        runner.completed_jobs = 0
        runner.failure_details = []
        def done(job):
            runner.batch_job_finished(job)
            completed.append(job)
        job = manager.run_job(Dispatcher(done), 'arbitrary_n', args=[
            'calibre_plugins.Goodreads_character_and_settings.worker_process',
            'process_goodreads_batch', (books, options),
        ], description='Isolated Goodreads fetch QA')
        runner.active_jobs[job] = len(books)
        return job

    try:
        with patch.object(plugin_main.QMessageBox, 'warning', side_effect=lambda *args: messages.append(args[-1])):
            job = submit([{'book_id': 1, 'goodreads_id': '34', 'title': 'First QA book'},
                          {'book_id': 2, 'goodreads_id': '35', 'title': 'Second QA book'}],
                         {'debug_simulated_error': 'missing_book_data'})
            notifications = job.notifications
            recorded = []

            class ObservedQueue(object):
                def put(self, value, *args, **kwargs):
                    recorded.append(value)
                    return notifications.put(value, *args, **kwargs)
                def __getattr__(self, name):
                    return getattr(notifications, name)

            job.notifications = ObservedQueue()
            wait_until(lambda: job in completed)
            assert not job.failed, job.details
            assert len(job.result) == 2 and all(result['error'] and not result['field_updates'] for result in job.result)
            for fraction, title in recorded:
                progress.setValue(round(fraction * 1000))
                progress_values.append(progress.value())
            assert progress_values == [500, 1000], progress_values
            assert runner.failed_count == 2 and runner.updated_count == 0
            assert any('First QA book' in message and 'Second QA book' in message for message in messages)

            coordinator = RequestCoordinator()
            with coordinator._locked():
                state = coordinator._load()
                state['cooldown_until'] = time.time() + 120
                coordinator._save(state)
            cancelled = submit([{'book_id': 3, 'goodreads_id': '34', 'title': 'Cancel QA book'}], {})
            wait_until(lambda: cancelled.start_time is not None)
            # Let the worker enter its shared-cooldown wait, then use Calibre's
            # real cancellation path. The future deadline prevents HTTP access.
            start = time.monotonic()
            wait_until(lambda: time.monotonic() - start >= 2)
            manager.kill_job(cancelled, None)
            wait_until(lambda: cancelled in completed)
            assert cancelled.killed and cancelled.failed
            assert not cancelled.result
            with coordinator._locked():
                state = coordinator._load()
                assert state['last_start'] is None, 'Cancellation check unexpectedly sent a request'
                state['cooldown_until'] = 0
                coordinator._save(state)
            assert coordinator.run(lambda: 'recovered', interval_seconds=1) == 'recovered'
            event(event='gui', progress=progress_values, reported_book_failures=2,
                  cancelled=cancelled.killed, coordinator_recovered=True, library_opened=False,
                  test_package_contains_fetch_policy=True)
    finally:
        manager.server.close()
        manager.threaded_server.close()
        manager.timer.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('coordinate', 'gui', 'live'))
    parser.add_argument('--directory')
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--cooldown', type=float, default=0)
    parser.add_argument('--hold', type=float, default=0)
    args = parser.parse_args()
    bootstrap()
    from calibre_plugins.Goodreads_character_and_settings.fetch_policy import RequestCoordinator
    if args.mode == 'coordinate':
        coordinator = RequestCoordinator(directory=args.directory)

        def request():
            event(event='started', time=time.time(), pid=os.getpid())
            if args.hold:
                time.sleep(args.hold)
            if args.cooldown:
                error = RuntimeError('simulated service cooldown')
                error.cooldown_seconds = args.cooldown
                raise error
            return True

        try:
            coordinator.run(request, interval_seconds=args.interval)
        except RuntimeError as error:
            if not args.cooldown:
                raise
            event(event='cooldown', time=time.time())
        return
    if args.mode == 'gui':
        gui_check()
        return
    if args.mode == 'live':
        from calibre_plugins.Goodreads_character_and_settings import common, worker_process as worker
        coordinator = RequestCoordinator()
        for book_id, variant in (('34', 'plain'), ('34', 'xml'), ('230926478', 'xml')):
            page = worker.fetch_goodreads_page(book_id, variant=variant, coordinator=coordinator)
            valid = common.has_goodreads_book_data(page['html'], book_id)
            valid_url = common.goodreads_book_url_matches_id(page['final_url'], book_id)
            assert valid and valid_url, 'Live response failed book validation'
            characters = common.extract_goodreads_values(page['html'], 'Characters')
            settings = common.extract_goodreads_values(page['html'], 'Setting')
            event(event='live', url=page['requested_url'], final_url=page['final_url'],
                  http_status=200, usable_payload=valid, matching_url=valid_url,
                  characters=len(characters), settings=len(settings))


if __name__ == '__main__':
    main()
