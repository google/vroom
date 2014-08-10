"""Vroom control block parsing."""
import re

import vroom

# Pylint is not smart enough to notice that all the exceptions here inherit from
# vroom.test.Failure, which is a standard Exception.
# pylint: disable-msg=nonstandard-exception

OPTION = vroom.Specification(
    BUFFER='buffer',
    RANGE='range',
    MODE='mode',
    DELAY='delay',
    MESSAGE_STRICTNESS='messages',
    SYSTEM_STRICTNESS='system',
    OUTPUT_CHANNEL='channel')

MODE = vroom.Specification(
    REGEX='regex',
    GLOB='glob',
    VERBATIM='verbatim')

SPECIAL_RANGE = vroom.Specification(
    CURRENT_LINE='.')

REGEX = vroom.Specification(
    BUFFER_NUMBER=re.compile(r'^(\d+)$'),
    RANGE=re.compile(r'^(\.|\d+)?(?:,(\+)?(\$|\d+)?)?$'),
    MODE=re.compile(r'^(%s)$' % '|'.join(MODE.Values())),
    DELAY=re.compile(r'^(\d+(?:\.\d+)?)s?$'),
    CONTROL_BLOCK=re.compile(r'(  .*) \(\s*([%><=\'"\w\d.+,$ ]*)\s*\)$'),
    ESCAPED_BLOCK=re.compile(r'(  .*) \(&([^)]+)\)$'))

DEFAULT_MODE = MODE.VERBATIM


def SplitLine(line):
  """Splits the line controls off of a line.

  >>> SplitLine('  > This is my line (2s)')
  ('  > This is my line', '2s')
  >>> SplitLine('  > This one has no controls')
  ('  > This one has no controls', None)
  >>> SplitLine('  > This has an escaped control (&see)')
  ('  > This has an escaped control (see)', None)
  >>> SplitLine('  world (20,)')
  ('  world', '20,')

  Args:
    line: The line to split
  Returns:
    (line, control string)
  """
  match = REGEX.CONTROL_BLOCK.match(line)
  if match:
    return match.groups()
  unescape = REGEX.ESCAPED_BLOCK.match(line)
  if unescape:
    return ('%s (%s)' % unescape.groups(), None)
  return (line, None)


def BufferWord(word):
  """Parses a buffer control word.

  >>> BufferWord('2')
  2
  >>> BufferWord('not-a-buffer')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "not-a-buffer"

  Args:
    word: The control string.
  Returns:
    An int.
  Raises:
    UnrecognizedWord: When the word is not a buffer word.
  """
  if REGEX.BUFFER_NUMBER.match(word):
    return int(word)
  raise UnrecognizedWord(word)


def RangeWord(word):
  """Parses a range control word.

  >>> RangeWord('.,')[0] == SPECIAL_RANGE.CURRENT_LINE
  True

  >>> RangeWord(',+10')[0] is None
  True
  >>> RangeWord(',+10')[1](3)
  13

  >>> RangeWord('2,$')[0]
  2
  >>> RangeWord('2,$')[1]('anything')
  0

  >>> RangeWord('8,10')[0]
  8
  >>> RangeWord('8,10')[1](8)
  10

  >>> RangeWord('20,')[0]
  20

  >>> RangeWord('farts')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "farts"

  Args:
    word: The word to parse.
  Returns:
    (start, start -> end)
  Raises:
    UnrecognizedWord: When the word is not a range word.
  """
  match = REGEX.RANGE.match(word)
  if not match:
    raise UnrecognizedWord(word)
  (start, operator, end) = match.groups()
  if start == '.':
    start = SPECIAL_RANGE.CURRENT_LINE
  elif start:
    start = int(start)
  if end is None and operator is None:
    getend = lambda x: x
  elif end == '$':
    getend = lambda x: 0
  elif operator == '+':
    getend = lambda x: x + int(end)
  else:
    getend = lambda x: int(end)
  return (start, getend)


