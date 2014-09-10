"""Vroom output manager. It's harder than it looks."""
import sys
import traceback

import vroom
import vroom.buffer
import vroom.color
import vroom.controls
import vroom.messages
import vroom.shell
import vroom.test
import vroom.vim

# In lots of places in this file we use the name 'file' to mean 'a file'.
# We do this so that Logger.Print can have an interface consistent with
# python3's print.
# pylint: disable-msg=redefined-builtin


STATUS = vroom.Specification(
    PASS='PASS',
    ERROR='ERROR',
    FAIL='FAIL')


COLORS = {
    STATUS.PASS: vroom.color.GREEN,
    STATUS.ERROR: vroom.color.YELLOW,
    STATUS.FAIL: vroom.color.RED,
}


class Writer(object):
  """An output writer for a single vroom test file."""

  def __init__(self, filename, args):
    """Creatse the writer.

    Args:
      filename: The file to be tested.
      args: The command line arguments.
    """
    self.messages = MessageLogger(args.dump_messages, args.verbose, args.color)
    self.commands = CommandLogger(args.dump_commands, args.verbose, args.color)
    self.syscalls = SyscallLogger(args.dump_syscalls, args.verbose, args.color)
    self.actions = ActionLogger(args.out, args.verbose, args.color)
    self._filename = filename

  def Begin(self, lines):
    """Begins testing the file.

    Args:
      lines: The lines of the file.
    """
    self.actions.Open(lines)

  def Write(self, file=None):
    """Writes output for the file.

    Must be done after all tests are completed, because stdout will be used to
    run vim during the duration of the tests.

    Args:
      file: An alternate file handle to write to. Default None.
    """
    self.actions.Print(self._filename, color=(
        vroom.color.BOLD, vroom.color.TEAL), file=file)
    self.actions.Print('', verbose=True, file=file)
    self.actions.Write(self._filename, file=file)
    extra = self.messages.Write(self._filename, file=file)
    extra = self.commands.Write(self._filename, file=file) or extra
    extra = self.syscalls.Write(self._filename, file=file) or extra
    self.actions.Print('', file=file, verbose=None if extra else True)
    stats = self.Stats()
    plural = '' if stats['total'] == 1 else 's'
    self.actions.Print('Ran %d test%s in %s.' % (
        stats['total'], plural, self._filename), end=' ')
    self.actions.PutStat(stats, STATUS.PASS, '%d passing', file=file)
    self.actions.PutStat(stats, STATUS.ERROR, '%d errored', file=file)
    self.actions.PutStat(stats, STATUS.FAIL, '%d failed', file=file, end='.\n')
    if stats['total'] == 0:
      self.actions.Print(
          'WARNING', color=vroom.color.YELLOW, file=file, end=': ')
      self.actions.Print('NO TESTS RUN', file=file)

  def Stats(self):
    """Statistics on this test. Should be called after the test has completed.

    Returns:
      A dict containing STATUS fields.
    """
    if not hasattr(self, '_stats'):
      stats = self.actions.Results()
      stats['total'] = (
          stats[STATUS.PASS] + stats[STATUS.ERROR] + stats[STATUS.FAIL])
      self._stats = stats
    return self._stats

  def Status(self):
    """Returns the status of this test.

    Returns:
      PASS for Passed.
      ERROR for Errored (no failures).
      FAIL for Failure.
    """
    stats = self.Stats()
    if stats[STATUS.FAIL]:
      return STATUS.FAIL
    elif stats[STATUS.ERROR]:
      return STATUS.ERROR
    return STATUS.PASS


class Logger(object):
  """Generic writer sublogger.

  We can't use one logger because sometimes we have different writing components
  (system logs, message logs, command logs) that are all writing interleavedly
  but which should output in separate blocks. These Loggers handle one of those
  separate blocks.

  Thus, it must queue all messages and write them all at once at the end.
  """
  HEADER = None
  EMPTY = None

  def __init__(self, file, verbose, color):
    """Creates the logger.

    Args:
      file: The file to log to.
      verbose: Whether or not to write verbosely.
      color: A function used to color text.
    """
    self._verbose = verbose
    self._color = color
    self._file = file
    self._queue = []

  def Log(self, message):
    """Records a message.

    Args:
      message: The message to record.
    """
    self._queue.append(message)

  def Logs(self):
    """The currently recorded messages.

    Mostly used when exceptions try to
    figure out why they happened.

    Returns:
      A list of messages.
    """
    return self._queue

  def Print(self, message, verbose=None, color=None, end='\n', file=None):
    """Prints a message to the file.

    Args:
      message: The message to print.
      verbose: When verbose is not None, message is only printed if verbose is
          the same as --verbose.
      color: vroom.color escape code (or a tuple of the same) to color the
          message with.
      end: The line-end (use '' to suppress the default newline).
      file: Alternate file handle to use.
    """
    handle = file or self._file
    if (verbose is None) or (verbose == self._verbose):
      if handle == sys.stdout and color is not None:
        if not isinstance(color, tuple):
          color = (color,)
        message = self._color(message, *color)
      handle.write(message + end)

  def Write(self, filename, file=None):
    """Writes all messages.

    Args:
      filename: Vroom file that was tested, for use in the header.
      file: An alternate file to write to. Will only redirect to the
          alternate file if it was going to write to a file in the first place.
    Returns:
      Whether or not output was written.
    """
    if self._file is None:
      return False
    file = file or self._file
    lines = list(self.Finalize(self._queue))
    self.Print('', file=file)
    if lines:
      if self.HEADER:
        header = self.HEADER % {'filename': filename}
        self.Print(header, end=':\n', file=file)
      for line in lines:
        self.Print(line.rstrip('\n'), file=file)
    elif self.EMPTY:
      empty = self.EMPTY % {'filename': filename}
      self.Print(empty, end='.\n', file=file)
    return True

  def Finalize(self, queue):
    """Used to pre-process all messages after the test and before display.

    Args:
      queue: The message queue
    Returns:
      The modified message queue.
    """
    return PrefixWithIndex(queue)


