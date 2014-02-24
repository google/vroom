"""Vroom action parsing (actions are different types of vroom lines)."""
import vroom
import vroom.controls

ACTION = vroom.Specification(
    COMMENT='comment',
    PASS='pass',
    INPUT='input',
    COMMAND='command',
    TEXT='text',
    CONTINUATION='continuation',
    DIRECTIVE='directive',
    MESSAGE='message',
    SYSTEM='system',
    HIJACK='hijack',
    OUTPUT='output')

DIRECTIVE = vroom.Specification(
    CLEAR='clear',
    END='end',
    MESSAGES='messages',
    SYSTEM='system')

DIRECTIVE_PREFIX = '  @'
EMPTY_LINE_CHECK = '  &'

# The number of blank lines that equate to a @clear command.
# (Set to None to disable).
BLANK_LINE_CLEAR_COMBO = 3

UNCONTROLLED_LINE_TYPES = {
    ACTION.CONTINUATION: '  |',
}

DELAY_OPTIONS = (vroom.controls.OPTION.DELAY,)
MODE_OPTIONS = (vroom.controls.OPTION.MODE,)
BUFFER_OPTIONS = (vroom.controls.OPTION.BUFFER,)
HIJACK_OPTIONS = (vroom.controls.OPTION.OUTPUT_CHANNEL,)
OUTPUT_OPTIONS = (
    vroom.controls.OPTION.BUFFER,
    vroom.controls.OPTION.RANGE,
    vroom.controls.OPTION.MODE,
)

CONTROLLED_LINE_TYPES = {
    ACTION.INPUT: ('  > ', DELAY_OPTIONS),
    ACTION.TEXT: ('  % ', DELAY_OPTIONS),
    ACTION.COMMAND: ('  :', DELAY_OPTIONS),
    ACTION.MESSAGE: ('  ~ ', MODE_OPTIONS),
    ACTION.SYSTEM: ('  ! ', MODE_OPTIONS),
    ACTION.HIJACK: ('  $ ', HIJACK_OPTIONS),
    ACTION.OUTPUT: ('  & ', OUTPUT_OPTIONS),
}


def ActionLine(line):
  """Parses a single action line of a vroom file.

  >>> ActionLine('This is a comment.')
  ('comment', 'This is a comment.', {})
  >>> ActionLine('  > iHello, world!<ESC> (2s)')
  ('input', 'iHello, world!<ESC>', {'delay': 2.0})
  >>> ActionLine('  :wqa')
  ('command', 'wqa', {'delay': None})
  >>> ActionLine('  % Hello, world!')  # doctest: +ELLIPSIS
  ('text', 'Hello, world!', ...)
  >>> ActionLine('  |To be continued.')
  ('continuation', 'To be continued.', {})
  >>> ActionLine('  ~ ERROR(*): (glob)')
  ('message', 'ERROR(*):', {'mode': 'glob'})
  >>> ActionLine('  ! system says (regex)')
  ('system', 'system says', {'mode': 'regex'})
  >>> ActionLine('  $ I say...')  # doctest: +ELLIPSIS
  ('hijack', 'I say...', ...)
  >>> ActionLine('  $ I say... (stderr)')  # doctest: +ELLIPSIS
  ('hijack', 'I say...', ...)
  >>> ActionLine('  @clear')
  ('directive', 'clear', {})
  >>> ActionLine('  @nope')
  Traceback (most recent call last):
    ...
  ParseError: Unrecognized directive "nope"
  >>> ActionLine('  & Output!')  # doctest: +ELLIPSIS
  ('output', 'Output!', ...)
  >>> ActionLine('  Simpler output!')  # doctest: +ELLIPSIS
  ('output', 'Simpler output!', ...)

  Args:
    line: The line (string)
  Returns:
    (ACTION, line, controls) where line is the original line with the newline,
        action prefix ('  > ', etc.) and control block removed, and controls is
        a control dictionary.
  Raises:
    vroom.ParseError
  """
  line = line.rstrip('\n')

  # PASS is different from COMMENT in that PASS breaks up output blocks,
  # hijack continuations, etc.
  if not line:
    return (ACTION.PASS, line, {})

  if not line.startswith('  '):
    return (ACTION.COMMENT, line, {})

  # These lines do not use control blocks.
  # NOTE: We currently don't even check for control blocks on these line types,
  # preferring to trust the user. We should consider which scenario is more
  # common: People wanting a line ending in parentheses without escaping them,
  # and so using a continuation, versus people accidentally putting a control
  # block where they shouldn't and being surprised when it's ignored.
  # Data would be nice.
  for linetype, prefix in UNCONTROLLED_LINE_TYPES.items():
    if line.startswith(prefix):
      return (linetype, line[len(prefix):], {})

  # Directives must be parsed in two chunks, as some allow controls blocks and
  # some don't. This section is directives with no control blocks.
  if line.startswith(DIRECTIVE_PREFIX):
    directive = line[len(DIRECTIVE_PREFIX):]
    if directive == DIRECTIVE.CLEAR:
      return (ACTION.DIRECTIVE, directive, {})

  line, controls = vroom.controls.SplitLine(line)

  def Controls(options):
    return vroom.controls.Parse(controls or '', *options)

  # Here lie directives that have control blocks.
  if line.startswith(DIRECTIVE_PREFIX):
    directive = line[len(DIRECTIVE_PREFIX):]
    if directive == DIRECTIVE.END:
      return (ACTION.DIRECTIVE, directive, Controls(BUFFER_OPTIONS))
    elif directive == DIRECTIVE.MESSAGES:
      return (ACTION.DIRECTIVE, directive, Controls(
          (vroom.controls.OPTION.MESSAGE_STRICTNESS,)))
    elif directive == DIRECTIVE.SYSTEM:
      return (ACTION.DIRECTIVE, directive, Controls(
          (vroom.controls.OPTION.SYSTEM_STRICTNESS,)))
    # Non-controlled directives should be parsed before SplitLineControls.
    raise vroom.ParseError('Unrecognized directive "%s"' % directive)

  for linetype, (prefix, options) in CONTROLLED_LINE_TYPES.items():
    if line.startswith(prefix):
      return (linetype, line[len(prefix):], Controls(options))

  # Special output to match empty buffer lines without trailing whitespace.
  if line == EMPTY_LINE_CHECK:
    return (ACTION.OUTPUT, '', Controls(OUTPUT_OPTIONS))

  # Default
  return (ACTION.OUTPUT, line[2:], Controls(OUTPUT_OPTIONS))