def DelayWord(word):
  """Parses a delay control word.

  >>> DelayWord('4')
  4.0
  >>> DelayWord('4.1s')
  4.1
  >>> DelayWord('nope')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "nope"

  Args:
    word: The word to parse.
  Returns:
    The delay, in milliseconds (as a float)
  Raises:
    UnrecognizedWord: When the word is not a delay word.
  """
  match = REGEX.DELAY.match(word)
  if match:
    return float(match.groups()[0])
  raise UnrecognizedWord(word)


def ModeWord(word):
  """Parses a mode control word.

  >>> ModeWord('regex') == MODE.REGEX
  True
  >>> ModeWord('glob') == MODE.GLOB
  True
  >>> ModeWord('verbatim') == MODE.VERBATIM
  True
  >>> ModeWord('nope')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "nope"

  Args:
    word: The word to parse.
  Returns:
    The mode string, a member of MODE
  Raises:
    UnrecognizedWord: When the word is not a mode word.
  """
  match = REGEX.MODE.match(word)
  if match:
    return word
  raise UnrecognizedWord(word)


def MessageWord(word):
  """Parses a message strictness level.

  >>> import vroom.messages
  >>> MessageWord('STRICT') == vroom.messages.STRICTNESS.STRICT
  True
  >>> MessageWord('RELAXED') == vroom.messages.STRICTNESS.RELAXED
  True
  >>> MessageWord('GUESS-ERRORS') == vroom.messages.STRICTNESS.ERRORS
  True
  >>> MessageWord('nope')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "nope"

  Args:
    word: The word to parse.
  Returns:
    The strictness, a member of vroom.messages.STRICTNESS
  Raises:
    UnrecognizedWord: When the word is not a STRICTNESS.
  """
  # vroom.controls can't import vroom.messages, because that creates a circular
  # dependency both with itself (controls is imported for DEFAULT_MODE) and
  # vroom.test. Sorry, pylint
  # Pylint, brilliant as usual, thinks that this line redefines 'vroom'.
  # pylint: disable-msg=redefined-outer-name
  import vroom.messages  # pylint: disable-msg=g-import-not-at-top
  regex = re.compile(
      r'^(%s)$' % '|'.join(vroom.messages.STRICTNESS.Values()))
  match = regex.match(word)
  if match:
    return word
  raise UnrecognizedWord(word)


def SystemWord(word):
  """Parses a system strictness level.

  >>> import vroom.shell
  >>> SystemWord('STRICT') == vroom.shell.STRICTNESS.STRICT
  True
  >>> SystemWord('RELAXED') == vroom.shell.STRICTNESS.RELAXED
  True
  >>> SystemWord('nope')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "nope"

  Args:
    word: The word to parse.
  Returns:
    The strictness, a member of vroom.shell.STRICTNESS
  Raises:
    UnrecognizedWord: When the word is not a STRICTNESS.
  """
  # vroom.controls can't import vroom.shell, because that creates a circular
  # dependency both with itself (controls is imported for DEFAULT_MODE) and
  # vroom.test. Sorry, pylint.
  # Pylint, brilliant as usual, thinks that this line redefines 'vroom'.
  # pylint: disable-msg=redefined-outer-name
  import vroom.shell  # pylint: disable-msg=g-import-not-at-top
  regex = re.compile(
      r'^(%s)$' % '|'.join(vroom.shell.STRICTNESS.Values()))
  match = regex.match(word)
  if match:
    return word
  raise UnrecognizedWord(word)


def OutputChannelWord(word):
  """Parses a system output channel.

  >>> import vroom.shell
  >>> OutputChannelWord('stdout') == vroom.shell.OUTCHANNEL.STDOUT
  True
  >>> OutputChannelWord('stderr') == vroom.shell.OUTCHANNEL.STDERR
  True
  >>> OutputChannelWord('command') == vroom.shell.OUTCHANNEL.COMMAND
  True
  >>> OutputChannelWord('status') == vroom.shell.OUTCHANNEL.STATUS
  True
  >>> OutputChannelWord('nope')
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "nope"

  Args:
    word: The word to parse.
  Returns:
    The output channel, a member of vroom.shell.OUTCHANNEL
  Raises:
    UnrecognizedWord: When the word is not an OUTCHANNEL.
  """
  # vroom.controls can't import vroom.shell, because that creates a circular
  # dependency both with itself (controls is imported for DEFAULT_MODE) and
  # vroom.test. Sorry, pylint
  # Pylint, brilliant as usual, thinks that this line redefines 'vroom'.
  # pylint: disable-msg=redefined-outer-name
  import vroom.shell  # pylint: disable-msg=g-import-not-at-top
  regex = re.compile(
      r'^(%s)$' % '|'.join(vroom.shell.OUTCHANNEL.Values()))
  match = regex.match(word)
  if match:
    return word
  raise UnrecognizedWord(word)