class MessageLogger(Logger):
  """A logger for vim messages."""

  HEADER = 'Vim messages during %(filename)s'
  EMPTY = 'There were no vim messages during %(filename)s'


class CommandLogger(Logger):
  """A logger for vim commands."""

  HEADER = 'Commands sent to vim during %(filename)s'
  EMPTY = 'No commands were sent to vim during %(filename)s'


class SyscallLogger(Logger):
  """A logger for vim system commands & calls."""

  HEADER = 'System call log during %(filename)s'
  EMPTY = 'No syscalls made by vim during %(filename)s'

  def Finalize(self, queue):
    return map(str, queue)


class ActionLogger(Logger):
  """A logger for the main test output.

  Prints the test file in verbose mode. Prints minimal pass/failure information
  otherwise.
  """

  def __init__(self, *args, **kwargs):
    self._opened = False
    super(ActionLogger, self).__init__(*args, **kwargs)

  def Open(self, lines):
    """Opens the action logger for a specific vroom file.

    Must be called before logging can begin.

    Args:
      lines: The file's lines.
    """
    self._lines = lines
    self._nextline = 0
    self._passed = 0
    self._errored = 0
    self._failed = 0
    self._opened = True

  def Write(self, filename, file=None):
    """Writes the test output. Should be called after vim has shut down.

    Args:
      filename: Used in the header.
      file: Alt file to redirect output to. Output will only be redirected
          if it was going to be output in the first place.
    Raises:
      NoTestRunning: if called too soon.
    """
    if not self._opened:
      raise NoTestRunning
    self.ExecutedUpTo(len(self._lines) - 1)
    for (line, args, kwargs) in self._queue:
      self.Print(line, *args, file=file, **kwargs)

  def PutStat(self, stats, stat, fmt, **kwargs):
    """Writes a stat to output.

    Will color the stat if the stat is non-zero and the output file is stdout.

    Args:
      stats: A dict with all the stats.
      stat: The STATUS to check.
      fmt: What to say about the stat.
      **kwargs: Passed on to print.
    """
    assert stat in stats and stat in COLORS
    num = stats[stat]
    kwargs.setdefault('end', ', ')
    if num:
      kwargs['color'] = COLORS[stat]
    self.Print(fmt % num, **kwargs)

  def Queue(self, message, *args, **kwargs):
    """Queues a single line for writing to the output file.

    Args:
      message: Will eventually be written.
      *args: Will be passed to Print.
      **kwargs: Will be passed to Print.
    """
    self._queue.append((message, args, kwargs))

  def Log(self, result, lineno, error=None):
    """Logs a test result.

    Args:
      result: The vroom.test.RESULT
      lineno: The line where the error occured.
      error: The exception if vroom.test.isBad(result)
    Raises:
      NoTestRunning: if called too soon.
    """
    self.Tally(result)
    self.ExecutedUpTo(lineno)
    if error is not None:
      self._Error(result, error, lineno)

  def Tally(self, result):
    """Tallies the result.

    Args:
      result: A vroom.test.result
    """
    if result == vroom.test.RESULT.PASSED:
      self._passed += 1
    if result == vroom.test.RESULT.ERROR:
      self._errored += 1
    if result == vroom.test.RESULT.FAILED:
      self._failed += 1

  def ExecutedUpTo(self, lineno):
    """Print output put to a given line number.

    This really only matters in --verbose mode where the file is printed as the
    tests run.

    Args:
      lineno: The line to print up to.
    """
    if self._verbose:
      for i, line in enumerate(self._lines[self._nextline:lineno + 1]):
        number = self.Lineno(self._nextline + i)
        self.Queue('%s %s' % (number, line.rstrip('\n')))
    self._nextline = lineno + 1

  def Lineno(self, lineno):
    """The string version of a line number, zero-padded as appropriate.

    Args:
      lineno: The line number
    Returns:
      The zero-padded string.
    """
    numberifier = '%%0%dd' % len(str(len(self._lines)))
    return numberifier % (lineno + 1)

  def Error(self, result, error):
    """Logs an error that didn't occur at a specific line.

    (Vim didn't start, etc.)

    Args:
      result: The vroom.test.RESULT.
      error: The exception.
    """
    self.Tally(result)
    self._Error(result, error)

  def _Error(self, result, error, lineno=None):
    """Prints an error message. Used by both Log and Error on bad results.

    Args:
      result: The vroom.test.RESULT.
      error: The execption.
      lineno: The place that the error occured, if known.
    """
    self.Queue('------------------------------------------------', verbose=True)
    if result == vroom.test.RESULT.ERROR:
      self.Queue(result.upper(), color=COLORS[STATUS.ERROR], end='')
    else:
      self.Queue(result.upper(), color=COLORS[STATUS.FAIL], end='')
    if lineno is not None:
      self.Queue(' on line %s' % self.Lineno(lineno), verbose=False, end='')
    self.Queue(': ', end='')
    self.Queue(str(error))
    # Print extra context about the error.
    # Python isinstance is freeking pathological: isinstance(foo, Foo) can
    # change depending upon how you import Foo.  Instead of dealing with that
    # mess, we ducktype exceptions.
    # Also, python can't do real closures, which is why contexted is a list.
    contexted = [False]

    def QueueContext(attr, writer, *args):
      value = None
      if hasattr(error, attr):
        value = getattr(error, attr)
      elif hasattr(error, 'GetFlattenedFailures'):
        for f in error.GetFlattenedFailures():
          if hasattr(f, attr):
            value = getattr(f, attr)
            break
      if value is None:
        return
      contexted[0] = True
      self.Queue('')
      writer(value, self.Queue, *args)

    QueueContext('messages', ErrorMessageContext)
    QueueContext('context', ErrorBufferContext)

    if lineno is not None:
      stripped = self._lines[lineno][2:]
      line = '\nFailed command on line %s:\n%s' % (
          self.Lineno(lineno), stripped)
      self.Queue(line, end='', verbose=False)

    QueueContext('expectations', ErrorShellQueue)
    QueueContext('syscalls', ErrorSystemCalls)
    QueueContext('commands', ErrorCommandContext)

    if contexted[0]:
      self.Queue('', verbose=False)
    self.Queue('------------------------------------------------', verbose=True)

  def Results(self):
    """The test results.

    Returns:
      A dict containing STATUS.PASS, STATUS.ERROR, and STATUS.FAIL.
    """
    return {
        STATUS.PASS: self._passed,
        STATUS.ERROR: self._errored,
        STATUS.FAIL: self._failed,
    }

  def Exception(self, exctype, exception, tb):
    """Prints out an unexpected exception with stack info.

    Should only be used when vroom encounters an error in its own programming.
    We don't ever want real users to see these.

    Args:
      exctype: The exception type.
      exception: The exception.
      tb: The traceback.
    """
    self.Tally(vroom.test.RESULT.ERROR)
    self.Queue('------------------------------------------------', verbose=True)
    self.Queue('')
    self.Queue('ERROR', color=COLORS[STATUS.ERROR], end='')
    self.Queue(': ', end='')
    self.Queue(''.join(traceback.format_exception(exctype, exception, tb)))
    self.Queue('')
    if hasattr(exception, 'shell_errors'):
      ErrorShellErrors(exception.shell_errors, self.Queue)
      self.Queue('')
    self.Queue('------------------------------------------------', verbose=True)


