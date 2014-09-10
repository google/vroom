"""Vroom command line arguments."""
import argparse
from argparse import SUPPRESS
import glob
import itertools
import os.path
import sys

import vroom
import vroom.color
import vroom.messages
import vroom.shell


parser = argparse.ArgumentParser(
    description='Vroom: launch your tests.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--version', action='version',
    version='%(prog)s ' + vroom.__version__)


class DirectoryArg(argparse.Action):
  """An argparse action for a valid directory path."""

  def __call__(self, _, namespace, values, option_string=None):
    if not os.path.isdir(values):
      raise argparse.ArgumentTypeError('Invalid directory "%s"' % values)
    if not os.access(values, os.R_OK):
      raise argparse.ArgumentTypeError('Cannot read directory "%s"' % values)
    setattr(namespace, self.dest, values)


#
# Ways to run vroom.

parser.add_argument(
    'filename',
    nargs='*',
    default=SUPPRESS,
    help="""
The vroom file(s) to run.
""")

parser.add_argument(
    '--crawl',
    action=DirectoryArg,
    nargs='?',
    const='.',
    default=None,
    metavar='DIR',
    help="""
Crawl [DIR] looking for vroom files.
if [DIR] is not given, the current directory is crawled.
""")

parser.add_argument(
    '--skip',
    nargs='+',
    default=[],
    metavar='PATH',
    help="""
Ignore PATH when using --crawl.
PATH may refer to a test or a directory containing tests.
PATH must be relative to the --crawl directory.
""")

management_group = parser.add_argument_group(
    'management',
    'Manage other running vroom processes')
management_group.add_argument(
    '--murder',
    action='store_true',
    default=False,
    help="""
Kill a running vroom test.
This will kill the first vroom (beside the current process) found.
If you want to kill a specific vroom, find the process number and kill it
yourself.
""")


#
# Vim configuration

parser.add_argument(
    '-s',
    '--servername',
    default='VROOM',
    help="""
The vim servername (see :help clientserver).
Use this to help vroom differentiate between vims if you want to run multiple
vrooms at once.
""")

parser.add_argument(
    '-u',
    '--vimrc',
    default='NONE',
    help="""
vimrc file to use.
""")

parser.add_argument(
    '-i',
    '--interactive',
    action='store_true',
    help="""
Keeps vim open after a vroom failure, allowing you to inspect vim's state.
""")

parser.add_argument(
    '--neovim',
    action='store_true',
    help="""
Run Neovim instead of Vim
""")

#
# Timing

parser.add_argument(
    '-d',
    '--delay',
    type=float,
    # See Parse for the real default
    default=SUPPRESS,
    metavar='DELAY',
    help="""
Delay after each vim command (in seconds).
(default: 0.09 for Vim, 0.00 for Neovim)
""")

parser.add_argument(
    '--shell-delay',
    type=float,
    # See Parse for the real default
    default=SUPPRESS,
    metavar='SHELL_DELAY',
    help="""
Extra delay (in seconds) after a vim command that's expected to trigger a shell
command. (default: 0.25 for Vim, 0.00 for Neovim)
""")

parser.add_argument(
    '-t',
    '--startuptime',
    type=float,
    default=0.5,
    metavar='STARTUPTIME',
    help="""
How long to wait for vim to start (in seconds). This option is ignored for
Neovim.
""")

#
# Output configuration

parser.add_argument(
    '-o',
    '--out',
    default=sys.stdout,
    type=argparse.FileType('w'),
    metavar='FILE',
    help="""
Write test output to [FILE] instead of STDOUT.
Vroom output should never be redirected, as vim will want to control stdout for
the duration of the testing.
""")

parser.add_argument(
    '-v',
    '--verbose',
    action='store_true',
    help="""
Increase the amount of test output.
""")

parser.add_argument(
    '--nocolor',
    dest='color',
    action='store_const',
    const=vroom.color.Colorless,
    default=vroom.color.Colored,
    help="""
Turn off color in output.
""")

parser.add_argument(
    '--dump-messages',
    nargs='?',
    const=True,
    default=None,
    type=argparse.FileType('w'),
    metavar='FILE',
    help="""
Dump a log of vim messages received during execution.
See :help messages in vim.
Logs are written to [FILE], or to the same place as --out if [FILE] is omitted.
""")

parser.add_argument(
    '--dump-commands',
    nargs='?',
    const=True,
    default=None,
    type=argparse.FileType('w'),
    metavar='FILE',
    help="""
Dump a list of command sent to vim during execution.
Logs are written to [FILE], or to the same place as --out if [FILE] is omitted.
""")


parser.add_argument(
    '--dump-syscalls',
    nargs='?',
    const=True,
    default=None,
    type=argparse.FileType('w'),
    metavar='FILE',
    help="""
Dump vim system call logs to [FILE].
Logs are written to [FILE], or to the same place as --out if [FILE] is omitted.
""")


#
# Strictness configuration

