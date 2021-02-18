"""Vroom vim management."""
import ast
from io import StringIO
import json
import re
import subprocess
import tempfile
import time


# Regex for quoted python string literal. From pyparsing.quotedString.reString.
QUOTED_STRING_RE = re.compile(r'''
  (?:"(?:[^"\n\r\\]|(?:"")|(?:\\x[0-9a-fA-F]+)|(?:\\.))*")|
  (?:'(?:[^'\n\r\\]|(?:'')|(?:\\x[0-9a-fA-F]+)|(?:\\.))*')
''', re.VERBOSE)

# Vroom has been written such that this data *could* go into a separate .vim
# file, and that would be great. However, python distutils (believe it or not)
# makes it extraordinarily tough to distribute custom files with your python
# modules. It's both difficult to know where they go and difficult to allow them
# to be read. If the user does a sudo install, distutils has no way to make the
# .vim file actually readable and vroom dies from permission errors.
# So screw you, python. I'll just hardcode it.
_, CONFIGFILE = tempfile.mkstemp()
with open(CONFIGFILE, 'w') as configfile:
  configfile.write("""
" Prevents your vroom tests from doing nasty things to your system.
set noswapfile

" Hidden function to execute a command and return the output.
" Useful for :messages
function! VroomExecute(command)
  redir => l:output
  silent! execute a:command
  redir end
  return l:output
endfunction

" Hidden function to reset a test.
function! VroomClear()
  stopinsert
  silent! bufdo! bdelete!
endfunction

" Hidden function to dump an error into vim.
function! VroomDie(output)
  let g:vroom_error = a:output
  let g:vroom_error .= "\\n:tabedit $VROOMFILE to edit the test file."
  let g:vroom_error .= "\\nThis output is saved in g:vroom_error."
  let g:vroom_error .= "\\nQuit vim when you're done."
  echo g:vroom_error
endfunction

" Hidden function to kill vim, independent of insert mode.
function! VroomEnd()
  qa!
endfunction
""")


def DeserializeVimValue(value_str):
  """Return string representation of value literal from vim.

  Args:
    value_str: A serialized string representing a simple value literal. The
        serialization format is just the output of the vimscript string() func.
  Raises:
    BadVimValue if the value could not be deserialized.
  """
  if not value_str:
    return None
  # Translate some vimscript idioms to python before evaling as python literal.
  # Vimscript strings represent backslashes literally.
  value_str = value_str.replace('\\', '\\\\').replace('\n', '\\n')
  # Replace "''" inside strings with "\'".
  def ToVimQuoteEscape(m):
    val = m.group(0)
    if val.startswith("'"):
      return val[:1] + val[1:-1].replace("''", "\\'") + val[-1:]
    else:
      return val
  value_str = re.sub(QUOTED_STRING_RE, ToVimQuoteEscape, value_str)
  try:
    return ast.literal_eval(value_str)
  except SyntaxError:
    raise BadVimValue(value_str)