def Parse(lines):
  """Parses a vroom file.

  Is actually a generator.

  Args:
    lines: An iterable of lines to parse. (A file handle will do.)
  Yields:
    (Number, ACTION, Line, Control Dictionary) where
        Number is the original line number (which may not be the same as the
            index in the list if continuation lines were used. It's the line
            number of the last relevant continuation.)
        ACTION is the ACTION (will never be COMMENT nor CONTINUATION)
        Line is the parsed line.
        Control Dictionary is the control data.
  Raises:
    vroom.ParseError with the relevant line number and an error message.
  """
  pending = None
  pass_count = 0
  for (lineno, line) in enumerate(lines):
    try:
      (linetype, line, control) = ActionLine(line)
    # Add line number context to all parse errors.
    except vroom.ParseError as e:
      e.SetLineNumber(lineno)
      raise
    # Ignore comments during vroom execution.
    if linetype == ACTION.COMMENT:
      # Comments break blank-line combos.
      pass_count = 0
      continue
    # Continuation actions are chained to the pending action.
    if linetype == ACTION.CONTINUATION:
      if pending is None:
        raise vroom.ConfigurationError('No command to continue', lineno)
      pending = (lineno, pending[1], pending[2] + line, pending[3])
      continue
    # Contiguous hijack commands are chained together by newline.
    if (pending is not None and
        pending[1] == ACTION.HIJACK and
        not control and
        linetype == ACTION.HIJACK):
      pending = (lineno, linetype, '\n'.join((pending[2], line)), pending[3])
      continue
    # Flush out any pending commands now that we know there's no continuations.
    if pending:
      yield pending
      pending = None
    action = (lineno, linetype, line, control)
    # PASS lines can't be continuated.
    if linetype == ACTION.PASS:
      pass_count += 1
      if pass_count == BLANK_LINE_CLEAR_COMBO:
        yield (lineno, ACTION.DIRECTIVE, DIRECTIVE.CLEAR, {})
      else:
        yield action
    else:
      pass_count = 0
    # Hold on to this line in case it's followed by a continuation.
    pending = action
  # Flush out any actions still in the queue.
  if pending:
    yield pending
