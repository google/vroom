"""Vroom fake shell bridge."""
import json
import os
import os.path
import pickle
import pipes
import re
import tempfile

import vroom
import vroom.controls
import vroom.test

# Pylint is not smart enough to notice that all the exceptions here inherit from
# vroom.test.Failure, which is a standard Exception.
# pylint: disable-msg=nonstandard-exception

VROOMFILE_VAR = 'VROOMFILE'
VROOMDIR_VAR = 'VROOMDIR'
LOG_FILENAME_VAR = 'VROOM_SHELL_LOGFILE'
CONTROL_FILENAME_VAR = 'VROOM_SHELL_CONTROLLFILE'
ERROR_FILENAME_VAR = 'VROOM_SHELL_ERRORFILE'

CONTROL = vroom.Specification(
    EXPECT='expect',
    RESPOND='respond')

STRICTNESS = vroom.Specification(
    STRICT='STRICT',
    RELAXED='RELAXED')

OUTCHANNEL = vroom.Specification(
    COMMAND='command',
    STDOUT='stdout',
    STDERR='stderr',
    STATUS='status')

DEFAULT_MODE = vroom.controls.MODE.REGEX


def Load(filename):
  """Loads a shell file into python space.

  Args:
    filename: The shell file to load.
  Returns:
    The file contents.
  Raises:
    FakeShellNotWorking
  """
  try:
    with open(filename, 'rb') as f:
      return pickle.load(f)
  except IOError:
    raise FakeShellNotWorking


def Send(filename, data):
  """Sends python data to a shell file.

  Args:
    filename: The shell file to send to.
    data: The python data to send.
  """
  with open(filename, 'wb') as f:
    pickle.dump(data, f)


class Communicator(object):
  """Object to communicate with the fake shell."""

  def __init__(self, filename, env, writer):
    self.vroom_env = env
    self.writer = writer.syscalls
    self.commands_writer = writer.commands

    _, self.control_filename = tempfile.mkstemp()
    _, self.log_filename = tempfile.mkstemp()
    _, self.error_filename = tempfile.mkstemp()
    Send(self.control_filename, [])
    Send(self.log_filename, [])
    Send(self.error_filename, [])

    self.env = os.environ.copy()
    self.env[VROOMFILE_VAR] = filename
    self.env[VROOMDIR_VAR] = os.path.dirname(filename) or '.'
    self.env[vroom.shell.LOG_FILENAME_VAR] = self.log_filename
    self.env[vroom.shell.CONTROL_FILENAME_VAR] = self.control_filename
    self.env[vroom.shell.ERROR_FILENAME_VAR] = self.error_filename

    self._copied_logs = 0

  def Control(self, hijacks):
    """Tell the shell the system control specifications."""
    existing = Load(self.control_filename)
    Send(self.control_filename, existing + hijacks)

  def Verify(self):
    """Checks that system output was caught and handled satisfactorily.

    Raises:
      FakeShellNotWorking: If it can't load the shell file.
      vroom.test.Failures: If there are other failures.
    """
    # Copy any new logs into the logger.
    logs = Load(self.log_filename)
    for log in logs[self._copied_logs:]:
      self.writer.Log(log)
    self._copied_logs = len(logs)

    failures = []

    # Check for shell errors.
    errors = Load(self.error_filename)
    if errors:
      failures.append(FakeShellNotWorking(errors))

    commands_logs = self.commands_writer.Logs()

    # Check that all controls have been handled.
    controls = Load(self.control_filename)
    if controls:
      Send(self.control_filename, [])
      missed = controls[0]
      if missed.expectation:
        failures.append(SystemNotCalled(logs, controls, commands_logs))
      failures.append(NoChanceForResponse(
          logs, missed, commands_logs))

    # Check for unexpected calls, if they user is into that.
    if self.vroom_env.system_strictness == STRICTNESS.STRICT:
      logs = self.writer.Logs()
      if [log for log in logs if log.TYPE == vroom.test.LOG.UNEXPECTED]:
        failures.append(UnexpectedSystemCalls(logs, commands_logs))

    if failures:
      raise vroom.test.Failures(failures)