parser.add_argument(
    '--message-strictness',
    choices=vroom.messages.STRICTNESS.Values(),
    default=vroom.messages.STRICTNESS.ERRORS,
    help="""
How to deal with unexpected messages.
When STRICT, unexpected messages will be treated as errors.
When RELAXED, unexpected messages will be ignored.
When GUESS-ERRORS (default), unexpected messages will be ignored unless vroom
things they look suspicious. Suspicious messages include things formatted like
vim errors like "E86: Buffer 3 does not exist" and messages that start with
ERROR.
""")

parser.add_argument(
    '--system-strictness',
    choices=vroom.shell.STRICTNESS.Values(),
    default=vroom.shell.STRICTNESS.STRICT,
    help="""
How to deal with unexpected system calls.
When STRICT (default), unexpected system calls will be treated as errors.
When RELAXED, unexpected system calls will be ignored.
""")


#
# Environment configuration

parser.add_argument(
    '--shell',
    default='shell.vroomfaker',
    help="""
The dummy shell executable (either a path or something on the $PATH).
Defaults to the right thing if you installed vroom normally.
""")

parser.add_argument(
    '--responder',
    default='respond.vroomfaker',
    help="""
The dummy responder executable (either a path or something on the $PATH).
Defaults to the right thing if you installed vroom normally.
""")


def Parse(args):
  """Parse the given arguments.

  Does a bit of magic to make sure that color isn't printed when output is being
  piped to a file.

  Does a bit more magic so you can use that --dump-messages and its ilk follow
  --out by default, instead of always going to stdout.

  Expands the filename arguments and complains if they don't point to any real
  files (unless vroom's doing something else).

  Args:
    args: The arguments to parse
  Returns:
    argparse.Namespace of the parsed args.
  Raises:
    ValueError: If the args are bad.
  """
  args = parser.parse_args(args)

  if args.out != sys.stdout:
    args.color = vroom.color.Colorless

  if not hasattr(args, 'delay'):
    # Default delay is 0.09 for Vim, 0 for Neovim
    args.delay = 0 if args.neovim else 0.09
  if not hasattr(args, 'shell_delay'):
    # Default shell delay is 0.25 for Vim, 0 for Neovim
    args.shell_delay = 0 if args.neovim else 0.25

  for dumper in ('dump_messages', 'dump_commands', 'dump_syscalls'):
    if getattr(args, dumper) is True:
      setattr(args, dumper, args.out)

  args.filenames = list(itertools.chain(
      Crawl(args.crawl, args.skip),
      *map(Expand, getattr(args, 'filename', []))))
  if not args.filenames and not args.murder:
    raise ValueError('Nothing to do.')
  if args.murder and args.filenames:
    raise ValueError(
        'You may birth tests and you may end them, but not both at once!')

  return args


def Close(args):
  """Cleans up an argument namespace, closing files etc.

  Args:
    args: The argparse.Namespace to close.
  """
  optfiles = [args.dump_messages, args.dump_commands, args.dump_syscalls]
  for optfile in filter(bool, optfiles):
    optfile.close()
  args.out.close()


def Expand(filename):
  """Expands a filename argument into a list of relevant filenames.

  Args:
    filename: The filename to expand.
  Raises:
    ValueError: When filename is non-existent.
  Returns:
    All vroom files in the directory (if it's a directory) and all files
    matching the glob (if it's a glob).
  """
  if os.path.isdir(filename):
    return glob.glob(os.path.join(filename, '*.vroom'))
  files = list(glob.glob(filename))
  if not files and os.path.exists(filename + '.vroom'):
    files = [filename + '.vroom']
  elif not files and not glob.has_magic(filename):
    raise ValueError('File "%s" not found.' % filename)
  return files


def IgnoredPaths(directory, skipped):
  for path in skipped:
    # --skip paths must be relative to the --crawl directory.
    path = os.path.join(directory, path)
    # All ignored paths which do not end in '.vroom' are assumed to be
    # directories. We have to make sure they've got a trailing slash, or
    # --skip=foo will axe anything with a foo prefix (foo/, foobar/, etc.)
    if not path.endswith('.vroom'):
      path = os.path.join(path, '')
    yield path


def Crawl(directory, ignored):
  """Crawls a directory looking for vroom files.

  Args:
    directory: The directory to crawl, may be None.
    ignored: A list of paths (absolute or relative to crawl directory) that will
        be pruned from the crawl results.
  Yields:
    the vroom files.
  """
  if not directory:
    return

  ignored = list(IgnoredPaths(directory, ignored))

  for (dirpath, dirnames, filenames) in os.walk(directory):
    # Traverse directories in alphabetical order. Default order fine for fnames.
    dirnames.sort()
    for filename in filenames:
      fullpath = os.path.join(dirpath, filename)
      for ignore in ignored:
        shared = os.path.commonprefix([ignore, fullpath])
        if shared == ignore:
          break
      else:
        if filename.endswith('.vroom'):
          yield fullpath
