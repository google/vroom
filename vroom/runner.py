"""The Vroom test runner. Does the heavy lifting."""
import sys

import vroom
import vroom.actions
import vroom.args
import vroom.buffer
import vroom.command
import vroom.environment
import vroom.output
import vroom.shell
import vroom.test
import vroom.vim

# Pylint is not smart enough to notice that all the exceptions here inherit from
# vroom.test.Failure, which is a standard Exception.
# pylint: disable-msg=nonstandard-exception


class Vroom(object):
  """Executes vroom tests."""

  def __init__(self, filename, args):
    """Creates the vroom test.

    Args:
      filename: The name of the file to execute.
      args: The vroom command line flags.
    """
    self._message_strictness = args.message_strictness
    self._system_strictness = args.system_strictness
    self._lineno = None
    # Whether this vroom instance has left the terminal in an unknown state.
    self.dirty = False
    self.env = vroom.environment.Environment(filename, args)
    self.ResetCommands()

  def ResetCommands(self):
    self._running_command = None
    self._command_queue = []

  def GetCommand(self):
    if not self._command_queue:
      self.PushCommand(None, None)
    return self._command_queue[-1]

  def PushCommand(self, line, delay=None):
    self._command_queue.append(
        vroom.command.Command(line, self._lineno, delay or 0, self.env))

  def ExecuteCommands(self):
    if not self._command_queue:
      return
    self.env.buffer.Unload()
    for self._running_command in self._command_queue:
      self._running_command.Execute()
    self.ResetCommands()

  def __call__(self, filehandle):
    """Runs vroom on a file.

    Args:
      filehandle: The open file to run on.
    Returns:
      A writer to write the test output later.
    """
    lines = list(filehandle)
    try:
      self.env.writer.Begin(lines)
      self.env.vim.Start()
      self.Run(lines)
    except vroom.ParseError as e:
      self.Record(vroom.test.RESULT.ERROR, e)
    except vroom.test.Failure as e:
      self.Record(vroom.test.RESULT.FAILED, e)
    except vroom.vim.Quit as e:
      # TODO(dbarnett): Revisit this when terminal reset is no longer necessary.
      if e.is_fatal:
        raise
      self.Record(vroom.test.RESULT.ERROR, e)
    except Exception:
      self.env.writer.actions.Exception(*sys.exc_info())
    finally:
      if not self.env.args.interactive:
        if not self.env.vim.Quit():
          self.dirty = True
          self.env.vim.Kill()
    status = self.env.writer.Status()
    if status != vroom.output.STATUS.PASS and self.env.args.interactive:
      self.env.vim.Output(self.env.writer)
      self.env.vim.process.wait()
    return self.env.writer

  def Record(self, result, error=None):
    """Add context to an error and log it.

    The current line number is added to the context when possible.

    Args:
      result: The log type, should be a member of vroom.test.RESULT
      error: The exception, if any.
    """
    # Figure out the line where the event happened.
    if self._running_command and self._running_command.lineno is not None:
      lineno = self._running_command.lineno
    elif self._lineno is not None:
      lineno = self._lineno
    else:
      lineno = getattr(error, 'lineno', None)
    if lineno is not None:
      self.env.writer.actions.Log(result, lineno, error)
    else:
      self.env.writer.actions.Error(result, error)

  def Test(self, function, *args, **kwargs):
    self.ExecuteCommands()
    function(*args, **kwargs)

  def Run(self, lines):
    """Runs a vroom file.

    Args:
      lines: List of lines in the file.
    """
    actions = list(vroom.actions.Parse(lines))
    for (self._lineno, action, line, controls) in actions:
      if action == vroom.actions.ACTION.PASS:
        # Line breaks send you back to the top of the buffer.
        self.env.buffer.Unload()
        # Line breaks distinguish between consecutive system hijacks.
        self.GetCommand().LineBreak()
      elif action == vroom.actions.ACTION.TEXT:
        self.PushCommand('i%s<ESC>' % line, **controls)
      elif action == vroom.actions.ACTION.COMMAND:
        self.PushCommand(':%s<CR>' % line, **controls)
      elif action == vroom.actions.ACTION.INPUT:
        self.PushCommand(line, **controls)
      elif action == vroom.actions.ACTION.MESSAGE:
        self.GetCommand().ExpectMessage(line, **controls)
      elif action == vroom.actions.ACTION.SYSTEM:
        self.GetCommand().ExpectSyscall(line, **controls)
      elif action == vroom.actions.ACTION.HIJACK:
        self.GetCommand().RespondToSyscall(line, **controls)
      elif action == vroom.actions.ACTION.DIRECTIVE:
        if line == vroom.actions.DIRECTIVE.CLEAR:
          self.ExecuteCommands()
          self.env.writer.actions.Log(vroom.test.RESULT.PASSED, self._lineno)
          self.env.vim.Clear()
        elif line == vroom.actions.DIRECTIVE.END:
          self.Test(self.env.buffer.EnsureAtEnd, **controls)
        elif line == vroom.actions.DIRECTIVE.MESSAGES:
          self.ExecuteCommands()
          strictness = controls.get('messages') or self._message_strictness
          self.env.message_strictness = strictness
        elif line == vroom.actions.DIRECTIVE.SYSTEM:
          self.ExecuteCommands()
          strictness = controls.get('system') or self._system_strictness
          self.env.system_strictness = strictness
        else:
          raise vroom.ConfigurationError('Unrecognized directive "%s"' % line)
      elif action == vroom.actions.ACTION.OUTPUT:
        self.Test(self.env.buffer.Verify, line, **controls)
      else:
        raise vroom.ConfigurationError('Unrecognized action "%s"' % action)
    self.ExecuteCommands()
    self.env.writer.actions.Log(vroom.test.RESULT.PASSED, self._lineno or 0)
    self.env.vim.Quit()
