"""Distribution for vroom."""
import codecs
from distutils.core import setup
import os.path
import sys


# Don't even try to run under python 2 or earlier. It will seem to work but fail
# in corner cases with strange encoding errors.
if sys.version_info[0] < 3:
  sys.exit('ERROR: Python < 3 is unsupported.')


version_path = os.path.join(os.path.dirname(__file__), 'vroom/VERSION.txt')
with codecs.open(version_path, 'r', 'utf-8') as f:
  version = f.read().strip()

setup(
    name='vroom',
    version=version,
    description='Launch your vimscript tests',
    author='Nate Soares',
    author_email='nate@so8r.es',
    url='https://github.com/google/vroom',
    packages=['vroom'],
    scripts=[
        'scripts/shell.vroomfaker',
        'scripts/respond.vroomfaker',
        'scripts/vroom',
    ],
    package_data={'vroom': ['VERSION.txt']},
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
)