OPTION_PARSERS = {
    OPTION.BUFFER: BufferWord,
    OPTION.RANGE: RangeWord,
    OPTION.MODE: ModeWord,
    OPTION.DELAY: DelayWord,
    OPTION.MESSAGE_STRICTNESS: MessageWord,
    OPTION.SYSTEM_STRICTNESS: SystemWord,
    OPTION.OUTPUT_CHANNEL: OutputChannelWord,
}


def Parse(controls, *options):
  """Parses a control block.

  >>> controls = Parse('2 .,+2 regex 4.02s')
  >>> (controls['buffer'], controls['mode'], controls['delay'])
  (2, 'regex', 4.02)
  >>> (controls['range'][0], controls['range'][1](1))
  ('.', 3)

  >>> controls = Parse('1 2', OPTION.BUFFER, OPTION.DELAY)
  >>> (controls['buffer'], controls['delay'])
  (1, 2.0)

  >>> controls = Parse('1 2', OPTION.DELAY, OPTION.BUFFER)
  >>> (controls['buffer'], controls['delay'])
  (2, 1.0)

  >>> Parse('1 2 3', OPTION.DELAY, OPTION.BUFFER)
  Traceback (most recent call last):
    ...
  DuplicatedControl: Duplicated buffer control "3"

  >>> Parse('regex 4.02s', OPTION.MODE)
  Traceback (most recent call last):
    ...
  UnrecognizedWord: Unrecognized control word "4.02s"

  >>> Parse('STRICT', OPTION.MESSAGE_STRICTNESS)
  {'messages': 'STRICT'}
  >>> Parse('STRICT', OPTION.SYSTEM_STRICTNESS)
  {'system': 'STRICT'}

  Pass in members of OPTION to restrict what types of words are allowed and to
  control word precedence. If no options are passed in, all are allowed with
  precedence BUFFER, RANGE, MODE, DELAY

  Args:
    controls: The control string to parse.
    *options: The allowed OPTION type for each word (in order of precedence).
  Returns:
    A dict with the controls, with OPTION's values for keys. The keys will
    always exist, and will be None if the option was not present.
  Raises:
    ValueError: When the control can not be parsed.
  """
  if not options:
    options = [OPTION.BUFFER, OPTION.RANGE, OPTION.MODE, OPTION.DELAY]
  for option in [o for o in options if o not in OPTION_PARSERS]:
    raise ValueError("Can't parse unknown control word: %s" % option)
  parsers = [(o, OPTION_PARSERS.get(o)) for o in options]

  result = {o: None for o, _ in parsers}

  def Insert(key, val, word):
    if result[key] is not None:
      raise DuplicatedControl(option, word)
    result[key] = val

  error = None
  for word in controls.split():
    for option, parser in parsers:
      try:
        Insert(option, parser(word), word)
      except vroom.ParseError as e:
        error = e
      else:
        break
    else:
      raise error

  return result


class UnrecognizedWord(vroom.ParseError):
  """Raised when a control word is not recognized."""

  def __init__(self, word):
    msg = 'Unrecognized control word "%s"' % word
    super(UnrecognizedWord, self).__init__(msg)


class DuplicatedControl(vroom.ParseError):
  """Raised when a control word is duplicated."""

  def __init__(self, option, word):
    msg = 'Duplicated %s control "%s"' % (option, word)
    super(DuplicatedControl, self).__init__(msg)