class Communicator(object):
  """Object to communicate with a vim server."""

  def __init__(self, args, env, writer):
    self.writer = writer.commands
    self.args = args
    # The order of switches matters. '--clean' will prevent vim from loading any
    # plugins from ~/.vim/, but it also sets '-u DEFAULTS'. We supply '-u' after
    # to force vim to take our '-u' value (while still avoiding plugins).
    self.start_command = [
        'vim',
        '--clean',
        '-u', args.vimrc,
        '--servername', args.servername,
        '-c', 'set shell=' + args.shell,
        '-c', 'source %s' % CONFIGFILE]
    self.env = env
    self._cache = {}

  def Start(self):
    """Starts vim."""
    if not self._IsCurrentDisplayUsable():
      # Try using explicit $DISPLAY value. This only affects vim's client/server
      # connections and not how console vim appears.
      original_display = self.env.get('DISPLAY')
      self.env['DISPLAY'] = ':0'
      if not self._IsCurrentDisplayUsable():
        # Restore original display value if ":0" doesn't work, either.
        if original_display is None:
          del self.env['DISPLAY']
        else:
          self.env['DISPLAY'] = original_display
      # TODO(dbarnett): Try all values from /tmp/.X11-unix/, etc.

    # We do this separately from __init__ so that if it fails, vroom.runner
    # still has a _vim attribute it can query for details.
    self.process = subprocess.Popen(self.start_command, env=self.env)
    time.sleep(self.args.startuptime)
    if self.process.poll() is not None and self.process.poll() != 0:
      # If vim exited this quickly, it probably means we passed a switch it
      # doesn't recognize. Try again without the '--clean' switch since this is
      # new in 8.0.1554+.
      self.start_command.remove('--clean')
      self.process = subprocess.Popen(self.start_command, env=self.env)
      time.sleep(self.args.startuptime)

  def _IsCurrentDisplayUsable(self):
    """Check whether vim fails using the current configured display."""
    try:
      self.Ask('1')
    except NoDisplay:
      return False
    except Quit:
      # Any other error means the display setting is fine (assuming vim didn't
      # fail before it checked the display).
      pass
    return True

  def Communicate(self, command, extra_delay=0):
    """Sends a command to vim & sleeps long enough for the command to happen.

    Args:
      command: The command to send.
      extra_delay: Delay in excess of --delay
    Raises:
      Quit: If vim quit unexpectedly.
    """
    self.writer.Log(command)
    self.TryToSay([
        'vim',
        '--servername', self.args.servername,
        '--remote-send', command])
    self._cache = {}
    time.sleep(self.args.delay + extra_delay)

  def Ask(self, expression):
    """Asks vim for the result of an expression.

    Args:
      expression: The expression to ask for.
    Returns:
      Return value from vim, or None if vim had no output.
    Raises:
      Quit if vim quit unexpectedly.
      BadVimValue if vim returns a value that can't be deserialized.
    """
    try:
      out = self.TryToSay([
          'vim',
          '--servername', self.args.servername,
          '--remote-expr', 'string(%s)' % expression])
    except ErrorOnExit as e:
      if e.error_text.startswith('E449:'):  # Invalid expression received
        raise InvalidExpression(expression)
      raise
    # Vim adds a trailing newline to --remote-expr output if there isn't one
    # already.
    return DeserializeVimValue(out.rstrip())

  def GetCurrentLine(self):
    """Figures out what line the cursor is on.

    Returns:
      The cursor's line.
    """
    if 'line' not in self._cache:
      lineno = self.Ask("line('.')")
      try:
        self._cache['line'] = lineno
      except (ValueError, TypeError):
        raise ValueError("Vim lost the cursor, it thinks it's '%s'." % lineno)
    return self._cache['line']

  def GetBufferLines(self, number):
    """Gets the lines in the requesed buffer.

    Args:
      number: The buffer number to load. SHOULD NOT be a member of
          SpecialBuffer, use GetMessages if you want messages. Only works on
          real buffers.
    Returns:
      The buffer lines.
    """
    if number not in self._cache:
      num = "'%'" if number is None else number
      cmd = "getbufline(%s, 1, '$')" % num
      self._cache[number] = self.Ask(cmd)
    return self._cache[number]

  def GetMessages(self):
    """Gets the vim message list.

    Returns:
      The message list.
    """
    # This prevents GetMessages() from being called twice in a row.
    # (When checking a (msg) output line, first we check the messages then we
    # load the buffer.) Cleans up --dump-commands a bit.
    if 'msg' not in self._cache:
      cmd = "VroomExecute('silent! messages')"
      # Add trailing newline as workaround for http://bugs.python.org/issue7638.
      self._cache['msg'] = (self.Ask(cmd) + '\n').splitlines()
    return self._cache['msg']

  def Clear(self):
    self.writer.Log(None)
    self.Ask('VroomClear()')
    self._cache = {}

  def Output(self, writer):
    """Send the writer output to the user."""
    if hasattr(self, 'process'):
      buf = StringIO()
      writer.Write(buf)
      self.Ask('VroomDie({})'.format(VimscriptString(buf.getvalue())))
      buf.close()

  def Quit(self):
    """Tries to cleanly quit the vim process.

    Returns:
      True if vim successfully quit or wasn't running, False otherwise.
    """
    # We might die before the process is even set up.
    if hasattr(self, 'process'):
      if self.process.poll() is None:
        # Evaluate our VroomEnd function as an expression instead of issuing a
        # command, which works even if vim isn't in normal mode.
        try:
          self.Ask('VroomEnd()')
        except Quit:
          # Probably failed to quit. If vim is still running, we'll return False
          # below.
          pass
      if self.process.poll() is None:
        return False
      else:
        del self.process
    return True

  def Kill(self):
    """Kills the vim process."""
    # We might die before the process is even set up.
    if hasattr(self, 'process'):
      if self.process.poll() is None:
        self.process.kill()
      del self.process

  def TryToSay(self, cmd):
    """Execute a given vim process.

    Args:
      cmd: The command to send.
    Returns:
      stdout from vim.
    Raises:
      Quit: If vim quits unexpectedly.
    """
    if hasattr(self, 'process') and self.process.poll() is not None:
      raise ServerQuit()

    # Override messages generated by the vim client process (in particular, the
    # "No display" message) to be in English so that we can recognise them.
    # We do this by setting both LC_ALL (per POSIX) and LANGUAGE (a GNU gettext
    # extension) to en_US.UTF-8.  (Setting LANG=C would disable localisation
    # entirely, but has the bad side-effect of also setting the character
    # encoding to ASCII, which breaks when the remote side sends a non-ASCII
    # character.)
    #
    # Note that this does not affect messages from the vim server process,
    # which should be matched using error codes as usual.
    env = self.env.copy()
    env.update({
      'LANGUAGE': 'en_US.UTF-8',
      'LC_ALL': 'en_US.UTF-8'})

    out, err = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env).communicate()
    if out is None:
      raise Quit('Vim could not respond to query "%s"' % ' '.join(cmd[3:]))
    if err:
      error_text = err.decode('utf-8').rstrip('\n')
      if error_text == 'No display: Send expression failed.':
        raise NoDisplay(self.env.get('DISPLAY'))
      else:
        raise ErrorOnExit(error_text)
    return out.decode('utf-8')