def WriteBackmatter(writers, args):
  """Writes the backmatter (# tests run, etc.) for a group of writers.

  Args:
    writers: The writers
    args: The command line args.
  """
  if len(writers) == 1:
    # No need to summarize, we'd be repeating ourselves.
    return
  count = 0
  total = 0
  passed = 0
  errored = 0
  args.out.write(args.color('\nVr', vroom.color.VIOLET))
  for writer in writers:
    count += 1
    total += writer.Stats()['total']
    status = writer.Status()
    if status == STATUS.PASS:
      passed += 1
    elif status == STATUS.ERROR:
      errored += 1
    args.out.write(args.color('o', COLORS[status]))
  args.out.write(args.color('m\n', vroom.color.VIOLET))
  plural = '' if total == 1 else 's'
  args.out.write('Ran %d test%s in %d files. ' % (total, plural, count))
  if passed == count:
    args.out.write('Everything is ')
    args.out.write(args.color('OK', COLORS[STATUS.PASS]))
    args.out.write('.')
  else:
    args.out.write(args.color('%d passed' % passed, COLORS[STATUS.PASS]))
    args.out.write(', ')
    args.out.write(args.color('%d errored' % errored, COLORS[STATUS.ERROR]))
    args.out.write(', ')
    failed = count - passed - errored
    args.out.write(args.color('%d failed' % failed, COLORS[STATUS.FAIL]))
  args.out.write('\n')


