"""Distribution for vroom."""
from distutils.core import setup
import os.path

with open(os.path.join(os.path.dirname(__file__), 'vroom/VERSION.txt')) as f:
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
)