def VimscriptString(string):
  """Escapes & quotes a string for usage as a vimscript string literal.

  Escaped such that \\n will mean newline (in other words double-quoted
  vimscript strings are used).

  >>> VimscriptString('Then (s)he said\\n"Hello"')
  '"Then (s)he said\\\\n\\\\"Hello\\\\""'

  Args:
    string: The string to escape.
  Returns:
    The escaped string, in double quotes.
  """
  return json.dumps(string)


def SplitCommand(string):
  """Parse out the actual command from the shell command.

  Vim will say things like
  /path/to/$SHELL -c '(cmd args) < /tmp/in > /tmp/out'
  We want to parse out just the 'cmd args' part. This is a bit difficult,
  because we don't know precisely what vim's shellescaping will do.

  This is a rather simple parser that grabs the first parenthesis block
  and knows enough to avoid nested parens, escaped parens, and parens in
  strings.

  NOTE: If the user does :call system('echo )'), *vim will error*. This is
  a bug in vim. We do not need to be sane in this case.

  >>> cmd, rebuild = SplitCommand('ls')
  >>> cmd
  'ls'
  >>> rebuild('mycmd')
  'mycmd'
  >>> cmd, rebuild = SplitCommand('(echo ")") < /tmp/in > /tmp/out')
  >>> cmd
  'echo ")"'
  >>> rebuild('mycmd')
  '(mycmd) < /tmp/in > /tmp/out'
  >>> SplitCommand('(cat /foo/bar > /tmp/whatever)')[0]
  'cat /foo/bar > /tmp/whatever'
  >>> SplitCommand("(echo '()')")[0]
  "echo '()'"

  Args:
    string: The command string to parse.
  Returns:
    (relevant, rebuild): A tuple containing the actual command issued by the
    user and a function to rebuild the full command that vim wants to execute.
  """
  if string.startswith('('):
    stack = []
    for i, char in enumerate(string):
      if stack and stack[-1] == '\\':
        stack.pop()
      elif stack and stack[-1] == '"' and char == '"':
        stack.pop()
      elif stack and stack[-1] == "'" and char == "'":
        stack.pop()
      elif stack and stack[-1] == '(' and char == ')':
        stack.pop()
      elif char in '\\\'("':
        stack.append(char)
      if not stack:
        return (string[1:i], lambda cmd: (string[0] + cmd + string[i:]))
  return (string, lambda cmd: cmd)


class Quit(Exception):
  """Raised when vim seems to have quit unexpectedly."""

  # Whether vroom should exit immediately or finish running other tests.
  is_fatal = False


class ServerQuit(Quit):
  """Raised when the vim server process quits unexpectedly."""

  is_fatal = True

  def __str__(self):
    return 'Vim server process quit unexpectedly'


class ErrorOnExit(Quit):
  """Raised when a vim process unexpectedly prints to stderr."""

  def __init__(self, error_text):
    super(ErrorOnExit, self).__init__()
    self.error_text = error_text

  def __str__(self):
    return 'Vim quit unexpectedly, saying "{}"'.format(self.error_text)


class InvalidExpression(Quit):
  def __init__(self, expression):
    super(InvalidExpression, self).__init__()
    self.expression = expression

  def __str__(self):
    return 'Vim failed to evaluate expression "{}"'.format(self.expression)


class NoDisplay(Quit):
  """Raised when vim can't access the defined display properly."""

  def __init__(self, display_value):
    super(NoDisplay, self).__init__()
    self.display_value = display_value

  def __str__(self):
    if self.display_value is not None:
      display_context = 'display "{}"'.format(self.display_value)
    else:
      display_context = 'unspecified display'
    return 'Vim failed to access {}'.format(display_context)


class BadVimValue(Exception):
  """Raised when vroom fails to deserialize a serialized value from vim."""

  is_fatal = False

  def __init__(self, value):
    self.value = value

  def __str__(self):
    return 'Vroom failed to deserialize vim value {!r}'.format(self.value)
