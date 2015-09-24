"""Vroom command blocks.

Vroom actions are written (by the user) out of order (from vroom's perspective).
Consider the following:

  :.!echo "Hi"
  $ Bye

Vroom must hijack the shell before the command is ever executed if the fake
shell is to know that to do when the system call comes down the line.

Thus, we need a Command object which is the combination of a command and all of
the checks and responses attached to it.
"""
import vroom.test

from vroom.result import Result

class Command(object):
  """Holds a vim command and records all checks requiring verification."""

  def __init__(self, command, lineno, delay, env):
    self.lineno = lineno
    self.env = env
    self.command = command
    self.delay = delay
    self.fakecmd = env.args.responder
    self._mexpectations = []
    self._syspectations = []

  def ExpectMessage(self, message, mode):
    self._mexpectations.append((message, mode))

  def ExpectSyscall(self, syscall, mode):
    if self._syspectations:
      self._syspectations[-1].closed = True
    self._syspectations.append(vroom.shell.Hijack(self.fakecmd, syscall, mode))

  def RespondToSyscall(self, response, **controls):
    if not self._syspectations or self._syspectations[-1].closed:
      self._syspectations.append(vroom.shell.Hijack(self.fakecmd))
    self._syspectations[-1].Respond(response, **controls)

  def LineBreak(self):
    if self._syspectations:
      self._syspectations[-1].closed = True

  def Execute(self):
    """Executes the command and verifies all checks."""
    if not any((self.command, self._mexpectations, self._syspectations)):
      return Result.Success()

    self.env.shell.Control(self._syspectations)
    oldmessages = self.env.vim.GetMessages()
    if self.lineno:
      self.env.writer.actions.ExecutedUpTo(self.lineno)
    if self.command:
      delay = self.delay
      if self._syspectations:
        delay += self.env.args.shell_delay
      self.env.vim.Communicate(self.command, delay)

    failures = []
    # Verify the message list.
    newmessages = self.env.vim.GetMessages()
    result = self.env.messenger.Verify(
        oldmessages, newmessages, self._mexpectations)
    if result.IsError():
      failures.append(result.value)

    # Verify the shell.
    result = self.env.shell.Verify()
    if result.IsError():
      failures.append(result.value)

    if failures:
      return Result.Error(vroom.test.Failures(failures))
    else:
      return Result.Success()
