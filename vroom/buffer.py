"""Vroom buffer handling."""
import vroom.controls
import vroom.test

# Pylint is not smart enough to notice that all the exceptions here inherit from
# vroom.test.Failure, which is a standard Exception.
# pylint: disable-msg=nonstandard-exception


class Manager(object):
  """Manages the vim buffers."""

  def __init__(self, vim):
    self.vim = vim
    self.Unload()

  def Unload(self):
    """Unload the current buffer."""
    self._loaded = False
    self._buffer = None
    self._data = []
    self._line = None
    self._last_range = None

  def Load(self, buff):
    """Loads the requested buffer.

    If no buffer is loaded nor requested, the active buffer is used.
    Otherwise if no buffer is requested, the current buffer is used.
    Otherwise the requested buffer is loaded.

    Args:
      buff: The buffer to load.
    """
    if self._loaded and buff is None:
      return
    self.Unload()
    self._data = self.vim.GetBufferLines(buff)
    self._buffer = buff
    self._loaded = True

  def View(self, start, end):
    """A generator over given lines in a buffer.

    When vim messages are viewed in this fashion, the messenger object will be
    notified that those messages were not unexpected.

    Args:
      start: The beginning of the range.
      end: A function to get the end of the range.
    Yields:
      An iterable over the range.
    Raises:
      NotEnoughOutput: when the range exceeds the buffer.
    """
    # If no start line is given, we advance to the next line. Therefore, if the
    # buffer has not yet been inspected we want to start at one before line 0.
    self._line = -1 if self._line is None else self._line
    # Vim 1-indexes lines.
    if start == vroom.controls.SPECIAL_RANGE.CURRENT_LINE:
      start = self.vim.GetCurrentLine() - 1
    else:
      start = (self._line + 1) if start is None else (start - 1)

    # No need to decrement; vroom ranges are inclusive and vim 1-indexes.
    end = (start + 1) if end is None else end(start + 1)
    # End = 0 means check till end of buffer.
    end = len(self._data) if end is 0 else end
    # If there's an error, they'll want to know what we were looking at.
    self._last_range = (start, end)

    # Yield each relevant line in the range.
    for i in range(start, end):
      self._line = i
      if i < len(self._data):
        yield self._data[i]
      else:
        raise NotEnoughOutput(self.GetContext())

  # 'range' is the most descriptive name here. Putting 'range' in kwargs and
  # pulling it out obfuscates the code. Sorry, pylint. (Same goes for 'buffer'.)
  def Verify(  # pylint: disable-msg=redefined-builtin
      self, desired, buffer=None, range=None, mode=None):
    """Checks the contents of a vim buffer.

    Checks that all lines in the given range in the loaded buffer match the
    given line under the given mode.

    Args:
      desired: The line that everything should look like.
      buffer: The buffer to load.
      range: The range of lines to check.
      mode: The mode to match in.
    Raises:
      WrongOutput: if the output is wrong.
    """
    self.Load(buffer)
    start, end = range or (None, None)
    for actual in self.View(start, end):
      if not vroom.test.Matches(desired, mode, actual):
        raise WrongOutput(desired, mode, self.GetContext())

  # See self.Verify for the reasoning behind the pylint trump.
  def EnsureAtEnd(self, buffer):  # pylint: disable-msg=redefined-builtin
    """Ensures that the test has verified to the end of the loaded buffer.

    Args:
      buffer: The buffer to load.
    Raises:
      BadOutput: If the buffer is not in a state to have its end checked.
      WrongOutput: If the buffer is not at the end.
    """
    self.Load(buffer)
    self._last_range = (len(self._data), len(self._data))
    if self._line is None:
      if self._data == [''] or not self._data:
        return
      msg = 'Misuse of @end: buffer has not been checked yet.'
      raise BadOutput(self.GetContext(), msg)
    if self._line != len(self._data) - 1:
      raise TooMuchOutput(self.GetContext())

  def GetContext(self):
    """Information about what part of the buffer was being looked at.

    Invaluable in exceptions.

    Returns:
      Dict containing 'buffer', 'data', 'line', 'start', and 'end'.
    """
    if (not self._loaded) or (self._last_range is None):
      return None
    (start, end) = self._last_range
    return {
        'buffer': self._buffer,
        'data': self._data,
        'line': self._line,
        'start': start,
        'end': end,
    }


class BadOutput(vroom.test.Failure):
  """Raised when vim's output is not the expected output."""
  DESCRIPTION = 'Output does not match expectation.'

  def __init__(self, context, message=None):
    self.context = context
    super(BadOutput, self).__init__(message or self.DESCRIPTION)


class WrongOutput(BadOutput):
  """Raised when a line fails to match the spec."""

  def __init__(self, line, mode, context):
    """Makes the exception.

    Args:
      line: The expected line.
      mode: The match mode.
      context: The buffer context.
    """
    self.context = context
    mode = mode or vroom.controls.DEFAULT_MODE
    msg = 'Expected "%s" in %s mode.' % (line, mode)
    super(WrongOutput, self).__init__(context, msg)


class TooMuchOutput(BadOutput):
  """Raised when vim has more output than a vroom test wants."""
  DESCRIPTION = 'Expected end of buffer.'


class NotEnoughOutput(BadOutput):
  """Raised when vim has less output than a vroom test wants."""
  DESCRIPTION = 'Unexpected end of buffer.'