def PrefixWithIndex(logs):
  """Prefixes a bunch of lines with their index.

  Indicies are zero-padded so that everything aligns nicely.
  If there's a None log it's skipped and a linebreak is output.
  Trailing None logs are ignored.

  >>> list(PrefixWithIndex(['a', 'a']))
  ['1\\ta', '2\\ta']
  >>> list(PrefixWithIndex(['a' for _ in range(10)]))[:2]
  ['01\\ta', '02\\ta']
  >>> list(PrefixWithIndex(['a', None, 'a']))
  ['1\\ta', '', '2\\ta']

  Args:
    logs: The lines to index.
  Yields:
    The indexed lines.
  """
  # Makes sure we don't accidentally modify the real logs.
  # Also, makes the code not break if someone passes us a generator.
  logs = list(logs)
  while logs and logs[-1] is None:
    logs.pop()
  # Gods, I love this line. It creates a formatter that pads a number out to
  # match the largest number necessary to index all the non-null lines in logs.
  numberifier = '%%0%dd' % len(str(len(list(filter(bool, logs)))))
  adjustment = 0
  for (i, log) in enumerate(logs):
    if log is None:
      adjustment += 1
      yield ''
    else:
      index = numberifier % (i + 1 - adjustment)
      yield '%s\t%s' % (index, log)


def ErrorContextPrinter(header, empty, modifier=None, singleton=None):
  """Creates a function that prints extra error data.

  Args:
    header: What to print before the data.
    empty: What to print when there's no data.
    modifier: Optional, run on all the data before printing.
    singleton: Optional, what to print when there's only one datum.
  Returns:
    Function that takes (data, printer) and prints the data using the printer.
  """

  def WriteExtraData(data, printer):
    data = list(modifier(data) if modifier else data)
    if data:
      if not singleton or len(data) > 1:
        printer(header, end=':\n')
        for datum in data:
          if datum is None:
            printer('')
          else:
            printer(str(datum))
      else:
        printer(singleton % data[0])
    else:
      printer(empty)

  return WriteExtraData


# Pylint isn't smart enough to notice that these are all generated functions.
ErrorMessageContext = ErrorContextPrinter(  # pylint: disable-msg=g-bad-name
    'Messages',
    'There were no messages.',
    modifier=None,
    singleton='Message was "%s"')

ErrorCommandContext = ErrorContextPrinter(  # pylint: disable-msg=g-bad-name
    'Last few commands (most recent last) were',
    'No relevant commands found.')

ErrorSystemCalls = ErrorContextPrinter(  # pylint: disable-msg=g-bad-name
    'Recent system logs are',
    'No system calls received. Perhaps your --shell is broken?')

ErrorShellQueue = ErrorContextPrinter(  # pylint: disable-msg=g-bad-name
    'Queued system controls are',
    'No system commands expected.')

ErrorShellErrors = ErrorContextPrinter(  # pylint: disable-msg=g-bad-name
    'Shell error list',
    'Shell had no chance to log errors.',
    modifier=PrefixWithIndex)


def ErrorBufferContext(context, printer):
  """Prints the buffer data relevant to an error.

  Args:
    context: The buffer context.
    printer: A function to do the printing.
  """
  if context is None:
    printer('No vim buffer was loaded.')
    return

  # Find out what buffer we're printing from.
  if context['buffer'] is None:
    printer('Checking the current buffer.', end='', verbose=True)
  else:
    printer('Checking buffer %s.' % context['buffer'], end='', verbose=True)
  printer(' Relevant buffer data:', verbose=True)
  printer('Found:', verbose=False)

  # Print the relevant buffer lines
  (start, end) = (context['start'], context['end'])
  # Empty buffer.
  if not context['data']:
    printer('An empty buffer.')
    return

  buflines = list(PrefixWithIndex(context['data']))
  # They're looking at a specific line.
  if end > start:
    for i, bufline in enumerate(buflines[start:end]):
      if context['line'] == i + start:
        printer(bufline + ' <<<<', color=vroom.color.BOLD)
      else:
        printer(bufline)
  # They're looking at the whole buffer.
  else:
    for bufline in buflines:
      printer(bufline)


class NoTestRunning(ValueError):
  """Raised when a logger is asked to log before the test begins."""

  def __init__(self):
    """Creates the exception."""
    super(NoTestRunning, self).__init__(
        'Please run a vroom test before outputting results.')
