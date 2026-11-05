"""Run a development script in Calibre with disposable config and cache."""

import os
import shutil
import subprocess
import sys
import tempfile


def main():
    calibre = os.environ.get('CALIBRE_DEBUG_EXECUTABLE') or shutil.which('calibre-debug')
    if not calibre:
        raise SystemExit('calibre-debug must be on PATH')
    with tempfile.TemporaryDirectory(prefix='goodreads-cs-qa-') as root:
        env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=os.path.join(root, 'config'),
                   CALIBRE_CACHE_DIRECTORY=os.path.join(root, 'cache'),
                   QT_QPA_PLATFORM=os.environ.get('QT_QPA_PLATFORM', 'offscreen'))
        # Child QA jobs must use the selected runtime as well, rather than
        # silently using the installed Calibre from the original PATH.
        env['PATH'] = os.path.dirname(os.path.abspath(calibre)) + os.pathsep + env.get('PATH', '')
        return subprocess.call([calibre, '-e', sys.argv[1], '--'] + sys.argv[2:], env=env)


if __name__ == '__main__':
    raise SystemExit(main())
