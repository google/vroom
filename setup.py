"""Distribution for vroom."""
from distutils.core import setup

setup(
    name='vroom',
    version='0.10.0',
    description='Launch your vimscript tests',
    author='Nate Soares',
    author_email='nate@so8r.es',
    packages=['vroom'],
    scripts=[
        'scripts/shell.vroomfaker',
        'scripts/respond.vroomfaker',
        'scripts/vroom',
    ])