class Hijack(object):
  """An object used to tell the fake shell what to do about system calls.

  It can contain a single expectation (of a system call) and any number of
  responses (text to return when the expected call is seen).

  If no expectation is given, it will match any command.
  If no responses are given, the command will be allowed through the fake shell.

  The Hijack can be 'Open' or 'Closed': we need a way to distinguish
  between this:

    $ One
    $ Two

  and this:

    $ One

    $ Two

  The former responds "One\\nTwo" to any command. The latter responds "One" to
  the first command, whatever it may be, and then "Two" to the next command.

  The solution is that line breaks "Close" an expectation. In this way, we can
  tell if a new respones should be part of the previous expectation or part of
  a new one.
  """

  def __init__(self, fakecmd, expectation=None, mode=None):
    self.closed = False
    self.fakecmd = fakecmd
    self.response = {}
    self.expectation = expectation
    self.mode = mode or DEFAULT_MODE

  def Response(self, command):
    """Returns the command that should be done in place of the true command.

    This will either be the original command or a call to respond.vroomfaker.

    Args:
      command: The vim-requested command.
    Returns:
      The user-specified command.
    """
    if self.expectation is not None:
      if not vroom.test.Matches(self.expectation, self.mode, command):
        return False

    # We don't want to do this on init because regexes don't repr() as nicely as
    # strings do.
    if self.expectation and self.mode == vroom.controls.MODE.REGEX:
      try:
        match_regex = re.compile(self.expectation)
      except re.error as e:
        raise vroom.ParseError("Can't match command. Invalid regex. %s'" % e)
    else:
      match_regex = re.compile(r'.*')

    # The actual response won't be exactly like the internal response, because
    # we've got to do some regex group binding magic.
    response = {}

    # Expand all of the responders that want to be bound to the regex.
    for channel in (
        OUTCHANNEL.COMMAND,
        OUTCHANNEL.STDOUT,
        OUTCHANNEL.STDERR):
      for line in self.response.get(channel, []):
        # We do an re.sub() regardless of whether the control was bound as
        # a regex: this forces you to escape consistently between all match
        # groups, which will help prevent your tests from breaking if you later
        # switch the command matching to regex from verbatim/glob.
        try:
          line = match_regex.sub(line, command)
        except re.error as e:
          # 'invalid group reference' is the expected message here.
          # Unfortunately the python re module doesn't differentiate its
          # exceptions well.
          if self.mode != vroom.controls.MODE.REGEX:
            raise vroom.ParseError(
                'Substitution error. '
                'Ensure that matchgroups (such as \\1) are escaped.')
          raise vroom.ParseError('Substitution error: %s.' % e)
        response.setdefault(channel, []).append(line)

    # The return status can't be regex-bound.
    if OUTCHANNEL.STATUS in self.response:
      response[OUTCHANNEL.STATUS] = self.response[OUTCHANNEL.STATUS]

    # If we actually want to do anything, call out to the responder.
    if response:
      return '%s %s' % (self.fakecmd, pipes.quote(json.dumps(response)))
    return command

  def Respond(self, line, channel=None):
    """Adds a response to this expectation.

    Args:
      line: The response to add.
      channel: The output channel to respond with 'line' in.
    """
    if channel is None:
      channel = OUTCHANNEL.STDOUT
    if channel == OUTCHANNEL.COMMAND:
      self.response.setdefault(OUTCHANNEL.COMMAND, []).append(line)
    elif channel == OUTCHANNEL.STDOUT:
      self.response.setdefault(OUTCHANNEL.STDOUT, []).append(line)
    elif channel == OUTCHANNEL.STDERR:
      self.response.setdefault(OUTCHANNEL.STDERR, []).append(line)
    elif channel == OUTCHANNEL.STATUS:
      if OUTCHANNEL.STATUS in self.response:
        raise vroom.ParseError('A system call cannot return two statuses!')
      try:
        status = int(line)
      except ValueError:
        raise vroom.ParseError('Returned status must be a number.')
      self.response[OUTCHANNEL.STATUS] = status
    else:
      assert False, 'Unrecognized output channel word.'

  def __repr__(self):
    return 'Hijack(%s, %s, %s)' % (self.expectation, self.mode, self.response)

  def __str__(self):
    out = ''
    # %07s pads things out to match  with "COMMAND:"
    if self.expectation is not None:
      out += ' EXPECT:\t%s (%s mode)\n' % (self.expectation, self.mode)
    rejoiner = '\n%07s\t' % ''
    if OUTCHANNEL.COMMAND in self.response:
      out += 'COMMAND:\t%s\n' % rejoiner.join(self.response[OUTCHANNEL.COMMAND])
    if OUTCHANNEL.STDOUT in self.response:
      out += ' STDOUT:\t%s\n' % rejoiner.join(self.response[OUTCHANNEL.STDOUT])
    if OUTCHANNEL.STDERR in self.response:
      out += ' STDERR:\t%s\n' % rejoiner.join(self.response[OUTCHANNEL.STDERR])
    if 'status' in self.response:
      out += ' STATUS:\t%s' % self.response['status']
    return out.rstrip('\n')


class FakeShellNotWorking(Exception):
  """Called when the fake shell is not working."""

  def __init__(self, errors):
    self.shell_errors = errors
    super(FakeShellNotWorking, self).__init__()

  def __str__(self):
    return 'The fake shell is not working as anticipated.'


class FakeShellFailure(vroom.test.Failure):
  """Generic fake shell error. Please raise its implementors."""
  DESCRIPTION = 'System failure'
  CONTEXT = 12

  def __init__(self, logs, commands, message=None):
    self.syscalls = logs[-self.CONTEXT:]
    self.commands = commands
    super(FakeShellFailure, self).__init__(message or self.DESCRIPTION)


class UnexpectedSystemCalls(FakeShellFailure):
  """Raised when a system call is made unexpectedly."""
  DESCRIPTION = 'Unexpected system call.'


class SystemNotCalled(FakeShellFailure):
  """Raised when an expected system call is not made."""
  DESCRIPTION = 'Expected system call not received.'

  def __init__(self, logs, expectations, commands):
    self.expectations = expectations
    super(SystemNotCalled, self).__init__(logs, commands)


class NoChanceForResponse(FakeShellFailure):
  """Raised when no system calls were made, but a response was specified."""
  DESCRIPTION = 'Got no chance to inject response: \n%s'

  def __init__(self, logs, response, commands):
    super(NoChanceForResponse, self).__init__(
        logs, commands, self.DESCRIPTION % response)
